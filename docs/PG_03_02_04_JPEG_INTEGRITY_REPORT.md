# PG-03.02–PG-03.04 — JPEG Integrity Engineering Report

Date: 2026-10-04  
Branch: `cursor/testing-ready-77c3`  
Evidence HEAD at backend validation: `68b906e7d5188ffe3093789e8a92817f5138ee29`  
GitHub Actions run: `37171832248`

## Result

**PG-03.02 — V**  
**PG-03.03 — V**  
**PG-03.04 — V**

The relevant Windows backend regression step completed successfully on the evidence HEAD.

This is engineering/data-integrity evidence. It is not photographer-quality evidence and does not pass G1 by itself.

## PG-03.02 — Geometry / orientation

Implemented in `backend/app/datasets/jpeg_integrity.py` and wired into real JPEG intake.

The intake now:

- normalizes EXIF display orientation before geometry analysis,
- uses ORB feature matching + RANSAC homography,
- requires a conservative geometry consensus,
- checks aligned edge similarity,
- detects/blocks:
  - crop with changed aspect ratio,
  - crop that keeps the same aspect ratio,
  - residual rotation,
  - mirror/flip,
  - wrong-copy or geometry that cannot be verified,
- allows only verified same-geometry or resize-only cases into first-pass recipe fitting.

Policy is conservative: uncertain pairs are excluded rather than stretched or guessed.

Automated regression covers same dimensions, resize, rotation, mirror, crop and unrelated/wrong-copy input.

## PG-03.03 — JPEG color / ICC / EXIF contract

Added Pillow/ImageCms to the locked backend dependencies and introduced one color-managed JPEG decoder.

Working-space contract:

`sRGB IEC 61966-2.1 — prographer working contract v1`

Behavior:

- embedded ICC is converted to sRGB,
- EXIF orientation is normalized before ICC conversion,
- RGB/L JPEG without ICC is explicitly recorded as an sRGB assumption,
- non-RGB JPEG without ICC is rejected rather than silently guessed,
- ICC fingerprint/evidence is written into intake records,
- J0 uses the same color-managed decoder,
- J1 real candidate and locked Test inherit that decoder through the shared J0 read path.

Automated regression covers:

- EXIF orientation normalization,
- valid embedded sRGB ICC,
- explicit missing-ICC assumption,
- sRGB ICC vs untagged sRGB convergence into the same working-space contract,
- rejection of CMYK/no-ICC input.

No Adobe/Lightroom color equivalence is claimed.

## PG-03.04 — Frozen bytes / dataset snapshot

Real JPEG intake now writes:

`dataset_snapshot.json`

For each Original/Edited file the snapshot records:

- role,
- pair ID,
- current locator,
- size,
- mtime evidence,
- full SHA-256.

The snapshot identity is content-derived and does not use the filesystem path as dataset identity.

Snapshot validation is mandatory before:

1. J0,
2. J1 feature extraction/training,
3. locked Test audit.

If a file disappears or its bytes change, processing stops.

Automated regression proves:

- a valid intake snapshot re-validates,
- mutation after Intake is rejected,
- a deliberate new Intake after mutation creates a different snapshot ID.

Therefore changed bytes cannot silently continue under the previous dataset snapshot identity.

## Main files

- `backend/app/datasets/jpeg_integrity.py`
- `backend/training_lab/jpeg_real_dataset_intake.py`
- `backend/training_lab/jpeg_j0_feasibility.py`
- `backend/training_lab/jpeg_real_j0_batch.py`
- `backend/training_lab/jpeg_real_j1_candidate.py`
- `backend/training_lab/jpeg_real_j1_test_audit.py`
- `backend/tests/test_jpeg_integrity.py`
- `backend/training_lab/JPEG_REAL_DATASET_INTAKE_README_HE.md`

## Remaining G1 work

These three Parts do not finish the whole data gate.

Still relevant next:

- PG-03.05 — approved unchanged-final identity cases,
- PG-03.06 — source groups / near-duplicate split protection,
- PG-03.07 — coverage report,
- PG-03.08 — Candidate/target provenance versioning,
- PG-03.09 — combined corruption/leakage regression fixtures,
- real photographer material and its provenance/consent when available.
