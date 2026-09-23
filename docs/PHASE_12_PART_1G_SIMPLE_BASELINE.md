# Phase 12 Part 1G — Simple Baseline Prediction Harness

## Purpose

Create a reproducible, leakage-safe reference baseline for P12-04 before the
representative Dataset V2 arrives.

This is not a Brain and is not intended for production editing.

## Supported strategies

Two constant-target baselines are supported:

- `median`
- `mean`

Both are fitted from **train samples only**.

The default CLI strategy is `median`.

The validation targets are never consulted during baseline fitting.

## Why a simple constant baseline exists

A learned candidate should demonstrate that it adds useful predictive value over
a trivial reference that ignores image content.

The baseline predicts the same train-derived target values for every validation
sample.

This makes it intentionally simple and easy to reproduce.

## Targets

The baseline covers the same Phase 12 targets:

- Exposure
- Temperature
- Tint

No additional edit parameters are introduced.

## Output

The tool writes:

1. prediction JSON compatible with the Part 1F Evaluation Harness;
2. metadata containing:
   - baseline version
   - strategy
   - dataset_id
   - split_id
   - train sample count
   - fitted values
   - deterministic baseline_id

## Leakage guardrail

Only samples assigned to `train` may influence the fitted values.

Only samples assigned to `validation` receive predictions.

Tests explicitly change extreme validation targets and verify that the fitted
baseline remains unchanged.

## Interpretation

A measured/CLIP/DINO/Brain candidate may later be compared against this baseline
using exactly the same Part 1F validation cohort and metrics.

This harness does not declare a quality winner and does not replace Lightroom
visual evaluation.
