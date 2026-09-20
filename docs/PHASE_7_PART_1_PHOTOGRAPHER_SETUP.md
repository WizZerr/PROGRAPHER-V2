# ProGrapher V2 — Phase 7 Part 1 — Photographer Setup

## Implemented

- Detect Lightroom Classic using OS-aware discovery:
  - Windows registry + standard Adobe install locations.
  - macOS `/Applications` discovery path prepared.
- Manual `.lrcat` selection through the native Tauri file dialog.
- Catalog is opened SQLite read-only.
- Selected catalog path and setup state are persisted locally.
- Photographer profile state begins as:
  - `no_profile`
  - then `data_review` after a valid catalog is selected.
- Catalog photo-record count may be displayed.
- The product explicitly does NOT treat total catalog photos as final edits or
  valid training examples.

## Important

`catalog_photo_records` is only a diagnostic catalog count.

`matched_final_edits` is intentionally not invented in Part 1. Pairing the
correct RAW with final edits belongs to the Lightroom Dataset work in Phase 8.

## Remaining Phase 7

- style / preset and required camera-profile selection;
- exact usable RAW vs final-edit matching count;
- readiness rules for experimental/evaluated profile;
- real Lightroom detection/catalog validation on macOS;
- Windows test against a real photographer catalog.
