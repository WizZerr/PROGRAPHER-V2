"""SP-AUTO-01: synthetic, source-only analysis integration tests."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto01 as bridge
from app.lightroom_bridge import sp_auto01_postprocess as post


def _verified_job(tmp_path):
    root = tmp_path / bridge.RESEARCH_NAME
    catalog_folder = root / bridge.CATALOG_PARENT
    catalog_folder.mkdir(parents=True)
    (catalog_folder / bridge.CATALOG_NAME).write_bytes(b"synthetic test catalog" * 180)
    (catalog_folder / bridge.PREVIEW_NAME).mkdir()
    job_path = bridge.prepare(root_override=root)
    job = bridge._fields(job_path)
    work = job_path.parent
    export = work / "exports" / "auto.jpg"
    rng = np.random.default_rng(45)
    pixels = rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(export, "JPEG", quality=95)
    target = work / "master_target_PRIVATE.txt"
    target.write_text(
        "schema=prographer.spauto01.master_target.v0\n"
        f"job_id={job['job_id']}\n"
        "master_uuid=synthetic_master\n"
        "photographer_target_training_approved=false\n"
        "full_develop_serialized_PRIVATE=" + "private_target_DO_NOT_READ_" * 30 + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "ok", "job_id": job["job_id"],
        "jpeg": str(export), "bytes": str(export.stat().st_size),
        "master_uuid": "synthetic_master", "copy_uuid": "synthetic_copy",
        "raw_offline": "true", "smart_preview": "true",
        "master_develop_unchanged": "true",
        "neutral_exposure": "0.0", "neutral_cropped": "false",
        "target_snapshot": str(target),
    }
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in result.items()), encoding="utf-8"
    )
    assert bridge.verify(root_override=root)[0] is True
    return root, work, export, target


class FakeRankedAI:
    def predict(self, image):
        assert image.mode == "RGB"
        return {
            "suggested_label": "UNKNOWN", "raw_top_label": "PORTRAIT",
            "abstained": True, "relative_top_score": 0.24,
            "relative_margin": 0.02,
            "ranking": [
                {"label": "PORTRAIT", "rank": 1, "relative_score": 0.24}
            ],
        }


def test_successful_auto_export_feeds_neutral_jpeg_only(tmp_path):
    root, work, jpeg, target = _verified_job(tmp_path)
    jpeg_bytes, target_bytes = jpeg.read_bytes(), target.read_bytes()
    result = post.analyze_completed_job(root_override=root, predictor=FakeRankedAI())
    assert result["analyzed"] == 1
    assert result["training_ready"] == 0
    assert result["scene_abstained"] is True
    assert result["scene_status"] == "ZERO_SHOT_UNCALIBRATED_HUMAN_REVIEW_REQUIRED"
    assert jpeg.read_bytes() == jpeg_bytes and target.read_bytes() == target_bytes

    private = json.loads((work / post.OUTPUT_NAME / post.PRIVATE_REPORT).read_text())
    source = private["source_analysis_ONLY_NEUTRAL_JPEG"]
    assert source["training_ready"] is False
    assert source["photographer_develop_target_in_model_input"] is False
    assert source["scene"]["raw_top_label"] == "PORTRAIT"
    assert private["visual_model_received_master_develop_target"] is False
    assert private["photographer_target_sha256_PRIVATE"] == post._digest(target)
    assert source["source_kind"].startswith("LIGHTROOM_SDK_AUTO_EXPORTED_")

    aggregate_text = (work / post.OUTPUT_NAME / post.AGGREGATE_REPORT).read_text()
    assert str(jpeg) not in aggregate_text
    assert str(target) not in aggregate_text
    assert "synthetic_master" not in aggregate_text
    assert "private_target_DO_NOT_READ" not in aggregate_text
    assert "PORTRAIT" not in aggregate_text
    assert post._digest(target) not in aggregate_text


def test_no_scene_model_default_and_training_never_enabled(tmp_path):
    root, work, _, _ = _verified_job(tmp_path)
    result = post.analyze_completed_job(root_override=root)
    assert result["scene_status"] == "AI_NOT_RUN"
    assert result["training_ready"] == 0


def test_reject_unverified_job_without_writing_analysis(tmp_path):
    root, work, export, target = _verified_job(tmp_path)
    state = bridge._fields(work / "result.txt")
    state["master_develop_unchanged"] = "false"
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in state.items()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="not verified"):
        post.analyze_completed_job(root_override=root)
    assert not (work / post.OUTPUT_NAME).exists()


def test_no_overwrite_and_no_duplicate_processing(tmp_path):
    root, work, export, target = _verified_job(tmp_path)
    post.analyze_completed_job(root_override=root)
    prior = (work / post.OUTPUT_NAME / post.PRIVATE_REPORT).read_bytes()
    with pytest.raises(FileExistsError, match="already exists"):
        post.analyze_completed_job(root_override=root)
    assert (work / post.OUTPUT_NAME / post.PRIVATE_REPORT).read_bytes() == prior


def test_if_target_changes_during_inference_no_result_written(tmp_path):
    root, work, export, target = _verified_job(tmp_path)
    class BadRuntime:
        def predict(self, image):
            target.write_text("changed by test only", encoding="utf-8")
            return FakeRankedAI().predict(image)
    with pytest.raises(ValueError, match="changed"):
        post.analyze_completed_job(root_override=root, predictor=BadRuntime())
    assert not (work / post.OUTPUT_NAME).exists()


def test_no_exported_jpeg_is_not_success(tmp_path):
    root, work, jpeg, target = _verified_job(tmp_path)
    jpeg.unlink()
    with pytest.raises(ValueError, match="not verified"):
        post.analyze_completed_job(root_override=root)
    assert not (work / post.OUTPUT_NAME).exists()
