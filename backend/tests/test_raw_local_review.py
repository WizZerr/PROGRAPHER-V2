"""Synthetic source RAW contact-sheet tests; never commits photographer data."""
from types import SimpleNamespace

import numpy as np
import pytest

from app.photographer import raw_local_review as review


def test_preview_dark_to_light_and_no_edited_inputs():
    rgb = np.zeros((10, 10, 3), dtype=np.float32)
    rgb[5:, :, :] = 1
    img = review._display_thumbnail(rgb)
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (0, 0, 0)
    assert img.getpixel((0, 9)) == (255, 255, 255)


def test_nonfinite_preview_rejected():
    with pytest.raises(ValueError):
        review._display_thumbnail(np.full((5, 5, 3), np.nan, dtype=np.float32))


def test_local_review_hash_preserves_original_and_no_private_aggregate(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    raw = source / "SIMULATED.CR3"
    raw.write_bytes(b"synthetic fixture")
    import hashlib
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    m = tmp_path / "PRIVATE.json"
    import json
    m.write_text(json.dumps({
        "all_model_inputs_are_RAW_only": True,
        "records": [{"provenance_PRIVATE": {
            "raw_path": str(raw), "raw_sha256": digest,
            "catalog_image_id": 100, "provisional_catalog_group": "GTEST",
        }}]
    }), encoding="utf-8")
    fake = SimpleNamespace(
        source_sha256=digest,
        rgb_linear=np.ones((8, 8, 3), dtype=np.float32) * 0.2,
    )
    monkeypatch.setattr(review, "decode_raw", lambda path: fake)
    out = tmp_path / "review"
    report = review.build_review(m, source, out)
    assert report["thumbnails_created"] == 1
    assert "SIMULATED" not in str(report)
    assert "GTEST" not in str(report)
    assert (out / "source_preview_01.jpg").is_file()
    html = (out / "REVIEW_PRIVATE.html").read_text(encoding="utf-8")
    assert "SIMULATED.CR3" in html
    assert "raw_identity_verified_by_photographer" in html
    assert "final_edit_confirmed_by_photographer" in html
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="new or empty"):
        review.build_review(m, source, out)


def test_changed_raw_does_not_create_thumbnail(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw = raw_root / "SIMULATED.CR3"
    raw.write_bytes(b"fixture")
    import json
    manifest = tmp_path / "private.json"
    manifest.write_text(json.dumps({
        "all_model_inputs_are_RAW_only": True,
        "records": [{"provenance_PRIVATE": {
            "raw_path": str(raw), "raw_sha256": "a" * 64
        }}]
    }), encoding="utf-8")
    monkeypatch.setattr(review, "decode_raw", lambda path: SimpleNamespace(
        source_sha256="b" * 64,
        rgb_linear=np.ones((8, 8, 3), dtype=np.float32),
    ))
    report = review.build_review(manifest, raw_root, tmp_path / "out")
    assert report["thumbnails_created"] == 0
    assert report["failed"] == {"ValueError": 1}
