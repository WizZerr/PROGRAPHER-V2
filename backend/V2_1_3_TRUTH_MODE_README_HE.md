# ProGrapher Backend V2.1.3 — Darkroom Truth Mode

Smoke-test diagnostics after the first real DNG test.

## New
- `GET /api/photos/{photo_id}/ai/xmp-test` downloads the exact Active-Profile AI Recipe as a Lightroom XMP sidecar.
- It does **not** approve the photo, create feedback, or create learning data.
- This lets us separate a bad local preview from a bad AI prediction by opening the exact Recipe in Lightroom Classic.

## Important
The local renderer is still approximate. Adobe Lightroom/XMP is authoritative for absolute white balance and final Develop interpretation.

No DB reset and no retraining are required.
