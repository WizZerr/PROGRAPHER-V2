# PG-04.03 — Encoded JPEG Export Implementation Report

Date: 2026-10-04  
Status: **V**

## Implemented

- `backend/app/rendering/jpeg_export.py`
- `backend/app/api/routes/jpeg_export.py`
- `backend/tests/test_jpeg_export.py`
- `docs/PG_04_03_JPEG_EXPORT_CONTRACT.md`

## Contract

Export is derived from:

`tracked original JPEG -> PG-03 sRGB/orientation normalization -> shared PG-04.01 EditRecipe -> optional post-render downscale -> JPEG encode`

It does not encode a preview/cache artifact or an already-edited JPEG copy.

The contract includes:

- quality 1–100, default 95,
- optional max-edge downscale without upscaling,
- fixed 4:4:4 chroma sampling,
- sRGB ICC embed/omit policy,
- EXIF preserve/strip policy,
- physically normalized orientation,
- metadata dimension rewrite,
- GPS explicit opt-in with no invented GPS,
- current-revision requirement,
- encoded-output reopen and measurement before return.

## Manual delta verification

Hosted GitHub Actions was not triggered because the monthly hosted-runner quota is exhausted.

The committed PG-04.03 behavior was verified locally against the current PG-04 rendering delta.

PASS:

- JPEG output reopens as JPEG/RGB,
- EXIF orientation 6 source exports as physically upright pixels with Orientation=1,
- full-size recipe render precedes optional resize,
- sRGB ICC embed policy,
- ICC omit policy,
- EXIF preserve policy,
- EXIF strip policy,
- GPS stripped by default,
- GPS preserved only when explicitly requested and present,
- requesting GPS on a source without GPS does not invent/fail,
- stale revision export is rejected,
- stale export API returns HTTP 409,
- original source bytes remain unchanged,
- new export/render modules compile/import in the local delta harness.

The immediate inherited baseline already had the PG-04.01 backend regression/compile evidence in run `37176350329`, and PG-04.02 was delta-verified before this Part.

This is technical export verification, not photographer-quality evidence.

## Result

PG-04.03 is **V**.

Next executable Part: **PG-04.04 — safe atomic filesystem export**.
