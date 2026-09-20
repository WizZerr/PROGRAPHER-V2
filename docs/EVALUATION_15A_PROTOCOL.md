# Phase 15A — Measurement Protocol Defined During Phase 0

This document defines the measurement structure early, as required by Phase 0. It does not claim that model quality has been tested.

## Comparisons
When valid data exists, compare on compatible material:
1. Photographer's normal workflow (real baseline, including presets/sync/tools already used).
2. Simple baseline.
3. Reproducible V1 where available.
4. Candidate V2.

## Data separation
- Split by events / source groups, not random images from the same event.
- Validation is used for model/threshold choices.
- Locked Test is reserved for final evaluation; if repeatedly used for decisions it becomes development data and a new Test set is required.

## Numerical measures
For Exposure / Temperature / Tint:
- MAE
- Median error
- P90
- P95
- Results by camera / lighting group where sample size permits

## Human/workflow measures
- Accepted without manual correction
- Corrected
- Serious failure
- Consistency issues
- Active working time
- Total elapsed time reported separately
- Review/transition overhead

## Two distinct product success measures
1. Automation coverage: percentage of selected photos accepted without manual edit correction.
2. Active-time reduction: reduction in the photographer's real active workflow time.

Do not merge these into one number.

## Visual truth
- Quality decisions must be made on a trustworthy Lightroom result / reference path, not only on an approximate local preview.
- The model name should be hidden from the photographer during comparative evaluation where practical.

## Promotion rule structure
A candidate may be promoted only after:
- Passing data-integrity checks.
- Passing compatibility/contract checks.
- Being evaluated on the predeclared Validation protocol.
- Showing no unacceptable serious regressions in weak groups.
- Meeting promotion thresholds that are locked before the comparison is used for a promotion decision.

## Threshold status
Specific numeric promotion thresholds are NOT defined by the supplied master plan. They must be frozen before the first candidate-selection experiment using professional target material; they must not be invented after seeing candidate results.
