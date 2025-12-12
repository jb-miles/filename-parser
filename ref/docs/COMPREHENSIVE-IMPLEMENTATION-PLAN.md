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
