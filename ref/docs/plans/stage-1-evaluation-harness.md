# Stage 1 Plan: Evaluation Harness & Metrics Infrastructure

**Status**: 🚧 In Progress (core harness shipped; metrics math fix + baselines pending)  
**Goal**: Build a dual-mode evaluation harness (blind/reference) with Excel + JSON outputs for regression checks.  
**Deliverable**: `tools/evaluate.py` producing correct precision/recall math, Excel/JSON artifacts, and a seeded baseline/CI smoke test.  
**Date**: 2025-12-11

## Scope & Goals
- [x] Confirm `tools/evaluate.py` replaces `parser_test.py` while reusing its CLI ergonomics and dataset loading logic
- [x] Keep the harness dataset-agnostic (`current-results.xlsx`, `sample-results.csv`, future labeled references)
- [x] Provide two modes: **blind** (coverage-first, no labels) and **reference** (accuracy vs. expected labels)
- [x] Establish durable outputs for humans (Excel table) and automation (JSON metrics)
- [ ] Fix precision/recall math to treat `None/None` as neutral so metrics never exceed 1.0; rerun latest reference set to refresh baseline

## Evaluation Script (`tools/evaluate.py`)
- [x] Port core parsing loop from `parser_test.py` (batch parse, progress output, error handling)
- [x] Add CLI flags: `--mode {blind,reference}`, `--input`, `--baseline`, `--output-json`, `--output-excel`, `--limit`, `--samples`
- [x] Factor parser bootstrap into a shared helper to reuse `parser.py` setup
- [x] Support dry-run (`--no-write`) to skip file outputs for quick checks
- [x] Support `--skip-excel` flag for faster CI runs
- [ ] Document expected input columns and default paths in a README stub

### Blind Mode (no labeled reference)
- [x] Parse dataset and compute coverage for existing fields: `{studio, performers, date, studio_code, path}`
- [x] Track coverage for new fields as they land: `{title, sequence, group}`
- [x] Generate pattern histogram (top 20) and frequency of unknown tokens
- [x] Produce anomaly buckets: rows with unlabeled tokens, total unlabeled token count
- [x] Emit outputs: console summary, JSON metrics, Excel summary table
- [x] **DECISION**: Single sheet named "Filename Parser Results" for blind mode
- [x] **DECISION**: Row-level data in blind mode Excel (not just aggregates)

### Reference Mode (with expected labels/baseline)
- [x] Accept labeled reference file (e.g., curated `.xlsx` with expected columns)
- [x] Compute per-field precision/recall/F1 vs. reference labels; surface false positives/negatives
- [x] Produce diff vs. baseline metrics with field-level breakdown
- [x] Capture sample mismatches (fp/fn) capped by CLI flag for quick inspection
- [x] Output Excel workbook with three sheets: Reference, Results, Diff
- [x] **DECISION**: Reference file must match 16-column schema exactly
- [ ] TODO: Add baseline comparison and threshold checks

## Output Artifacts
- [x] JSON metrics: timestamped, stored under `metrics/` with mode encoded in filename
- [x] Excel workbook: replaces `parser_test` output; bundles all data
- [x] **DECISION**: Filename pattern is `metrics/{mode}-YYYYMMDD-HHMMSS.{xlsx|json}`
- [ ] Optional CSV/Markdown summary for PR comments (reference mode)

### Excel Output Format (aligned to `master.xlsx`)
- [x] Blind mode: single sheet `Filename Parser Results` (schema below)
- [x] Reference mode: three sheets
  - [x] `Reference` (verbatim copy of provided reference data, same columns)
  - [x] `Results` (parser output, same columns)
  - [x] `Diff` (same columns; differing cells contain `{"expected": "...", "returned": "..."}`)
- [x] Column schema (order preserved):
  1. `input` (string): raw path/filename as received
  2. `removed` (string): stripped tokens with labels, e.g., `.mp4(extension_mp4) | 1080P(resolution_1080P)`
  3. `path` (string/NaN): parent directories after stripping filename
  4. `filename_cleaned` (string): basename after removals; separators/brackets preserved as-is; no POV artifact
  5. `path_pattern` (string/NaN): template of recognized path tokens, e.g., `{studio} {text}/{group}`
  6. `filename_pattern` (string): template of recognized filename tokens, e.g., `({studio}) - {title} ({date})`
  7. `studio` (string/NaN): canonical studio label from parser logic
  8. `title` (string/NaN): structured title from parser logic (not merely leftovers)
  9. `performers` (string/NaN): comma-delimited performer list from parser logic
  10. `date` (string/NaN): normalized date
  11. `studio_code` (string/NaN): extracted code/ID
  12. `sequence` (JSON/NaN): typed scene/ordinal info, e.g., `{"scene": 2}` or `{"title": 2}` (true JSON)
  13. `group` (string/NaN): scene series / collection bucket from path context
  14. `unlabeled_path_tokens` (set-string/NaN): leftover path tokens, e.g., `{"PART 1"}`
  15. `unlabeled_filename_tokens` (set-string/NaN): leftover filename tokens, e.g., `{"SexScenes","Primetime"}`
  16. `match_stats` (JSON/NaN): token accounting with numeric values, e.g., `{"path_tokens": 0, "filename_tokens": 3, "matched_tokens": 3, "match_rate": 1.0}` (true JSON)
- [ ] TODO: Lock data types (JSON columns materialized as dicts in memory, serialized compactly in Excel; no stringified numbers)
- [ ] TODO: Add schema validation step to catch ordering/type drift before writing workbook
- [ ] TODO: Keep separators untouched in `filename_cleaned`; normalization occurs elsewhere in the pipeline

### Excel Write Implementation
- [x] Build a dataclass/struct for row emission with explicit fields in the above order
- [x] Emit `sequence` and `match_stats` as real dicts; serialize via openpyxl (compact JSON in sheet)
- [x] Preserve set-ish columns as brace-wrapped strings for readability
- [x] **IMPLEMENTATION NOTE**: Parser extracts all fields directly via pipeline modules - evaluator just reads them
- [ ] Include a schema assertion test to ensure column order and presence before writing (both Results and Diff)
- [x] Implement diff generation: for each cell difference in `Diff`, emit `{"expected": <ref>, "returned": <result>}`; otherwise copy the agreed value

## Integration & CI
- [ ] Add pytest wrapper around evaluation harness (smoke run both modes on small fixture)
- [ ] Seed `metrics/baseline.json` from first successful reference-mode run
- [ ] CI check: fail when coverage drops >2% (blind) or precision/recall drops beyond threshold (reference)
- [ ] TODO: add GitHub Actions job invoking both modes with a small sample dataset
- [ ] TODO: keep metrics artifacts as workflow uploads without committing large files

## Testing the Harness
- [ ] Unit test coverage calculations vs. hand-computed expectations
- [ ] Property test histogram counts for determinism
- [ ] Golden-file test for diff output between two JSON runs
- [ ] TODO: fixture for Excel writer to ensure consistent columns/order across runs

## Open Design Questions
- [x] Finalize Excel table columns (coverage summary, anomalies, mismatches, diffs) - **RESOLVED**: Using 16-column schema with row-level data
- [ ] Should blind mode include lightweight heuristic scoring for performer candidates?
- [x] Where to store/reference-mode labels (inline workbook tabs vs. separate CSV)? - **RESOLVED**: Three-sheet Excel workbook for reference mode
- [ ] Do we keep any JSON/Excel outputs in git or only as CI artifacts?
- [ ] What minimum sample size is acceptable for quick CI smoke vs. full dataset?

---

## Implementation Notes (2025-12-11)

### Architecture Decisions

**Extraction Logic Location**: Title and sequence extraction moved to parser pipeline modules rather than evaluation tool
- Created `modules/sequence_extractor.py` for part/scene/episode/volume/title-number extraction
- Created `modules/title_extractor.py` for title extraction from unlabeled tokens
- Parser pipeline now runs: pre-tokenize → tokenize → date → studio → studio_code → performers → **sequence** → **title**
- Evaluation harness simply reads `result.title`, `result.sequence`, `result.group` from parser

**Mode Calculation Differences**:
- **Blind mode**: Calculates coverage as `matched_tokens / total_tokens` where matched includes all labeled fields (studio, performers, date, studio_code, sequence, title)
- **Reference mode**: Calculates precision/recall/F1 per field by comparing parsed results vs reference labels

**Excel Output Strategy**:
- Blind mode: Single sheet "Filename Parser Results" with all 16 columns
- Reference mode: Three sheets (Reference, Results, Diff) all using same 16-column schema
- Diff cells show `{"expected": <ref>, "returned": <parsed>}` for mismatches

### Field Extraction Rules (User-Defined)

**Title**:
- Extracted from leftover unlabeled tokens after all other extraction
- Must contain at least one meaningful word (2+ letter alphabetic sequences)
- Trailing numbers extracted as sequence `{"title": N}` if present

**Sequence** (multiple indicators possible, stored in order):
- **Part**: `pt. N`, `pt N`, `pN`, `p.N`, `part N`, `partN`, `part.N`, `part-N` (may have `#` between)
- **Scene**: `scene N`, `sc N`, `s N` patterns (BUT: `sc-?NNNN` = Sean Cody studio code, skip)
- **Episode**: `episode N`, `ep N`, `e N` patterns
- **Volume**: `vol N`, `v N` patterns (can be in filename OR parent directory)
- **Title number**: Loose number at end of title string (e.g., "Some Title 3" → title="Some Title", sequence={"title": 3})
- Multiple sequence indicators merged into single dict (last wins for duplicates)

**Group**:
- Immediate parent directory name from path
- Extracted during sequence extraction phase

### File Structure Created

```
filename-parser/
├── tools/
│   └── evaluate.py          # Main evaluation harness
├── modules/
│   ├── sequence_extractor.py  # NEW: Sequence & group extraction
│   ├── title_extractor.py     # NEW: Title extraction
│   └── ...
├── metrics/                   # NEW: Output directory
│   ├── blind-YYYYMMDD-HHMMSS.xlsx
│   ├── blind-YYYYMMDD-HHMMSS.json
│   └── ...
└── plans/
    └── stage-1-evaluation-harness.md
```

### Testing Status

- ✅ Blind mode tested with sample data (20 rows)
- ✅ Title extraction working correctly (85% coverage in test)
- ✅ Sequence extraction working (5% coverage in test - low due to sample data)
- ✅ Excel output generating properly with 16-column schema
- ✅ JSON metrics capturing coverage, patterns, anomalies
- ⚠️ Reference mode implemented but not yet tested with real reference data
- ⚠️ Baseline comparison logic not yet implemented

### Next Steps

1. Test reference mode with actual reference file
2. Implement baseline comparison and threshold checks
3. Add pytest wrappers for both modes
4. Set up CI integration
5. Document CLI usage in README
