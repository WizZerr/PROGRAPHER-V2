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

## Correction after photographer aggregate report (2026-10-11)
The first 01E.02 report counted all RAW rows as color-grading nonzero because ColorGradeBlending was nonzero in every row. This is a **configuration value, not proof of visible grading**. The original raw field-presence and raw nonzero counts remain for diagnostics; new separate metrics `nonzero_configuration_values`, `nonzero_adjustment_values` and `records_with_nonzero_adjustment_candidate` exclude Blending/Balance from adjustment candidates. These are **candidate controls only**: a hue with zero saturation might have no visible impact; Adobe validation remains mandatory. Synthetic regression added. In the 01E.02 first report, 7,023 nonzero Blending values were observed; there were 47 additional nonzero ColorGrade field occurrences. Number of distinct affected photos not yet known without recalculation.
