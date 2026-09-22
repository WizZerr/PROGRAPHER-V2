# Phase 11 Part 6D — class-aware person detector candidate

## Why this candidate exists

The PP-HumanSeg evaluation candidate produced false-positive human-subject
evidence on a real CR3 containing animal sculptures. It therefore remains an
evaluation candidate and is not promoted.

Part 6D adds a second subject candidate:
`PekingU/rtdetr_r50vd`.

Unlike the binary human-segmentation candidate, this path is an object
detector and only emits ProGrapher `subject` evidence for detections whose
model label is exactly `person`.

Face remains YuNet 2026may.
Skin remains explicitly unavailable.

The default Brain V2 pipeline is still NOT changed.

## Licensing / provenance

The Hugging Face model repository declares Apache-2.0.
The official RT-DETR repository is Apache-2.0.

The model is downloaded to `backend/vendor/huggingface/` for local evaluation
and that vendor directory is intentionally git-ignored.

## Validation gates

1. Negative control: the sculpture CR3 should produce zero person subjects.
2. Positive event RAW: a clear person/couple should produce sensible person
   boxes.
3. Full regression suite must remain green.
4. CPU/CUDA and later MPS behavior is measured separately.
