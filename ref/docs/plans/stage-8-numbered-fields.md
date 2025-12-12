# Stage 8 Plan: Numbered Fields (Volume/Part/Scene)

**Status**: 🚧 Not Started  
**Goal**: Extract structured numeric metadata reliably from filenames and paths.  
**Deliverable**: Extractor covering scene/part/volume and trailing title numbers with clear precedence rules and tests.

## Tasks
- [ ] Scene: `scene|sc|s` + number; handle `Scene 04`, `Sc4`, `S-04`.
- [ ] Part: `part|pt|p|disc|cd|tape` + number (path and filename).
- [ ] Volume: `vol|volume|v` + number; `X of Y` → `{volume, total_volumes}`.
- [ ] Trailing numeric suffixes on titles (`Title.2`, `Title-2`) → `{sequence: {title: 2}}` instead of title text.
- [ ] Ambiguity handling: prioritize keyworded numbers over bare numbers; path numbers preferred over ambiguous filename numbers.
- [ ] Tests: scene/part/volume cases, `X of Y`, ambiguity with multiple numbers, path-preference case (`PART 1/05 Scene.mp4`).
