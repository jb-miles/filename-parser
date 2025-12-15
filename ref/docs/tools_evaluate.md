# Evaluation Harness (`tools/evaluate.py`)

Comprehensive evaluation tool for the filename parser with coverage metrics and reference comparison capabilities.

## Overview

The evaluation harness provides two distinct modes for analyzing parser performance:

- **Blind Mode**: Coverage-first metrics without reference labels (default)
- **Reference Mode**: Precision/recall comparison against labeled reference data

## Installation & Requirements

```bash
# Required packages
pip install openpyxl

# Run from filename-parser directory
cd /path/to/filename-parser
python tools/evaluate.py [options]
```

## Command Line Interface

### Basic Usage

```bash
# Blind mode (default) - coverage metrics
python tools/evaluate.py --input sample.txt

# Reference mode - compare against labels
python tools/evaluate.py --mode reference --input reference.xlsx

# Dry run - no file output
python tools/evaluate.py --input sample.txt --no-write

# Limit processing to N files
python tools/evaluate.py --input sample.txt --limit 100
```

### CLI Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mode` | choice | `blind` | Evaluation mode: `blind` or `reference` |
| `--input` | path | *required* | Input file (`.txt` for blind, `.xlsx` for reference) |
| `--baseline` | path | - | Baseline metrics JSON for comparison (reference mode) |
| `--output-excel` | path | auto | Output Excel file path |
| `--output-json` | path | auto | Output JSON metrics file path |
| `--limit` | int | - | Limit number of files to process |
| `--samples` | int | `10` | Number of mismatch samples (reference mode) |
| `--no-write` | flag | `false` | Dry-run mode: skip writing output files |
| `--skip-excel` | flag | `false` | Skip Excel output for faster CI runs |

### Default Output Paths

When `--output-excel` or `--output-json` are not specified:

```
metrics/{mode}-YYYYMMDD-HHMMSS.xlsx
metrics/{mode}-YYYYMMDD-HHMMSS.json
```

Examples:
- `metrics/blind-20251211-143540.xlsx`
- `metrics/reference-20251211-150322.json`

## Input Formats

### Blind Mode Input

**Text file** (`.txt`) with one filename per line:

```
LatinLeche - I Can Dry Your Shirt (Brunito Querido).mp4
(2005) Eurocreme - RAW Films - Raw Edge (720p).mp4
BelAmi - Kinky Angels - Scene 3 (Kevin Warhol).mp4
```

**Excel file** (`.xlsx`) with `input` column containing filenames.

### Reference Mode Input

**Excel file** (`.xlsx`) with the **exact 16-column schema**:

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `input` | string | Raw path/filename |
| 2 | `removed` | string | Stripped tokens with labels |
| 3 | `path` | string/null | Parent directories |
| 4 | `filename_cleaned` | string | Basename after removals |
| 5 | `path_pattern` | string/null | Path token template |
| 6 | `filename_pattern` | string | Filename token template |
| 7 | `studio` | string/null | Studio name |
| 8 | `title` | string/null | Extracted title |
| 9 | `performers` | string/null | Comma-delimited performers |
| 10 | `date` | string/null | Normalized date |
| 11 | `studio_code` | string/null | Studio code/ID |
| 12 | `sequence` | JSON/null | Sequence info (e.g., `{"scene": 2}`) |
| 13 | `group` | string/null | Parent directory/collection |
| 14 | `unlabeled_path_tokens` | set-string/null | Leftover path tokens |
| 15 | `unlabeled_filename_tokens` | set-string/null | Leftover filename tokens |
| 16 | `match_stats` | JSON | Token accounting metrics |

**Note**: Reference file must match this schema exactly for comparison.

## Output Formats

### Excel Output

#### Blind Mode: Single Sheet

**Sheet Name**: `Filename Parser Results`

Contains all 16 columns with parsed data for each input filename.

**Example Row**:
```
input: LatinLeche - I Can Dry Your Shirt (Brunito Querido).mp4
removed: .mp4(extension_mp4)
path: (empty)
filename_cleaned: LatinLeche - I Can Dry Your Shirt (Brunito Querido)
filename_pattern: {studio} {title} {performers}
studio: Latin Leche
title: I Can Dry Your Shirt
performers: Brunito Querido
match_stats: {"filename_tokens": 3, "matched_tokens": 3, "match_rate": 1.0}
```

#### Reference Mode: Three Sheets

1. **Reference Sheet**
   - Verbatim copy of input reference data
   - Same 16-column schema

2. **Results Sheet**
   - Parser output for same inputs
   - Same 16-column schema

3. **Diff Sheet**
   - Shows differences between Reference and Results
   - Matching cells: show the agreed value
   - Differing cells: `{"expected": "<reference>", "returned": "<parsed>"}`

**Example Diff Cell**:
```
studio: {"expected": "Latin Leche", "returned": "LatinLeche"}
title: I Can Dry Your Shirt  (both matched)
```

### JSON Metrics Output

#### Blind Mode JSON

```json
{
  "mode": "blind",
  "total_rows": 20,
  "avg_match_rate": 0.9850,
  "field_coverage": {
    "studio": 0.80,
    "performers": 0.65,
    "date": 0.10,
    "studio_code": 0.10,
    "title": 0.35,
    "sequence": 0.15,
    "group": 0.35
  },
  "pattern_histogram": [
    {"pattern": "{studio} {performers}", "count": 4},
    {"pattern": "{performers}", "count": 4},
    {"pattern": "{studio} {title}", "count": 2}
  ],
  "anomalies": {
    "rows_with_unlabeled_tokens": 3,
    "total_unlabeled_tokens": 8
  },
  "timestamp": "2025-12-11T14:35:40.123456"
}
```

**Field Coverage**: Percentage of rows where each field is populated.

**Pattern Histogram**: Top 20 most common token patterns.

**Anomalies**:
- `rows_with_unlabeled_tokens`: Count of rows with tokens that couldn't be classified
- `total_unlabeled_tokens`: Total number of unclassified tokens across all rows

#### Reference Mode JSON

```json
{
  "mode": "reference",
  "total_rows": 20,
  "overall_accuracy": 0.8571,
  "field_metrics": {
    "studio": {
      "precision": 0.9375,
      "recall": 0.9375,
      "f1": 0.9375,
      "correct": 15,
      "total": 20,
      "false_positives": 1,
      "false_negatives": 0,
      "incorrect": 4
    },
    "title": {
      "precision": 1.0,
      "recall": 0.7143,
      "f1": 0.8333,
      "correct": 5,
      "total": 20,
      "false_positives": 0,
      "false_negatives": 2,
      "incorrect": 0
    }
  },
  "sample_mismatches": [
    {
      "input": "LatinLeche - Scene (Performers).mp4",
      "field": "studio",
      "parsed": "LatinLeche",
      "expected": "Latin Leche"
    }
  ],
  "timestamp": "2025-12-11T15:03:22.654321"
}
```

**Per-Field Metrics**:
- `precision`: correct / (parsed non-null)
- `recall`: correct / (reference non-null)
- `f1`: harmonic mean of precision and recall
- `correct`: number of exact matches
- `false_positives`: parser returned value, reference had null
- `false_negatives`: parser returned null, reference had value
- `incorrect`: both non-null but different values

**Sample Mismatches**: Up to `--samples` examples of differences (default: 10).

## Console Output

### Blind Mode Console

```
=== Filename Parser Evaluation (blind mode) ===
Input: sample.txt
Excel output: metrics/blind-20251211-143540.xlsx
JSON output: metrics/blind-20251211-143540.json

Reading input...
Found 20 filenames to process

Parsing filenames...
Completed parsing 20 filenames

Calculating blind mode metrics...

=== Metrics Summary ===
Total rows: 20
Average match rate: 100.00%

Field coverage:
  studio: 55.00%
  performers: 65.00%
  date: 10.00%
  studio_code: 10.00%
  title: 35.00%
  sequence: 15.00%
  group: 35.00%

Top 5 patterns:
  {studio} {performers}: 4 occurrences
  {performers}: 4 occurrences
  {studio} {title}: 2 occurrences
  {sequence}: 2 occurrences
  {studio} {title} {date}: 1 occurrences

Writing Excel output to metrics/blind-20251211-143540.xlsx...
Writing JSON metrics to metrics/blind-20251211-143540.json...

✓ Evaluation complete!
```

### Reference Mode Console

```
=== Filename Parser Evaluation (reference mode) ===
Input: reference.xlsx
Excel output: metrics/reference-20251211-150322.xlsx
JSON output: metrics/reference-20251211-150322.json

Reading input...
Found 20 filenames to process

Parsing filenames...
Completed parsing 20 filenames

Calculating reference mode metrics...
Loading reference data from reference.xlsx...
Comparing 20 parsed rows vs 20 reference rows...

=== Metrics Summary ===
Total rows: 20
Overall accuracy: 85.71%

Per-field metrics:
  studio:
    Precision: 93.75%
    Recall: 93.75%
    F1: 93.75%
    Correct: 15/20
  performers:
    Precision: 100.00%
    Recall: 100.00%
    F1: 100.00%
    Correct: 13/20
  title:
    Precision: 100.00%
    Recall: 71.43%
    F1: 83.33%
    Correct: 5/20

Sample mismatches (showing up to 10):
  studio: LatinLeche - I Can Dry Your Shirt (Brunito Qu...
    Expected: Latin Leche
    Parsed: LatinLeche

Writing Excel output to metrics/reference-20251211-150322.xlsx...
Writing JSON metrics to metrics/reference-20251211-150322.json...

✓ Evaluation complete!
```

## Usage Examples

### Example 1: Quick Blind Mode Check

```bash
# Process first 50 files, dry run
python tools/evaluate.py \
  --input /path/to/filenames.txt \
  --limit 50 \
  --no-write
```

**Output**: Console summary only, no files written.

### Example 2: Full Dataset Evaluation

```bash
# Process all files, save outputs
python tools/evaluate.py \
  --input /path/to/large-dataset.txt \
  --output-excel reports/full-evaluation.xlsx \
  --output-json reports/full-evaluation.json
```

**Output**:
- `reports/full-evaluation.xlsx` (single sheet)
- `reports/full-evaluation.json` (coverage metrics)

### Example 3: Reference Mode Comparison

```bash
# Compare against reference labels
python tools/evaluate.py \
  --mode reference \
  --input /path/to/reference-data.xlsx \
  --samples 20
```

**Output**:
- `metrics/reference-YYYYMMDD-HHMMSS.xlsx` (three sheets)
- `metrics/reference-YYYYMMDD-HHMMSS.json` (precision/recall metrics)
- Console output shows up to 20 sample mismatches

### Example 4: CI Integration

```bash
# Fast CI run without Excel
python tools/evaluate.py \
  --input test-fixtures/sample.txt \
  --limit 100 \
  --skip-excel \
  --output-json metrics/ci-run.json
```

**Output**: JSON metrics only for CI threshold checks.

## Field Extraction Rules

### Title
- Extracted from leftover unlabeled tokens after all other extraction
- Must contain at least one meaningful word (2+ letter alphabetic sequences)
- Trailing numbers extracted as sequence `{"title": N}` if present

### Sequence
Multiple sequence indicators can be present, stored in a single dict:

- **Part**: `pt. N`, `pt N`, `pN`, `p.N`, `part N`, `partN`, `part.N`, `part-N`
- **Scene**: `scene N`, `sc N`, `s N` (exception: `sc-NNNN` = Sean Cody studio code)
- **Episode**: `episode N`, `ep N`, `e N`
- **Volume**: `vol N`, `v N` (can be in filename OR parent directory)
- **Title number**: Loose number at end of title

**Example**:
```
Input: "Hot Scenes - Part 2 - Episode 5.mp4"
Sequence: {"part": 2, "episode": 5}
```

### Group
- Immediate parent directory name from path
- Extracted during sequence extraction phase

**Example**:
```
Input: "/videos/BelAmi Collection/Kinky Angels - Scene 3.mp4"
Group: "BelAmi Collection"
```

## Architecture Notes

### Parser Pipeline Integration

The evaluation harness uses the full parser pipeline:

1. Pre-tokenization (remove quality markers, extensions)
2. Tokenization (extract tokens and patterns)
3. Date extraction
4. Studio matching
5. Studio code finding
6. Performer matching
7. **Sequence extraction** (part/scene/episode/volume/group)
8. **Title extraction** (from remaining unlabeled tokens)

All extraction logic lives in parser modules (`modules/sequence_extractor.py`, `modules/title_extractor.py`). The evaluator simply reads the results.

### Metrics Calculation

**Blind Mode**: `coverage = rows_with_field / total_rows`

**Reference Mode**:
- `precision = correct / parsed_non_null`
- `recall = correct / reference_non_null`
- `f1 = 2 * (precision * recall) / (precision + recall)`

## Troubleshooting

### Common Issues

**Issue**: `FileNotFoundError: No such file or directory`
```bash
# Solution: Use absolute path or ensure file exists
python tools/evaluate.py --input /absolute/path/to/file.txt
```

**Issue**: `ValueError: Reference file headers don't match schema`
```bash
# Solution: Ensure reference Excel has exact 16-column schema
# Check column order matches: input, removed, path, filename_cleaned, ...
```

**Issue**: `ImportError: No module named 'openpyxl'`
```bash
# Solution: Install required package
pip install openpyxl
```

### Debug Tips

1. **Use `--no-write` for quick tests** without generating files
2. **Use `--limit 10`** to process small samples for debugging
3. **Check console output** for parsing progress and errors
4. **Examine JSON output** for detailed field-level metrics

## Performance

- **Typical Speed**: ~100-500 files/second (depends on filename complexity)
- **Memory Usage**: ~1-2 MB per 1000 files processed
- **Large Datasets**: Use `--skip-excel` for faster JSON-only output

## Future Enhancements

- [ ] Baseline comparison and threshold checks
- [ ] CSV/Markdown summary output for PR comments
- [ ] Pytest integration for automated testing
- [ ] CI/CD pipeline integration examples
- [ ] Schema validation before Excel write
- [ ] Parallel processing for large datasets

## Related Files

- [plans/stage-1-evaluation-harness.md](plans/stage-1-evaluation-harness.md) - Implementation plan and decisions
- [yansa.py](yansa.py) - Main parser with pipeline
- [modules/sequence_extractor.py](modules/sequence_extractor.py) - Sequence and group extraction
- [modules/title_extractor.py](modules/title_extractor.py) - Title extraction

## Support

For issues or questions:
- Check [plans/stage-1-evaluation-harness.md](plans/stage-1-evaluation-harness.md) for implementation details
- Review console output for specific error messages
- Examine JSON metrics for detailed diagnostics
