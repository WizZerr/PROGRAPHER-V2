# RAW-CAT-01E.01 — Tone Curve Syntactic Decoder (engineering, NOT Adobe parity)

Date: 2026-10-11
Parent decision: [D-015](D_015_RAW_FIRST_SCOPE.md)

## Scope
A conservative parser for Lightroom Classic Develop `ToneCurvePV2012` and `ToneCurvePV2012Red/Green/Blue` fields when serialized as a **flat comma-separated list of integer x/y point pairs** in 0..255 with strictly increasing x values. Supported forms retain point coordinates, linearity classification, original serialized length and SHA-256 in the **LOCAL PRIVATE** manifest. Unsupported structures retain explicit `undecoded_reason`, length and fingerprint, never invented curve points.

Aggregate report gains `curve_decode_coverage`, with counts for decoded, undecoded, linear, nonlinear and reasons, plus a `curve_decoder` warning. It includes NO individual curve coordinates, photo identifiers, paths or photographer images.

## Evidence and caveats
- Parser verified with synthetic supported/rejected cases and synthetic catalog integration tests.
- **Not yet verified against the photographer's live catalogue after this change**, Lightroom visual controls, XMP output or Lightroom Classic releases.
- A successful syntactic decode is **not proof of Adobe's actual tone-curve interpretation**. Point coordinates in local manifest are never automatically considered training-ready; this part does not run inference, rendering, export or RAW matching.
- No masks, complex local edits, custom camera looks/profiles, or HSL/color-grading reconstruction added here.
- Existing 01D read-only guarantees maintained: immutable SQLite copy, no source writes. No private photographer data committed.

## Next validation (user Windows)
Run both `test_curve_semantics.py` and `test_raw_catalog_intake.py`. Re-run `python -m app.photographer.raw_catalog_intake` against exported copy and upload the aggregate report ONLY. Then confirm at least a small mix of truly nonlinear curves in Lightroom/XMP before calling 01E.01 verified.
