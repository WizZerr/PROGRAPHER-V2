"""01E.03A regression fixtures: synthetic names and curves ONLY."""
import json
from pathlib import Path
import sqlite3

from app.photographer.lightroom_validation_plan import (
    CATEGORIES, build_validation_plan, classify_sample,
)
from app.photographer.raw_catalog_intake import inspect_catalog
from test_raw_catalog_intake import synthetic_catalog


def _rec(image_id, group, develop=None, complex_fields=None, excluded=None):
    return {
        "catalog_image_id": image_id, "file_stem": "SYNTH_PRIVATE_" + str(image_id),
        "extension": "cr3", "event_group_id": group,
        "develop": develop or {}, "complex": complex_fields or {},
        "parse_exclusion": excluded,
        "training_eligible": False,
    }


def test_sample_classification_varied_evidence_and_unverified_masks():
    r = _rec(1, "G0001", {
        "HueAdjustmentYellow": -4, "ColorGradeBlending": 50,
        "ConvertToGrayscale": True,
        "ColorGradeShadowLum": 4,
    }, {
        "ToneCurvePV2012": {"decoded": True, "is_linear": False},
        "ToneCurvePV2012Red": {"decoded": True, "is_linear": False},
        "MaskGroupBasedCorrections": {"decoded": False, "structure_nonempty": True},
    })
    tags = classify_sample(r)
    assert "nonlinear_tone_curve" in tags
    assert "nonlinear_rgb_channel_curve" in tags
    assert "hsl_mixer_adjustment_candidate" in tags
    assert "grayscale_conversion" in tags
    assert "color_grading_adjustment_candidate" in tags
    assert "mask_payload_unverified" in tags
    assert not classify_sample({**r, "parse_exclusion": "develop_parse_failed"})
    assert "color_grading_adjustment_candidate" not in classify_sample(
        _rec(2, "G0001", {"ColorGradeBlending": 50})
    )


def test_plan_privacy_bounded_counts_and_raw_rows_stay_unverified():
    records = [
        _rec(1, "G0001", {"HueAdjustmentYellow": -2}),
        _rec(2, "G0002", {"HueAdjustmentYellow": -3}),
        _rec(3, "G0003", {"HueAdjustmentYellow": -4}),
        _rec(4, "G0001", {"ColorGradeBlending": 50}),
        _rec(5, "G0002", {"ConvertToGrayscale": True}),
    ]
    report, private = build_validation_plan(records, per_category=2)
    assert report["category_candidate_counts"]["hsl_mixer_adjustment_candidate"] == 3
    assert report["selected_unique_photo_count"] >= 3
    assert report["selected_candidate_group_count"] >= 2
    assert report["training_ready_samples"] == 0
    assert all(not sample["training_eligible"] for sample in private["samples"])
    assert all(not sample["lightroom_parity_verified"] for sample in private["samples"])
    assert "SYNTH_PRIVATE" not in json.dumps(report)
    assert "SYNTH_PRIVATE_1" in json.dumps(private)
    assert list(report["category_candidate_counts"]) == list(CATEGORIES)


def test_catalog_integration_works_without_raw_or_xmp(tmp_path: Path):
    cat = tmp_path / "synthetic.lrcat"
    synthetic_catalog(cat)
    report, manifest = inspect_catalog(cat, include_private=True)
    assert manifest is not None
    sampled, private = build_validation_plan(manifest["records"], per_category=1)
    assert sampled["catalog_raw_rows_considered"] == 2
    assert sampled["selected_unique_photo_count"] >= 1
    assert all(not item["source_raw_verified"] for item in private["samples"])
    assert report["training_ready_samples"] == 0


def test_sample_selector_does_not_fabricate_missing_categories():
    report, private = build_validation_plan([_rec(1, "G0001")])
    assert report["selected_unique_photo_count"] == 0
    assert private["samples"] == []
    assert all(v == 0 for v in report["category_candidate_counts"].values())
