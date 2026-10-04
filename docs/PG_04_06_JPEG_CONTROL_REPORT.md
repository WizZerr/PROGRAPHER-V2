# PG-04.06 — JPEG UI Control Mapping Report

Date: 2026-10-04  
Status: **V**

## Implemented

Backend:

- `backend/app/rendering/jpeg_controls.py`
- `backend/app/api/routes/jpeg_controls.py`
- `backend/tests/test_jpeg_controls.py`

Frontend:

- `frontend/src/features/darkroom/jpegControls.api.ts`
- `frontend/src/features/darkroom/JpegRenderedPreview.tsx`
- JPEG branch of `DarkroomScreen.tsx`
- POST-capable blob helper in `frontend/src/lib/api.ts`

## Frozen UI semantics

JPEG controls are:

- brightness,
- contrast,
- warmth,
- green↔magenta tint.

All are normalized `-100..100`, neutral `0`.

JPEG warmth is explicitly not Kelvin. JPEG tint is explicitly not Lightroom/Camera Raw Tint.

RAW keeps the existing XMP/Kelvin/Tint contract.

## Verification

Manual control/pixel harness:

- neutral controls -> exact identity pixels,
- brightness +25 changes pixels,
- contrast +25 changes pixels,
- warmth +25 changes pixels,
- tint +25 changes pixels.

The committed source contract was also checked for:

- real `JpegRenderedPreview` usage in the JPEG Darkroom,
- removal of the old JPEG view-only message,
- no RAW temperature binding or Kelvin-valued control in the JPEG panel,
- RAW panel still retaining its Kelvin range and value,
- registered backend JPEG-control route,
- monotonic render revision,
- request-id freshness guard,
- immediate revocation/clearing of the prior preview when controls change.

An older async preview response cannot replace a newer control state.

Hosted Actions was not triggered because the monthly hosted-runner allowance remains exhausted.

## Result

PG-04.06 is **V**.

Next executable Part: **PG-04.07 — RAW/XMP safety and truth boundary**.
