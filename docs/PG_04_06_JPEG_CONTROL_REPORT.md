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


## Interactive JPEG preview UX follow-up — 2026-10-05

Manual Windows testing confirmed that the optimized backend path became much
faster, but RAW still felt perceptually instant because its illustration is
local to the frontend.

JPEG now uses the same interaction principle without weakening render truth:

- the selected JPEG controls immediately drive a local illustration layer,
- the exact PG-04.02/PG-04.06 backend render continues in the background,
- while the backend is catching up, no blocking "processing preview" state is
  shown; the local illustration remains visible,
- once the exact render for the current control signature arrives, it replaces
  the illustration silently,
- an exact render for older controls is never shown over a newer local state,
- the comparison badge is `המחשה`, matching RAW and truthfully describing the
  immediate layer,
- the footer states that the immediate illustration is local while the precise
  render updates in the background.

This changes interaction latency only. The canonical recipe, revision guards,
renderer and export semantics remain unchanged.


## Interactive/render handoff correction — 2026-10-05

Windows manual testing exposed a visible one-second "settle": the local JPEG
illustration appeared immediately, then the authoritative backend PNG replaced
it with noticeably different brightness/color.

Root cause: the local layer used approximate CSS filters/overlays, while the
backend used the exact `jpeg-global-controls-v1` affine RGB recipe.

The local JPEG path now mirrors the exact backend formulas as an sRGB SVG
component-transfer matrix (per-channel slope + shared contrast bias). The
backend render remains active in the background for safety/provenance but is no
longer painted over the interactive preview. This removes the visual handoff
rather than hiding it with a spinner or delay.
