# Comprehensive Implementation Plan: Maximum Efficiency Roadmap

## Current State Snapshot
- **Studio Coverage**: 47.2% (2,347/4,977 rows)
- **Performer Coverage**: 13.3% (661/4,977 rows)
- **Date Coverage**: 1.0% (48/4,977 rows)
- **Studio Code Coverage**: 0% (0/4,977 rows)
- **Missing Fields**: title, series, volume, part, scene

## Target State
- **High Coverage**: >85% for studio, >60% for performers, >15% for dates, >20% for studio codes
- **New Fields**: Structured extraction for title, series, volume, part, scene
- **Path Intelligence**: Directory structure metadata promoted to structured fields
- **Quality Assurance**: Evaluation harness preventing regressions
## Workflow
- [ ] Before starting each stage, validate that the stage plan still fits current project needs; adjust scope or tasks if misaligned.
- [ ] At the start of each stage iteration, run the unit test suite and evaluate the parser in reference mode to capture a baseline snapshot (save metrics artifacts).
- [ ] After any module change, rerun the evaluation harness in reference mode, log precision/recall deltas per field, and note regressions or improvements.
- [ ] Document extraction coverage changes against the baseline with concrete examples.
- [ ] Write or update comprehensive user-facing and developer documentation describing the behavior change, rationale, and example inputs/outputs.
- [ ] Review token pattern distributions to uncover new edge cases or anomalies and queue follow-up fixes if needed.
- [ ] Run end-to-end integration tests across the full pipeline to confirm downstream extractors remain stable.
- [ ] Commit metrics artifacts (JSON/Excel outputs) and notes alongside the code to preserve history and ease stage retrospectives.
- [ ] At the end of each stage, verify the learned results remain accurate (no loss of previously correct matches) and that the stage-specific deliverables are fully achieved.


## Stage Checklist (links to detailed plans)
- [ ] Stage 0: Parallel Path + Filename Pipelines [[stage-0-architecture-split]]
- [ ] Stage 1: Evaluation Harness & Metrics Infrastructure [[stage-1-evaluation-harness]]
- [ ] Stage 2: Dictionary Expansion [[stage-2-dictionary-expansion]]
- [ ] Stage 3: Core Tokenization & Normalization Upgrade [[stage-3-tokenization-normalization]]
- [ ] Stage 4: Protected Spans & Rejoin Logic [[stage-4-protected-spans]]
- [ ] Stage 5: Path-Aware Extraction System [[stage-5-path-aware-extraction]]
- [ ] Stage 6: Studio Matching Enhancement [[stage-6-studio-matching]]
- [ ] Stage 7: Performer Detection Enhancement [[stage-7-performer-detection]]
- [ ] Stage 8: Numbered Fields (Volume/Part/Scene) [[stage-8-numbered-fields]]
- [ ] Stage 9: Date & Studio Code Extraction [[stage-9-date-and-code-extraction]]
- [ ] Stage 10: Title/Series Resolution & Final Integration [[stage-10-title-series-integration]]
