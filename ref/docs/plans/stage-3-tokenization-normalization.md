# Stage 3 Plan: Core Tokenization & Normalization Upgrade

**Status**: 🚧 Not Started  
**Goal**: Improve splitting/cleanup while preserving semantic units to feed downstream extractors.  
**Deliverable**: Tokenizer that normalizes delimiters/unicode, trims noise, and passes targeted unit tests without breaking protected spans.

## Tasks
- [ ] Delimiter normalization for commas/ampersands/slashes/underscores/dashes with context rules.
- [ ] Unicode cleanup (quotes, dashes, zero-width chars) and whitespace collapse; preserve apostrophes/hyphens inside words.
- [ ] Token trimming: strip leading indices; extract part/volume indicators; trim punctuation; collapse repeats; drop empties.
- [ ] Test mixed separators, glued names, dash-without-space titles, decimal preservation, and leading indices.
