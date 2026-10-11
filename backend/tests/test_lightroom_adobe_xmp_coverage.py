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
    assert report["lexical_family_keys"]["local_masks_retouch"] == ["MaskGroupBasedCorrections"]
    assert report["uncompared_property_structure_count"]["sequence_shallow"] == 1
    assert "777" not in str(report)
    assert "SYNTH" not in str(report)
    assert report["training_ready_samples"] == 0


def test_categories_are_lexical_only():
    assert lexical_family("MaskGroupBasedCorrections") == "local_masks_retouch"
    assert lexical_family("Look") == "look_and_profile"
    assert lexical_family("CropTop") == "crop_geometry"
    assert lexical_family("FutureUnexpectedField") == "other_unclassified"
