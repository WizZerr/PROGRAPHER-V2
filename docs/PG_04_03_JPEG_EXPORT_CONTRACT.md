# PG-04.03 — Encoded JPEG Export Contract

Date: 2026-10-04  
Status: implementation prepared; manual delta verification required before V.

## Purpose

PG-04.03 defines the encoded JPEG bytes produced from a current JPEG EditRecipe.

It owns encoding semantics only. Destination folders, duplicate names, existing files, disk-full handling and atomic final writes belong to PG-04.04.

## Canonical implementation

- `backend/app/rendering/jpeg_export.py`
- `backend/app/api/routes/jpeg_export.py`
- `backend/tests/test_jpeg_export.py`

The encoder consumes the shared PG-04.01 renderer. It does not define a second edit interpretation.

## Source-of-pixels rule

Export always resolves the tracked original JPEG inside the Event and performs:

`source JPEG -> PG-03 working-space decode -> shared EditRecipe render -> optional resize -> JPEG encode`

It does not encode the product preview, render-cache PNG or another already-edited JPEG copy.

The requested recipe revision must still be current. Stale/replaced revisions are rejected before export.

## Quality and size

- Quality range: 1–100.
- Default quality: 95.
- Chroma subsampling: fixed 4:4:4 for this contract.
- Progressive encoding: off.
- Optimize pass: off.
- `max_edge=null`: keep full rendered dimensions.
- Positive `max_edge`: downscale after the full-resolution recipe render.
- Export never upscales a smaller image.

The resize occurs after the recipe render so export is derived from full-resolution edit semantics.

## Color / ICC

Pixels entering the encoder are already normalized to the declared sRGB working-space contract.

Two explicit policies exist:

- `embed_srgb` — default; embed an sRGB ICC profile.
- `omit` — write no ICC profile.

There is no pass-through of an incompatible source ICC after pixels have been converted to sRGB.

## Orientation

PG-03 normalizes EXIF display orientation into pixels before the recipe is rendered.

Encoded output therefore has physically upright pixels. When EXIF is preserved, Orientation is rewritten to `1`.

Width/height EXIF fields are rewritten to the actual encoded dimensions after optional resize.

## Metadata and GPS

Metadata policy:

- `preserve` — copy source EXIF, then patch orientation/dimensions.
- `strip` — emit no EXIF metadata.

GPS is a separate explicit opt-in and defaults to false.

- `include_gps=false`: GPS is removed from preserved EXIF.
- `include_gps=true`: source GPS is preserved if it exists.
- Asking to include GPS does not invent GPS on a source that has none.
- `metadata_policy=strip` + `include_gps=true` is invalid.

## Reopen verification

Every encoded artifact is reopened before it is returned.

Verification checks:

- format is JPEG,
- mode is RGB,
- encoded dimensions match expected dimensions,
- ICC presence matches policy,
- preserved orientation is normalized,
- GPS presence matches the actual opt-in/source combination,
- stripped metadata remains stripped.

A failed reopen/measurement rejects the export bytes.

## API

`POST /api/events/{event_id}/files/{fingerprint}/jpeg-export/encode`

The endpoint returns encoded JPEG bytes only. It does not choose or write a destination path.

Stale/replaced recipe revisions return HTTP 409.

## Boundary to PG-04.04

PG-04.04 will take these already-verified encoded bytes and own:

- separate destination folders,
- file naming and duplicate-name policy,
- existing destination files,
- disk-full/write failures,
- atomic temporary-file -> final-file promotion,
- source hash before/after filesystem export.
