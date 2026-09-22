# Phase 11 Part 7D — Windows Evidence Consolidation

This document consolidates the Phase 11 evidence that can be closed or documented
on the current Windows workstation **without inventing Dataset V2 quality results**.

## P11-04 — feature representation comparison

**Status: BLOCKED**

The comparison infrastructure exists, but there is no representative Dataset V2
with final Lightroom targets and at least two event groups for event-safe
train/validation. Therefore ProGrapher does **not** declare a quality winner among:

- measured features
- CLIP
- DINO

No synthetic quality result is substituted for the missing dataset.

## P11-05 — contribution, resources, licensing

**Status: PARTIAL**

Evidence now available:

- model/license inventory
- detector extraction timing
- process-tree RAM evidence
- NVIDIA total-used memory delta evidence
- reviewed Windows detector controls

The remaining quality item is **feature-group contribution / ablation**. That is
blocked by the same missing representative Dataset V2.

Reviewed Part 7B resource observations:

- CPU steady median: **1.7166 s**
- CUDA steady median: **1.2964 s**
- CPU peak process-tree RSS: **2378.8 MB**
- CUDA peak process-tree RSS: **2906.4 MB**
- max NVIDIA total-used memory delta: **747.0 MB**
- controls correct on CPU: **yes**
- controls correct on CUDA: **yes**

These are engineering measurements, not a 2,000-photo production-throughput claim.
The NVIDIA number is system-total used-memory delta, not per-process VRAM.

## P11-06 — reference computers / device consistency

**Windows CPU↔CUDA evidence: PASSED**

The 42-RAW deterministic engineering sample produced:

- samples: **42**
- consistent: **42**
- mismatched: **0**
- errors: **0**
- overall pass: **True**
- CPU median detector time: **1.3652 s**
- CUDA median detector time: **1.1837 s**

The sample included RAWs with zero detections and RAWs with multiple faces /
subjects. CPU and CUDA remained within the fixed comparison tolerances.

**Global P11-06 is still open** because:

- real macOS / Apple Silicon / MPS has not been tested;
- broader representative product fixtures remain a separate requirement.

## Detector candidate state

- YuNet face: basic Windows negative/positive gate passed.
- RT-DETR person: basic Windows negative/positive gate passed.
- PP-HumanSeg: rejected for promotion after a sculpture false positive.
- Skin: intentionally unavailable; no naive skin-color heuristic is promoted.

## Source reports

- `docs/runtime/phase11_model_license_inventory.json`
- `docs/runtime/phase11_detector_resource_benchmark.json`
- `docs/runtime/phase11_multi_raw_detector_consistency_42.json`
- `docs/runtime/phase11_windows_evidence_summary.json`

## Guardrails

This Part 7D does **not**:

- change production inference;
- promote a detector into the default production pipeline;
- fabricate Dataset V2 quality metrics;
- close macOS/MPS;
- declare universal wedding/event detector accuracy;
- declare FiveK to be a representative ProGrapher training dataset.

