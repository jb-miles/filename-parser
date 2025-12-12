# Stage 7 Plan: Performer Detection Enhancement

**Status**: 🚧 Not Started  
**Goal**: Increase performer coverage to >60% with better list splitting and name pattern detection while avoiding title bleed.  
**Deliverable**: Performer extractor that handles mixed separators, initials, hyphens, and gating so weak signals do not override titles; validated by unit tests.

## Tasks
- [ ] Split on commas/ampersands/“and”/slashes (with no-space variants).
- [ ] Support apostrophes, hyphens, initials, and leading digits in names.
- [ ] Mixed token splitting: separate title vs names when glued; use capitalization patterns.
- [ ] Soft-signal gating: require sufficient capitalized-word evidence; avoid promoting path boilerplate to performers.
- [ ] Multi-pass detection on filename and terminal path segment with deduping.
- [ ] Tests: ampersand split, initials, leading-number names, mixed separators, apostrophe preservation; confirm gating prevents false positives from weak signals.
