# RAW-CAT-01E.02 — Color, profiles and opaque edit coverage

Date: 2026-10-11. Scope: D-015 RAW-first. Research-only backend feature; it does not produce a Lightroom-equivalent RAW render, train an AI Brain, or modify originals.

## Syntactic support
- HSL Mixer: Hue/Saturation/Luminance across eight colors, Gray Mixer for eight colors.
- Color Grading: Global/Shadow/Midtone/Highlight Hue/Sat/Lum where explicitly present; Blending and Balance.
- Legacy Split Toning: Shadow/Highlight Hue/Saturation and Balance.
- Numeric values must be finite. Explicit 0 and missing are tracked separately. No values/defaults are fabricated.
- CameraProfile, ProcessVersion, WhiteBalance and B&W stay in the scalar inventory. Look, AILook, CameraProfileDigest, Preset and ToggleStyleDigest are opaque hashed descriptions only.
- Masks, Retouch, PointColors, RedEyeInfo and FilterList remain opaque. Present/nonempty does NOT mean active, correct or reproducible.

## Outputs
Aggregate additions: color_decoder, color_family_coverage, color_field_coverage, profile_field_coverage, opaque_local_edit_coverage. No filenames, capture times, folder paths or personal values. Optional PRIVATE manifest stays LOCAL; metadata is hashed when opaque. All rows retain training_eligible=false and color_semantics_validated=false.

## Evidence / next Gate
Local synthetic suite: 27 tests passed (including 01D and 01E.01). Windows pytest and large real Lightroom catalog validation PENDING. Lightroom/XMP semantics, true masks, camera look rendering, source RAW identity, event labels, finality and G1-G4 are NOT proven. G0 remains unsigned.

Next: on Windows, run tests/test_curve_semantics.py tests/test_raw_catalog_intake.py tests/test_develop_color_semantics.py, then scan exported closed Lightroom catalog and share AGGREGATE report ONLY.
