# PG-04.06 — JPEG UI Control Mapping Contract

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / DARKROOM WIRING PENDING**

## Purpose

PG-04.06 gives JPEG editing controls product semantics that are real, versioned and rendered by the same PG-04.01 engine used by preview/export.

It explicitly avoids reusing Lightroom/RAW units where JPEG pixels cannot support the same meaning.

## JPEG controls

Contract version: `jpeg-global-controls-v1`.

All controls use normalized UI units from `-100` to `+100`, neutral `0`.

- `brightness` — global encoded-RGB brightness gain.
- `contrast` — global contrast around encoded midpoint 0.5.
- `warmth` — relative red/blue channel balance; not Kelvin.
- `tint` — relative green vs magenta balance; not Lightroom Tint units.

There is no JPEG `temperature_kelvin` control and no claim that normalized JPEG tint equals Lightroom/Camera Raw Tint.

## Renderer mapping

The controls compile into the existing versioned quadratic RGB polynomial EditRecipe.

No second renderer exists.

Neutral controls compile exactly to the PG-04.01 identity recipe.

The current v1 mapping is intentionally global/affine inside the polynomial contract:

- brightness uses a multiplicative gain,
- contrast changes slope around midpoint 0.5,
- warmth adjusts opposing red/blue gains,
- tint adjusts green against red+blue.

Output clipping remains owned by the shared renderer.

## Product preview API

`POST /api/jpeg-controls/preview`

Input:

- event id,
- fingerprint,
- monotonically increasing revision,
- normalized control values.

The backend builds the canonical EditRecipe and calls the exact PG-04.02 product preview renderer.

This preserves revision/cache/stale guarantees.

## Acceptance

PG-04.06 may become V only when:

- neutral JPEG controls are exact identity,
- every supported non-neutral control changes rendered pixels,
- values outside the declared ranges fail instead of clipping silently,
- the Darkroom JPEG panel calls the real preview endpoint,
- JPEG UI does not show Kelvin/RAW Tint semantics,
- stale preview responses cannot replace a newer UI state.
