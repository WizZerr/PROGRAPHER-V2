# ProGrapher V2 — Phase 9 Part 1 — Baseline + Candidate Registry

## Purpose

Phase 9 must preserve a reproducible reference before any new Brain work is
allowed to replace it.

This Part establishes the comparison contract without pretending that a
working legacy profile exists.

## Added

- `baseline.train_median.v1`
  - fitted only from verified `train` samples;
  - predicts constant median Exposure / Temperature / Tint;
  - intentionally simple, so later models must beat something explicit.
- common candidate registry:
  - Baseline,
  - reconstructed V1,
  - future V2 candidate.
- reconstructed V1 is explicitly different from the original user profile.
- model-affecting changes are typed as:
  - baseline,
  - correctness_fix,
  - model_experiment.
- default model promotion requires a passed quality gate.
- promotion always records a rollback candidate.
- common MAE comparison contract rejects split leakage.
- bounded Legacy inventory tool:
  - searches only the LEGACY folder supplied by the user;
  - hashes relevant source/model artifacts;
  - detects CLIP / ExtraTrees evidence;
  - reports `incomplete` instead of inventing missing weights.

## What is NOT claimed

- We do not yet claim V1 has been reconstructed.
- We do not claim the original trained user profile exists.
- We do not promote any model.
- V2 does not exist yet.

The next Phase 9 step is to run the inventory against the real `LEGACY`
folder and inspect exactly what V1 code/artifacts are actually available.
