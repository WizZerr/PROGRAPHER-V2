# Phase 11 Part 7C — Multi-RAW CPU↔CUDA detector consistency

Purpose: extend P11-06 Windows evidence beyond the two control RAWs.

The tool:

- scans a supplied RAW folder recursively;
- chooses a deterministic spread of files instead of taking only the first N;
- can always include explicit control RAWs;
- decodes every selected RAW through the Phase 11 RAW preprocessor;
- runs the same YuNet + RT-DETR candidate on CPU and CUDA;
- compares per-kind states;
- compares face/person detection counts;
- greedily matches boxes and requires IoU >= 0.98;
- requires confidence difference <= 0.01;
- records every decode/runtime error instead of silently skipping a difficult RAW.

This is consistency evidence, not editing-quality evidence.

It does not close:
- P11-04, which remains blocked by a representative event-safe Dataset V2;
- P11-05 feature-group contribution, blocked by the same Dataset;
- macOS/MPS validation;
- the broader Phase 0 30–50 RAW formal fixture requirement.

No production inference path is changed.
