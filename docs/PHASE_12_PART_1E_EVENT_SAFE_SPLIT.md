# Phase 12 Part 1E — Event-Safe Split Manifest

## Purpose

Create a deterministic train/validation split at **event level**, never at
individual-photo level.

This prevents leakage where photographs from the same event appear in both
training and validation.

## Input

Part 1D `DatasetImportManifest`.

Only samples with:

`ready_for_three_target_training = true`

receive a split assignment.

Incomplete or invalid samples remain outside model training/evaluation.

## Split rule

Usable `event_id` values are ranked deterministically by:

`SHA-256(seed + event_id)`

A validation-event count is calculated from the requested validation fraction
and clamped so both train and validation contain at least one event.

The default is:

- validation fraction: 0.20
- seed: `phase12-v1`

## Reproducibility

The saved split contains:

- source `dataset_id`
- `split_id`
- seed
- validation fraction
- complete train event list
- complete validation event list
- sample-level assignment derived from the event assignment

`split_id` is bound to the Dataset manifest identity.

The same Dataset + seed + fraction reproduces the same split.

## Leakage guardrail

No event may occur in both train and validation.

All ready samples belonging to the same event inherit exactly the same split.

## Important limitation

This Part does not create the final locked Phase 15 test set.

It establishes the Phase 12 train/validation discipline required for honest
experiments. The permanently locked test protocol belongs to the later
evaluation phase.

## Still not done

- no model training
- no Baseline/Brain quality comparison
- no WB representation winner
- no locked final test set
- no human Lightroom evaluation
