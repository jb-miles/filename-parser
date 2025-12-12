# Stage 5 Plan: Path-Aware Extraction System

**Status**: 🚧 Not Started  
**Goal**: Extract metadata from directory structure with guardrails, merging with filename data via the resolver ([[stage-0-architecture-split]]).  
**Deliverable**: Path parser feeding studios/codes/series/part/volume signals into the resolver, with `filename_cleaned` untouched by path text and group promotion controlled by whitelists.

## Tasks
- Infrastructure:
  - [ ] Split full path into segments; normalize segments and store metadata (segment, normalized, index).
  - [ ] Run path parsing in dedicated pipeline; pass candidates + confidence to resolver (filename wins on conflict, see [[stage-0-architecture-split]]).
- Path studios and codes:
  - [ ] Match studios on segments (including domain normalization) with confidence scores.
  - [ ] Extract studio codes from segments; strip bitrate/resolution suffixes; prefer filename matches.
- Series/collection + group guardrails:
  - [ ] Identify recurring parent segments for series; maintain series alias file.
  - [ ] Promote group/collection only when pattern is whitelisted; do not promote generic set/volume labels (e.g., `Hard Brit Lads 7 of 7`, `TF Part 1`).
- Part/volume from path:
  - [ ] Detect `part|pt|p|disc|cd|tape` + number; detect `vol|volume|v` + number and `X of Y`.
  - [ ] Prefer path-derived numbers over ambiguous filename numbers.
- Conflict rules:
  - [ ] Studio: filename wins on conflict; path may backfill when filename empty/low confidence; log source.
  - [ ] Codes: never overwrite filename code with path code.
- Testing:
  - [ ] Cases: `crunchboy.com PART 1/filename.mp4` (studio=Crunchboy, part=1), `Hard Brit Lads 7 of 7/Scene 04.mp4` (series/group suppressed unless whitelisted; volume=7, scene=4), `TF Part 1 (Individual Scenes)/filename.mp4` (series/part=1).
