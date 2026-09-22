# ProGrapher V2 — Phase 11 Part 4D — Dataset V2 → Comparison Bundle

## Why this part exists

Part 4C created a fair comparison harness. Part 4D connects it to the
documented Dataset V2 contract instead of inventing a second training schema.

The adapter reads the Dataset V2 sample fields:

- `sample_id`
- `source_path`
- `camera`
- `exif`
- `raw_info`
- `target_recipe.exposure`
- `target_recipe.temperature`
- `target_recipe.tint`
- `event_group`
- `capture_time`
- `split`

Additional manifest fields are preserved by the source manifest but are not
required by this extraction adapter.

## Test protection

The builder selects only `train` and `validation`.

`test` rows are counted and explicitly excluded before RAW decoding or
embedding extraction. They are not silently merged into validation.

Event leakage between train and validation is rejected.

## Missing target policy

A target is missing only when it is absent/null/non-numeric.

`0` is a real edit value and is preserved as 0.

The adapter never converts a missing target into zero.

## Extraction

Every selected sample is decoded from its real `source_path`.

For the same ordered sample IDs it builds:

- `dataset.npz`
- `features_measured.npz`
- `features_clip.npz`
- optionally `features_dinov3.npz`
- `bundle_report.json`

Measured features use the current versioned Brain V2 feature extractor.

CLIP and DINOv3 use the already-defined controlled encoder adapters.

## All-or-nothing rule

A comparison must not look better because one encoder silently skipped hard
photos.

If a selected RAW is missing, fails decoding, or fails embedding extraction,
the bundle build raises an error. A complete candidate matrix must contain
exactly the same sample IDs as the Dataset V2 comparison set.

## Source identity

For this offline experiment the builder SHA-256 hashes each selected RAW
before building its Brain input. This is intentionally slower than a
lightweight event fingerprint but avoids using filenames as source identity.

## Camera identity

Camera make/model is used only when Dataset V2 provides it.

The adapter never infers a camera model from the filename.

LibRaw/rawpy may still recover numeric camera-dependent information and RAW WB
through the existing preprocessing fallback.

## DINOv3

DINOv3 extraction is opt-in with `--include-dinov3`.

Until Hugging Face/Meta access is approved, build Measured + CLIP only. The
same Dataset NPZ can later be rebuilt with DINOv3 enabled; the comparison
contract does not change.

## Important

Part 4D creates real feature matrices. It still does not promote an encoder.

Actual metrics are produced by `phase11_compare_encoders.py`, using the same
predictor and validation samples for every candidate.
