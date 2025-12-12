# Stage 10 Plan: Title/Series Resolution & Final Integration

**Status**: 🚧 Not Started  
**Goal**: Finalize title and series extraction, integrate all fields, and ensure metadata completeness.  
**Deliverable**: Title/series extractor that backfills from path series, applies confidence gating, and produces stable patterns with final verification tests.

## Tasks
- Title extraction:
  - [ ] Title = basename minus structured fields (studio, code, performers, date, numbered fields, junk).
  - [ ] Trim boilerplate suffixes (`movie`, `clip`, `video`); collapse whitespace.
  - [ ] Confidence gating so low-signal tokens (path boilerplate, resolutions) do not force a title when other fields already explain the string.
- Series resolution:
  - [ ] Priority: path-derived series ([[stage-5-path-aware-extraction]]), bracket series indicators, recurring parent patterns; maintain series dictionary/aliases.
  - [ ] Flag series vs studio conflicts for review.
- Pattern generation:
  - [ ] Update pattern generator to include new fields (`title`, `series`, `volume`, `part`, `scene`); include `{path}` where available.
  - [ ] Ensure every row has `{path}` and `{title}` (even minimal).
- Testing & validation:
  - [ ] Integration test with full pipeline on diverse sample; no regressions vs [[stage-1-evaluation-harness]] baseline.
  - [ ] Edge cases: minimal filename, maximal filename, ambiguous numbers, mixed languages.
  - [ ] Final evaluation harness run on full dataset; generate coverage report.
