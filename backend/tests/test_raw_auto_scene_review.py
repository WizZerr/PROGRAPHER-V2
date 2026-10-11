"""Synthetic private RAW zero-shot scene review tests; no real weights, no real photos."""
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from app.photographer import raw_auto_scene_review as scene


class FakePredictor:
    def predict(self, image):
        assert image.mode == "RGB"
        return {
            "raw_top_label": "DANCING",
            "suggested_label": "DANCING",
            "relative_top_score": 0.71,
            "relative_margin": 0.56,
            "abstained": False,
        }


def test_rank_uncertain_abstention_and_margin():
    even = [1 / 8.0] * 8
    result = scene._rank_relative(even)
    assert result["suggested_label"] == "UNKNOWN"
    assert result["abstained"] is True
    result = scene._rank_relative([0.03, 0.03, 0.7, 0.03, 0.03, 0.03, 0.12, 0.03])
    assert result["raw_top_label"] == "DANCING"
    assert result["suggested_label"] == "DANCING"
    with pytest.raises(ValueError):
        scene._rank_relative([0.5, 0.5])


def test_darkness_is_not_called_indoor_or_wedding():
    assert scene._lighting_indicator({"fraction_luminance_below_0_03": .89}) == "RAW כהה מאוד"
    assert scene._lighting_indicator({"fraction_luminance_below_0_03": .05}) == "RAW בהיר יחסית"


def test_private_html_and_aggregate_separation(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw = raw_root / "FAKE.CR3"
    raw.write_bytes(b"synthetic")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    private = tmp_path / "PRIVATE.json"
    private.write_text(json.dumps({
        "all_model_inputs_are_RAW_only": True,
        "records": [{"provenance_PRIVATE": {
            "raw_path": str(raw), "raw_sha256": digest,
            "catalog_image_id": 100, "provisional_catalog_group": "GTEST"
        }}]
    }), encoding="utf-8")
    monkeypatch.setattr(scene, "decode_raw", lambda _: SimpleNamespace(
        source_sha256=digest, rgb_linear=np.full((8, 8, 3), .2, dtype=np.float32)
    ))
    result = scene.build_auto_review(private, raw_root, tmp_path / "out", FakePredictor())
    assert result["suggestions_generated"] == 1
    assert result["automatic_unknown_count"] == 0
    assert result["training_ready_samples"] == 0
    assert "FAKE" not in str(result)
    assert "GTEST" not in str(result)
    assert digest not in str(result)
    html = (tmp_path / "out" / "AI_REVIEW_PRIVATE.html").read_text(encoding="utf-8")
    assert "FAKE.CR3" in html
    assert "DANCING" in html
    assert "לא בדקתי עדיין" in html
    assert "לא אומת" in html
    assert (tmp_path / "out" / "preview_01.jpg").is_file()
    with pytest.raises(ValueError, match="new or empty"):
        scene.build_auto_review(private, raw_root, tmp_path / "out", FakePredictor())


def test_model_uses_original_raw_and_rejects_hash_changed(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw = raw_root / "FAKE.CR3"
    raw.write_bytes(b"synthetic")
    private = tmp_path / "PRIVATE.json"
    private.write_text(json.dumps({
        "all_model_inputs_are_RAW_only": True,
        "records": [{"provenance_PRIVATE": {
            "raw_path": str(raw), "raw_sha256": "a" * 64,
            "catalog_image_id": 12
        }}]
    }), encoding="utf-8")
    monkeypatch.setattr(scene, "decode_raw", lambda _: SimpleNamespace(
        source_sha256="b" * 64, rgb_linear=np.zeros((8, 8, 3), dtype=np.float32)
    ))
    report = scene.build_auto_review(private, raw_root, tmp_path / "out", FakePredictor())
    assert report["suggestions_generated"] == 0
    assert report["failures"] == {"ValueError": 1}
