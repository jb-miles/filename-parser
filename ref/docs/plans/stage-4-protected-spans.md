# Stage 4 Plan: Protected Spans & Rejoin Logic

**Status**: 🚧 Not Started  
**Goal**: Preserve known entities during splitting and rejoin accidental splits.  
**Deliverable**: Span marking + rejoin heuristics with tests covering studios, codes, dates, and fragile names.

## Tasks
- [ ] Protected spans pre-pass for studios, codes, dates, domains/URLs/emails; store labeled spans.
- [ ] Rejoin heuristics: studio pairs (`Sean`+`Cody`), code fragments (`SC`+`1234`), prefixes (`Mc`/`O'`), hyphenated names.
- [ ] Tests for preserved spans (studios, codes, dates, accented names) and rejoin cases (e.g., `AT & T` → `AT&T` when protected).
