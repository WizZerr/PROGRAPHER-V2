# Phase 12 Part 1H — Candidate Experiment Contract

## Purpose

Create one reproducible experiment contract for the candidate comparisons that
will run when representative Dataset V2 material arrives.

This Part records experiment identity only. It does not train a model and does
not fabricate predictions.

## Candidate families

The contract supports:

- `simple_baseline`
- `measured_features`
- `clip`
- `dino`
- `brain`

The family label is descriptive, not a ranking.

## Experiment identity

Each `experiment_id` is deterministically bound to:

- candidate name and family
- dataset_id
- split_id
- target contract version
- exact target names
- white-balance target representation
- representation name/version/model ID/feature version
- estimator name and configuration
- random seed
- code revision
- train cohort fingerprint
- validation cohort fingerprint

Changing any of those inputs changes the experiment identity.

## White balance representation

The experiment contract records whether the run uses:

- `absolute_kelvin`
- `delta_from_as_shot`

This prevents results produced under different WB target representations from
being mixed silently.

The contract does not choose which representation is better.

## Cohort fingerprints

The train and validation sample IDs are hashed separately.

The contract verifies:

- non-empty train cohort
- non-empty validation cohort
- no sample leakage
- every referenced sample exists and is training-ready in the Dataset manifest

## Code revision

`code_revision` is required and explicit.

Recommended value when real experiments begin:

`git:<commit-sha>`

This makes a result traceable to the exact implementation used.

## How this connects to the existing Phase 12 pipeline

```text
Dataset Readiness
      ↓
Dataset Manifest
      ↓
Event-Safe Split
      ↓
Candidate Experiment Spec
      ↓
Candidate training / prediction   [blocked until representative data]
      ↓
Evaluation Harness
      ↓
Lightroom visual review
```

## Still blocked

- real candidate training
- measured / CLIP / DINO quality comparison
- WB representation selection
- camera / lighting failure analysis
- production Brain promotion
