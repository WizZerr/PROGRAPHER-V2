# ProGrapher V2 — Phase 11 Part 4C

Builds a neutral same-dataset comparison harness for:

- measured RAW / EXIF / WB / region features
- CLIP
- DINOv3

Every candidate must use the exact same photo IDs, event-safe split,
predictor settings and targets.

Targets:
- Exposure EV
- Temperature K
- Tint

Metrics per target:
- MAE
- Median AE
- P90 AE
- P95 AE

The harness rejects:
- missing/extra candidate samples
- event leakage between train/validation
- test split usage
- NaN/Inf values
- duplicate candidate IDs

The controlled downstream predictor is
`extratrees-independent-targets-v1`.

One independent ExtraTrees regressor is trained per target so the much larger
numeric scale of Temperature cannot dominate Exposure/Tint tree decisions.

A train-median baseline is also reported.

No aggregate winner or automatic promotion is produced.

Next: Part 4D adapts ProGrapher Dataset V2 into the NPZ contract and batch
extracts Measured + CLIP. DINOv3 can be added later without redesign.
