# PG-04.06 — JPEG UI Control Mapping Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Backend added

- `backend/app/rendering/jpeg_controls.py`
- `backend/app/api/routes/jpeg_controls.py`
- `backend/tests/test_jpeg_controls.py`

## Current contract

JPEG controls are normalized, global controls:

- brightness,
- contrast,
- warmth,
- tint.

All are -100..100.

Temperature in Kelvin and Lightroom Tint equivalence are explicitly false in the contract.

## Darkroom wiring added

- JPEG is no longer presented as PR1 view-only.
- The JPEG panel exposes brightness, contrast, warmth and green↔magenta controls.
- JPEG values are normalized -100..100; Kelvin and Lightroom Tint wording is absent.
- The stage uses `JpegRenderedPreview`, which POSTs the controls to the real backend renderer.
- Preview requests are debounced.
- A monotonically increasing revision is assigned to each request.
- A request-id guard prevents an older async response from replacing the newest UI state.
- Holding B shows the original source using the existing comparison behavior.
- RAW keeps its existing XMP/Kelvin flow unchanged.

## Remaining before V

Run targeted backend mapping/pixel tests plus frontend static/type verification of the committed Darkroom delta.
