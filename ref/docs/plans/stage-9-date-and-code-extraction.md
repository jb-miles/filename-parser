# Stage 9 Plan: Date & Studio Code Extraction

**Status**: 🚧 Not Started  
**Goal**: Expand date formats and studio code detection/normalization to hit coverage targets.  
**Deliverable**: Date/code extractor handling compact formats and brand-prefixed codes, with tests and preference for filename sources.

## Tasks
- Dates:
  - [ ] Add `YYMMDD`, `DD-MM-YY`, dotted (`2023.01.15`), compact (`20230115`), and split patterns (year + day-of-year).
  - [ ] Path dates: month names/abbrevs (`Nov 2021`), year-only, month-year; store precision.
- Studio codes:
  - [ ] Apply expanded patterns from [[stage-2-dictionary-expansion]]; strip bitrate/resolution suffixes (`SC1234-1080p` → `SC1234`).
  - [ ] Normalize brand-prefixed codes to canonical digits when appropriate (`ACM3190` → `3190`, `SC-0161` → `161`, `8494_02` → `8494-02`) while retaining raw for traceability.
  - [ ] Handle spaces/hyphens (`SC 1234`, `SC-1234`, `SC1234`); prefer filename over path.
- Tests: compact/dotted dates, path month-year, codes with suffixes, brand-prefixed normalization, and filename-vs-path precedence.
