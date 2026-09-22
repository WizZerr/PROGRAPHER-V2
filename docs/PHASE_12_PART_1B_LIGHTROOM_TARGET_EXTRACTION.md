# Phase 12 Part 1B — Lightroom Target Extraction Bridge

## Purpose

Connect the Phase 12 target contract to Lightroom / Camera Raw XMP metadata
without training a model and without guessing missing rendering context.

## Extracted fields

The bridge reads the Camera Raw XMP namespace for:
- Exposure2012, with legacy Exposure fallback
- Temperature
- Tint
- ProcessVersion
- CameraProfile
- ToneCurveName2012, with legacy ToneCurveName fallback
- WhiteBalance

These values are converted into the Part 1A Phase12TargetSample.

## Missing learned targets

Exposure, Temperature, or Tint may be absent during ingestion.
They remain None and are exposed through missing_target_fields.
A sample is not ready for three-target training until all three are present.

## Rendering context

The extractor rejects a sample when Process Version, Camera Profile, Tone Curve
identity, or Preset identity is unknown.

Tone Curve identity may be supplied explicitly if the XMP does not contain a
named curve.

Preset identity is always explicit. The caller may pass `none` only when that is
actually known.

## White balance guardrail

Final XMP Temperature/Tint are never reused as As Shot values.

Trusted As-Shot values may be attached separately, and
wb_mapping_reliable=True remains guarded by the Part 1A contract.

## Still blocked

- no Dataset V2 quality comparison
- no measured/CLIP/DINO winner
- no training
- no Base Editor promotion
- no human Lightroom evaluation of predictions

## Production impact

None. This is a training/import bridge only and is not wired into production
inference.
