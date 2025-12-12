# Stage 6 Plan: Studio Matching Enhancement

**Status**: 🚧 Not Started  
**Goal**: Raise studio coverage to >85% with aggressive normalization, aliases, and confidence scoring.  
**Deliverable**: Studio matcher using expanded dictionary/aliases, normalized matching, confidence output, and tests for bracket/domain cases.

## Tasks
- [ ] Normalize studios and candidates (lowercase, strip punctuation, collapse whitespace, drop `.com/.net` suffixes, remove production suffixes).
- [ ] Prioritize bracket labels; ignore obvious non-studio brackets via junk list.
- [ ] Implement alias mapping (canonical + aliases + domain).
- [ ] Add confidence scoring tiers (bracket > exact > normalized > path-derived).
- [ ] Tests: bracket extraction, normalization (`Latin_Prod`), domain stripping (`crunchboy.com`), non-studio brackets ignored.
