# Phase 12 Part 1F — Evaluation Harness

## Purpose

Prepare the P12-04 comparison machinery before representative Dataset V2
material arrives.

This Part does not train a model and does not fabricate quality results.

## Fair-comparison contract

Every candidate must be evaluated on exactly the same validation sample IDs
from the Part 1E event-safe split.

The evaluator rejects:
- missing validation predictions
- extra predictions
- duplicate sample IDs
- Dataset / split identity mismatches
- non-finite prediction values

This prevents one candidate from receiving an easier validation subset.

## Metrics

Metrics are calculated separately for:
- Exposure, in stops
- Temperature, in Kelvin
- Tint, in Lightroom Tint units

For each target:
- MAE
- Median Absolute Error
- P90 Absolute Error
- P95 Absolute Error

Percentiles use deterministic linear interpolation.

The three targets are not collapsed into one aggregate score because their
units are different.

## Baseline comparison

A candidate may be compared against a supplied baseline on the same Dataset and
same split.

For each target, the report records:
- baseline MAE
- candidate MAE
- absolute MAE improvement
- percent MAE improvement when baseline MAE is non-zero

The harness does not decide that a candidate is a production winner.

## Candidate names

The implementation is intentionally generic.

When real Dataset V2 material arrives, candidate prediction files can represent:
- simple baseline
- measured features
- CLIP
- DINO
- later Brain variants

Legacy Brain V1 is not required by this harness.

## Reproducibility

Each candidate evaluation receives a deterministic `evaluation_id` bound to:
- candidate name
- dataset_id
- split_id
- metric version
- exact prediction values

## Still blocked by real data

- actual quality comparison
- WB representation selection
- camera / lighting failure analysis
- Lightroom visual review
- Base Editor promotion
