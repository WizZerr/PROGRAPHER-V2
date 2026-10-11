"""Synthetic XMP coverage audit; no photographer material."""
from app.photographer.lightroom_adobe_xmp_coverage import (
    audit_uncompared_properties, lexical_family,
)
from test_lightroom_adobe_xmp_comparison import fixture


def test_uncompared_fields_contain_names_not_values(tmp_path):
    plan, xmp = fixture(tmp_path)
    report = audit_uncompared_properties(plan, xmp)
    assert report["compared_match_count"] == 3
    assert report["compared_property_count"] == 4
    assert report["uncompared_property_count"] == 1
    assert report["lexical_family_keys"]["local_masks_retouch_opaque"] == ["MaskGroupBasedCorrections"]
    assert report["uncompared_property_structure_count"]["sequence_shallow"] == 1
    assert "777" not in str(report)
    assert "SYNTH" not in str(report)
    assert report["training_ready_samples"] == 0


def test_categories_are_lexical_only():
    assert lexical_family("MaskGroupBasedCorrections") == "local_masks_retouch_opaque"
    assert lexical_family("Look") == "profile_look_opaque"
    assert lexical_family("CropTop") == "optics_geometry"
    assert lexical_family("FutureUnexpectedField") == "other_unclassified"


def test_hsl_calibration_detail_and_opaque_are_not_conflated():
    assert lexical_family("LuminanceAdjustmentRed") == "hsl_mixer"
    assert lexical_family("HueAdjustmentMagenta") == "hsl_mixer"
    assert lexical_family("LuminanceNoiseReductionDetail") == "detail_noise"
    assert lexical_family("RedHue") == "camera_calibration_context"
    assert lexical_family("ParametricLights") == "tone_curve_controls"
    assert lexical_family("PointColors") == "point_color_opaque"
    assert lexical_family("SplitToningBalance") == "legacy_split_toning"


def test_v2_taxonomy_accounting_preserved(tmp_path):
    plan, xmp = fixture(tmp_path)
    report = audit_uncompared_properties(plan, xmp)
    assert report["schema"].endswith(".v2")
    assert report["name_taxonomy"] == "xmp_name_hint_v2"
    assert sum(report["lexical_family_counts"].values()) + report[
        "unlisted_nonstandard_property_key_count"
    ] == report["uncompared_property_count"]
