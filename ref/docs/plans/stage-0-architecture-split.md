# Stage 0 Plan: Parallel Path + Filename Pipelines

**Status**: 🚧 Not Started  
**Goal**: Separate concerns by running a dedicated `PathParser` on directory segments and a `FilenameParser` on the basename, then merge with explicit conflict rules.  
**Deliverable**: Parser outputs include merged fields plus telemetry indicating source (`path` vs `filename`), with `filename_cleaned` free of parent directories and tests covering resolver behavior.

## Tasks
- [ ] Create `PathParser` that tokenizes/normalizes path segments independently (no mutation of basename tokens).
- [ ] Keep normalization utilities shared but isolate token streams to prevent path bleed into filename parsing.
- [ ] Implement resolver: filename wins on conflict; path backfills when filename is empty/low confidence; expose confidence scores.
- [ ] Emit source telemetry per field (e.g., `studio_source=path|filename`, `group_source=path`).
- [ ] Enforce path/basename separation in outputs: `filename_cleaned` excludes parent dirs; `group` only set via resolver rules (see [[stage-5-path-aware-extraction]] guardrails).
- [ ] Add unit tests for resolver precedence and telemetry emission.
