# RAW-CAT-01E.03B.02 — Adobe XMP uncovered-property audit

Date 2026-10-11. D-015 RAW-first, isolated pre-G0 research. NOT permission to train.

## Verified evidence from 01E.03B.01

44/44 focused Windows tests passed (the existing suite including 01E.04A and 01E.03B.01). A separately Adobe-written XMP file agreed on 48 scalar/point-curve property representations compared against ONE catalog sample, with 0 mismatches; one absent ConvertToGrayscale property was not interpreted as false/zero. Family breakdown: 14 basic/other, 13 HSL, 9 color grading, 4 legacy split toning, 4 point curves and 4 profile/context. The XMP exposes 76 other GLOBAL Adobe Camera Raw properties not included in the comparison. A companion ACR file exists but is not interpreted.

## New 01E.03B.02 tool

Module: backend/app/photographer/lightroom_adobe_xmp_coverage.py
Tests: backend/tests/test_lightroom_adobe_xmp_coverage.py

Runs with the local PRIVATE 01E.03A plan and independent Adobe XMP. No RAW read or image decoding. Reads only global Camera Raw property keys and shallow representation shape. Output includes key names (not values), grouped by a LEXICAL family hint for triage; labels do not prove feature semantics, mask effects or Lightroom pixel parity. Nonstandard key names are counted but not emitted. Never commit RAW, .acr, Adobe XMP or private manifests.

From backend, Lightroom closed, use:
    python -m pytest -q tests/test_lightroom_adobe_xmp_coverage.py
    python -m app.photographer.lightroom_adobe_xmp_coverage --local-plan "LOCAL_PRIVATE_PLAN.json" --xmp "ADOBE_REFERENCE.xmp" --report "AGGREGATE_REPORT_OUTSIDE_RAW_FOLDER.json"

Share ONLY the aggregate JSON. No private image IDs, file stems, paths or pixel data in output. Windows tests and actual Adobe XMP coverage run remain PENDING.

## Interpretation and next gate

A matched property or curve coordinate proves agreement on that recorded property for this single sample, NOT Lightroom tone interpolation, Adobe Color/Look behavior, nested masks/retouch or .acr, and not final edit provenance. Requires representative approved RAW from more than one event and explicit gate approval before Brain training.

## V2 taxonomy correction (2026-10-11)

The original real v1 audit passed in the 46/46 Windows suite and found 76 extra properties: 71 scalar text, 3 shallow sequences, 2 nested/ambiguous. Original categories are ONLY lexical hints and showed misleading overlaps (LuminanceAdjustment was counted as Detail/Noise; HSL and RGB Calibration conflated; parametric curves and PointColors left in generic other). Version 2 explicitly prioritizes HSL prefixes, noise-reduction prefixes, calibration channel fields, parametric tone curves, opaque PointColors and mask payloads, profile/Look, optics, process metadata. Schema is now `prographer.adobe_xmp_coverage_audit.v2` to avoid silently changing interpretation of v1 reports. Two new synthetic regressions added; Windows execution of V2 is PENDING. No new decoding, pixel parity or AI training claim.
