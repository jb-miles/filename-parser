# Stage 2 Plan: Dictionary Expansion

**Status**: 🚧 Not Started  
**Goal**: Expand studio and junk dictionaries plus studio-code patterns to lift baseline coverage.  
**Deliverable**: Updated dictionaries with validation schemas and a validation script; CI check blocking invalid entries.

## Tasks
- Studios:
  - [ ] Add missing bracket labels (Prollboy, Latin Prod, Latino Twink, Black XXL, Black Rebel, Military prod, Galago, FamilyCreep, Bearback).
  - [ ] Add domain-normalized aliases (e.g., `crunchboy.com` → `Crunchboy`) and punctuation variants.
  - [ ] Add studio alias mapping file for normalization rules.
- Junk tokens:
  - [ ] Add resolution/quality/bitrate encodings (`1080p`, `720p`, `4k`, `h264`, `hevc`, `x265`, `dvdrip`, `webrip`, `web-dl`, etc.).
  - [ ] Add collection boilerplate (`MOVIES PACK`, `Individual Scenes`, `Collection`, `Bundle`) and non-studio brackets (e.g., `[720p]`).
- Studio codes:
  - [ ] Inventory alphanumeric patterns (4–10 chars with hyphens/numbers); hand-classify 100 samples.
  - [ ] Add validated patterns (e.g., `ACM####-####`, `SC####-####`, `MK#######`, `[A-Z]{2,4}[-\\s]?\\d{3,5}`) with suffix tolerance.
- Validation:
  - [ ] JSON schemas for `parser-dictionary.json` and `studios.json`.
  - [ ] Add `tools/validate_dictionaries.py` and wire to CI on dictionary changes.
