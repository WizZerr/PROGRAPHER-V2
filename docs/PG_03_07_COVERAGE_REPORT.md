# PG-03.07 — Dataset Coverage Report

Date: 2026-10-04  
Evidence HEAD: `613c6c1ac221a3abbf7abc69651fd6d63984f3c8`  
GitHub Actions run: `37173058568`

## Result

**PG-03.07 — V**

The Windows backend regression completed successfully on the evidence HEAD.

## What is generated

Real JPEG Intake now writes:

`coverage_report.json`

The report intentionally separates:

- original file count,
- edited file count,
- matched pair count,
- usable learning pair count,
- excluded pair count,
- unmatched/ambiguous material.

A large file count can therefore no longer masquerade as a large usable training set.

## Coverage dimensions

For usable pairs the report records aggregate and per-event coverage for:

- camera make/model,
- lighting bucket,
- edit scope,
- split,
- source groups.

### Camera

Camera metadata is read from EXIF when present.

Missing camera metadata is reported as UNKNOWN rather than silently inferred.

### Lighting

A coarse image-luminance bucket is computed:

- low_key
- mid_tone
- high_key
- mixed_contrast

This is an engineering coverage signal, not semantic scene understanding.

### Edit scope

A global affine RGB fit is used only as a coverage classifier.

Labels:

- `identity_like`
- `global_like`
- `local_or_complex_suspected`

`local_or_complex_suspected` deliberately combines local editing with complex/nonlinear global edits that a simple affine transform cannot explain. It is not presented as a retouch detector.

## Exclusions / hard groups

Every excluded matched pair remains visible by reason.

The report also contains `hard_groups` for Events with:

- exclusions,
- local/complex suspected edits.

This prevents difficult Events or difficult edit styles from disappearing inside aggregate averages.

## Regression evidence

Tests prove:

- EXIF camera make/model/ISO are preserved into coverage evidence,
- low-key lighting classification is recorded,
- a simple global edit is labeled global-like,
- a spatially local/complex edit is surfaced separately,
- file counts, matched pairs and usable pairs are reported separately,
- geometry-excluded pairs remain visible by reason,
- hard groups are present instead of being hidden.

This is dataset coverage evidence only. Real professional coverage depends on the photographer material that has not arrived yet.
