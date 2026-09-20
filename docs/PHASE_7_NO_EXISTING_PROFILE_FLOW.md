# Phase 7 — No existing profile / no catalog flow

## Why this change exists

A photographer is not expected to arrive with a ProGrapher profile file.

The personal profile is a future ProGrapher artifact created after importing
and validating that photographer's own editing data.

The Master Plan requires selecting a Lightroom catalog **or another edit
source**, so catalog-only onboarding was too narrow.

## Supported setup choices

1. Existing Lightroom `.lrcat`.
2. A user-selected edits/XMP folder.
3. No historical edit source yet.

Choosing option 3 sets:
- source_type = `none`
- status = `needs_more_data`

It does not block technical use of ProGrapher.

## Truthfulness

- XMP count is only a file count.
- Lightroom catalog photo count is only a catalog record count.
- Neither is shown as valid training-pair count.
- RAW ↔ final-edit matching remains Phase 8 work.
