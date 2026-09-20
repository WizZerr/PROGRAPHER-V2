# ProGrapher V2 — Phase 8 Part 4 — Lightroom Reference + Round-trip Foundation

## Implemented

- Explicit Lightroom edit evidence contract for:
  - master photo,
  - virtual copy,
  - verified XMP,
  - manual Lightroom reference.
- Virtual Copy identity is never inferred from filename alone.
- Known-recipe XMP writer for reference testing.
- Reference XMP is written into a separate work folder, never beside or into
  the original RAW.
- RAW SHA-256 is measured before and after the round-trip.
- XMP is read back through the same Dataset reader and compared field by field.
- Missing values remain missing; real zero remains zero.
- Lightroom render reference registry stores:
  - RAW source identity,
  - exact recipe,
  - Process Family,
  - Camera Profile,
  - Lightroom version,
  - render path and SHA-256,
  - color space and file format.
- Reference manifests are written atomically.

## What this proves now

It proves the ProGrapher side of the 23A round-trip contract:
known recipe -> XMP -> readback, while the RAW remains unchanged.

It also creates the storage contract needed by 22A for:
RAW + known recipe + Lightroom export reference.

## What is NOT yet proven

- Lightroom Classic has not yet been shown to ingest the generated reference
  XMP and return exactly the same settings on a real RAW.
- A real Lightroom render has not yet been visually / numerically compared.
- Virtual Copy IDs are only a contract until real Lightroom catalog/plugin
  evidence is available.
- macOS remains NOT TESTED.

Those require a real Lightroom reference exercise and belong to the 15A +
22A + 23A completion step immediately after Phase 8.
