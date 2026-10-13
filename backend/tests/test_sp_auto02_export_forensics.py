"""Synthetic SP-AUTO-02 encoding forensics; no photographer photos or Lightroom."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto01 as bridge
from app.lightroom_bridge import sp_auto01_reference_compare as ref
from app.lightroom_bridge import sp_auto02_export_forensics as fx


def _pair(tmp_path, *, manual_quality=80, resized=False, same_bytes=False):
    root = tmp_path / bridge.RESEARCH_NAME
    home = root / bridge.CATALOG_PARENT
    home.mkdir(parents=True)
    (home / bridge.CATALOG_NAME).write_bytes(b"not-real-catalog" * 150)
    (home / bridge.PREVIEW_NAME).mkdir()
    job_path = bridge.prepare(root_override=root)
    job = bridge._fields(job_path)
    work = job_path.parent

    source = work / "exports" / "auto.jpg"
    manual = root / ref.MANUAL_RELATIVE
    manual.parent.mkdir(parents=True)
    pix = np.random.default_rng(9).integers(0, 256, (128, 128, 3), dtype=np.uint8)
    Image.fromarray(pix).save(source, "JPEG", quality=100, subsampling=0)
    if same_bytes:
        manual.write_bytes(source.read_bytes())
    else:
        if resized:
            pix = pix[:100, :110, :]
        Image.fromarray(pix).save(manual, "JPEG", quality=manual_quality, subsampling=2)
    target = work / "master_target_PRIVATE.txt"
    target.write_text(
        "schema=prographer.spauto01.master_target.v0\n"
        + "job_id=" + job["job_id"] + "\n"
        + "master_uuid=master_fake\n"
        + "full_develop_serialized_PRIVATE=" + "HIDDEN_TARGET_" * 30 + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "ok", "job_id": job["job_id"],
        "jpeg": str(source), "bytes": str(source.stat().st_size),
        "master_uuid": "master_fake", "copy_uuid": "virtual_fake",
        "raw_offline": "true", "smart_preview": "true",
        "master_develop_unchanged": "true", "neutral_exposure": "0.0",
        "neutral_cropped": "false", "target_snapshot": str(target),
    }
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in result.items()), encoding="utf-8"
    )
    assert bridge.verify(root_override=root)[0]
    return root, work, source, manual, target


def test_different_jpeg_encodings_explain_structure_not_causality(tmp_path):
    root, work, src, manual, target = _pair(tmp_path)
    before = (src.read_bytes(), manual.read_bytes(), target.read_bytes())
    d = fx.run(root_override=root)
    assert d["dimensions_match"] is True
    assert d["jpeg_quantization_tables_match"] is False
    assert d["jpeg_chroma_subsampling_match"] is False
    assert d["encoding_difference_supported"] is True
    assert d["decoded_rgb_pixel_equal"] is False
    assert d["mean_absolute_rgb_difference_8bit"] > 0
    assert d["fraction_channels_exact"] < 1
    assert d["fraction_channels_within_1"] <= d["fraction_channels_within_2"]
    assert d["rgb_psnr_db"] > 0
    assert d["cause_of_pixel_difference_proven"] is False
    assert d["training_ready"] is False
    assert before == (src.read_bytes(), manual.read_bytes(), target.read_bytes())

    raw = (work / fx.DIRNAME / fx.REPORT).read_text(encoding="utf-8")
    assert json.loads(raw)["schema"] == fx.SCHEMA
    assert str(src) not in raw and str(manual) not in raw
    assert "HIDDEN_TARGET_" not in raw
    assert "master_fake" not in raw
    assert "0H1A4577" not in raw


def test_same_decoded_pixels_no_false_causal_leakage_proof(tmp_path):
    root, _, _, _, _ = _pair(tmp_path, same_bytes=True)
    d = fx.run(root_override=root)
    assert d["decoded_rgb_pixel_equal"] is True
    assert d["jpeg_quantization_tables_match"] is True
    assert d["rgb_psnr_db"] is None
    assert d["cause_of_pixel_difference_proven"] is False
    assert d["neutrality_independent_of_master_develop_proven"] is False


def test_different_dimensions_do_not_create_spurious_rgb_metrics(tmp_path):
    root, _, _, _, _ = _pair(tmp_path, resized=True)
    d = fx.run(root_override=root)
    assert d["diagnostic_status"] == "DIMENSION_MISMATCH_STOP"
    assert d["dimensions_match"] is False
    assert d["training_ready"] is False
    assert "mean_absolute_rgb_difference_8bit" not in d


def test_forensics_never_overwrites_a_previous_report(tmp_path):
    root, work, _, _, _ = _pair(tmp_path)
    fx.run(root_override=root)
    report = work / fx.DIRNAME / fx.REPORT
    before = report.read_bytes()
    with pytest.raises(FileExistsError, match="already exists"):
        fx.run(root_override=root)
    assert report.read_bytes() == before


def test_fail_closed_when_bridge_not_verified(tmp_path):
    root, work, src, manual, _ = _pair(tmp_path)
    state = bridge._fields(work / "result.txt")
    state["master_develop_unchanged"] = "false"
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in state.items()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="not verified"):
        fx.run(root_override=root)
    assert not (work / fx.DIRNAME).exists()


def test_missing_manual_reference_no_report(tmp_path):
    root, work, _, manual, _ = _pair(tmp_path)
    manual.unlink()
    with pytest.raises(ValueError, match="manual neutral reference"):
        fx.run(root_override=root)
    assert not (work / fx.DIRNAME).exists()
