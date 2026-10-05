# PG-04.02 — Product JPEG Preview / Full-Resolution Render Contract

Date: 2026-10-04  
Status: implementation committed; regression verification pending because hosted GitHub Actions minutes are exhausted.

## Purpose

PG-04.02 connects the shared JPEG EditRecipe/renderer from PG-04.01 to a product-side execution path without defining a second edit interpretation.

The Part owns:

- fast preview rendering,
- full-resolution technical rendering,
- revision-scoped render cache,
- stale-revision rejection,
- a current-revision guard that future approval/save flows must call.

It does **not** define final JPEG export encoding. That remains PG-04.03.

## Canonical implementation

- `backend/app/rendering/jpeg_product_render.py`
- `backend/app/api/routes/jpeg_render.py`
- `backend/tests/test_jpeg_product_render.py`

The render path consumes `backend/app/rendering/jpeg_renderer.py`; it does not duplicate polynomial semantics.

## Source contract

Only a tracked `.jpg` / `.jpeg` source inside the selected Event root is accepted.

Pillow may identify a camera JPEG carrying a valid MPF index as an `MPO`
container. This is treated as JPEG-compatible input: ProGrapher decodes and edits
the primary frame (frame 0) only. Auxiliary MPO frames are ignored. Containers
other than `JPEG` or `MPO` still fail explicitly.

Before rendering, the source is decoded through the PG-03 JPEG working-space contract:

- EXIF display orientation is normalized,
- embedded ICC is converted to sRGB,
- supported no-ICC RGB/L JPEGs use the declared sRGB assumption,
- unsafe color cases fail explicitly.

A full SHA-256 of the source bytes is recorded in render cache provenance.

## Revision contract

Every render request contains:

- `revision >= 1`,
- one versioned JPEG EditRecipe.

The canonical render-only recipe payload is hashed with SHA-256.

For one Event/file pair:

1. a revision cannot be rebound to a different recipe,
2. a revision cannot be rebound after source bytes change,
3. once revision N+1 becomes current, revision N is stale and is rejected,
4. future approval/save code must pass `assert_current_jpeg_revision()`.

This is the server-side guarantee behind “an old preview must not replace a newer edit” and “do not approve a recipe that has already been replaced.”

## Preview path

Endpoint:

`POST /api/events/{event_id}/files/{fingerprint}/jpeg-render/preview`

Preview uses the same source normalization and shared EditRecipe renderer as full resolution.

For speed, the normalized source is downsampled to a maximum edge of 1600 px before the shared transform is applied.

The response is a transient PNG with `Cache-Control: private, no-store`. Browser cache is intentionally not the revision authority.

## Full-resolution path

Endpoint:

`POST /api/events/{event_id}/files/{fingerprint}/jpeg-render/full`

The shared EditRecipe is applied to the full normalized source dimensions.

The response is a transient lossless PNG. This is deliberately **not** the final export format; PG-04.03 will define JPEG quality, size, ICC, orientation and metadata/GPS policy.

## Current-revision guard

Endpoint:

`POST /api/events/{event_id}/files/{fingerprint}/jpeg-render/assert-current`

A stale or replaced revision returns HTTP 409.

The actual JPEG review/approval UI is not introduced here; when that capability is added, approval must call the same guard rather than trusting a preview already on screen.

## Cache

Local cache root:

`<user-data>/jpeg_product_render_cache/v1/...`

Cache identity includes:

- Event/file identity,
- revision,
- canonical recipe SHA-256,
- source SHA-256,
- renderer contract version.

Artifacts and manifests are written atomically.

## Response provenance

Render responses expose:

- recipe revision,
- recipe SHA-256,
- source SHA-256,
- render mode,
- render dimensions,
- cache hit/miss.

## Completion evidence

The authored regression suite covers:

- full-resolution output equals the shared renderer applied to the PG-03 working-space decode,
- preview maximum edge,
- revision cache reuse,
- same-revision recipe conflict,
- stale revision rejection after a newer revision,
- current-revision approval guard,
- API revision/provenance headers and HTTP 409 behavior,
- real-world JPEG compatibility for MPO/MPF-backed `.JPG` sources, using only the primary frame.

Hosted Actions were intentionally not triggered because the account has exhausted its monthly hosted-runner minutes. PG-04.02 stays `◐` until this suite plus the backend regression/compile checks are executed successfully by local/manual CI or after hosted minutes reset.
