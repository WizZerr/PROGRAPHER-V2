"""SP-AUTO-01 research contract tests: synthetic only; no Lightroom or real photos."""
from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto01 as bridge


def _layout(tmp_path):
    root = tmp_path / bridge.RESEARCH_NAME
    cat = root / bridge.CATALOG_PARENT
    cat.mkdir(parents=True)
    (cat / bridge.CATALOG_NAME).write_bytes(b"synthetic catalog" * 128)
    (cat / bridge.PREVIEW_NAME).mkdir()
    return root, cat


def _complete_job(tmp_path):
    root, cat = _layout(tmp_path)
    job = bridge.prepare(root_override=root)
    status = bridge._fields(job.parent / "result.txt")
    fields = bridge._fields(job)
    assert fields["selection_policy"] == bridge.SELECTION
    assert fields["operation"] == bridge.OPERATION
    assert fields["neutral_policy"] == bridge.NEUTRAL_POLICY
    return root, cat, job, status["job_id"]


def _success_result(tmp_path, *, result_overrides=None):
    root, cat, job, job_id = _complete_job(tmp_path)
    work = job.parent
    img = work / "exports" / "neutral.jpg"
    rng = np.random.default_rng(88)
    Image.fromarray(rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)).save(
        img, format="JPEG", quality=92
    )
    target = work / "master_target_PRIVATE.txt"
    target.write_text(
        "schema=prographer.spauto01.master_target.v0\n"
        + f"job_id={job_id}\n"
        + "master_uuid=master_A\n"
        + "target_Exposure2012=0.7\n"
        + "full_develop_serialized_PRIVATE=" + ("synthetic" * 20) + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "ok",
        "job_id": job_id,
        "jpeg": str(img),
        "bytes": str(img.stat().st_size),
        "master_uuid": "master_A",
        "copy_uuid": "copy_B",
        "raw_offline": "true",
        "smart_preview": "true",
        "master_develop_unchanged": "true",
        "neutral_exposure": "0.0",
        "neutral_cropped": "false",
        "target_snapshot": str(target),
    }
    result.update(result_overrides or {})
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in result.items()),
        encoding="utf-8",
    )
    return root, cat, job, img, target


def test_prepare_creates_single_private_job_without_touching_catalog(tmp_path):
    root, cat = _layout(tmp_path)
    catalog = cat / bridge.CATALOG_NAME
    before = hashlib.sha256(catalog.read_bytes()).hexdigest()
    job = bridge.prepare(root_override=root)
    assert job.is_file()
    assert bridge._fields(job.parent / "result.txt")["status"] == "prepared"
    assert bridge._fields(job)["catalog_path"] == str(catalog)
    assert (job.parent / "exports").is_dir()
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == before
    with pytest.raises(FileExistsError):
        bridge.prepare(root_override=root)


def test_prepared_is_not_automatically_success(tmp_path):
    root, _cat, _job, _jobid = _complete_job(tmp_path)
    assert bridge.verify(root_override=root) == (False, "NOT_COMPLETE_PREPARED")


def test_mock_lightroom_result_succeeds_only_with_private_artifacts(tmp_path):
    root, cat, job, img, target = _success_result(tmp_path)
    original = (cat / bridge.CATALOG_NAME).read_bytes()
    assert bridge.verify(root_override=root)[0] is True
    assert img.is_file() and target.is_file()
    assert (cat / bridge.CATALOG_NAME).read_bytes() == original


@pytest.mark.parametrize("field,value", [
    ("raw_offline", "false"),
    ("smart_preview", "false"),
    ("master_develop_unchanged", "false"),
    ("neutral_cropped", "true"),
    ("neutral_exposure", "0.45"),
    ("copy_uuid", "master_A"),
])
def test_rejects_false_source_or_reset_proof(tmp_path, field, value):
    root, _cat, _job, _img, _target = _success_result(
        tmp_path, result_overrides={field: value}
    )
    assert bridge.verify(root_override=root)[0] is False


def test_rejects_file_escape_even_if_size_valid(tmp_path):
    root, cat, job, img, target = _success_result(tmp_path)
    sibling = cat / "escaped.jpg"
    sibling.write_bytes(img.read_bytes())
    result = bridge._fields(job.parent / "result.txt")
    result["jpeg"] = str(sibling)
    (job.parent / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in result.items()), encoding="utf-8"
    )
    assert bridge.verify(root_override=root)[1] == "JPEG_OUTSIDE_PRIVATE_OUTPUT"


def test_rejects_stale_or_corrupt_job(tmp_path):
    root, cat, job, img, target = _success_result(tmp_path)
    result = bridge._fields(job.parent / "result.txt")
    result["job_id"] = "0" * 32
    (job.parent / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in result.items()), encoding="utf-8"
    )
    assert bridge.verify(root_override=root)[1] == "STALE_OR_MISMATCHED_JOB"


def test_missing_private_master_target_fails(tmp_path):
    root, cat, job, img, target = _success_result(tmp_path)
    target.unlink()
    assert bridge.verify(root_override=root)[1] == "INVALID_PRIVATE_TARGET"


def test_missing_smart_preview_store_blocks_prepare(tmp_path):
    root, cat = _layout(tmp_path)
    (cat / bridge.PREVIEW_NAME).rmdir()
    with pytest.raises(ValueError, match="Smart Preview"):
        bridge.prepare(root_override=root)


def test_smart_preview_symlink_is_rejected(tmp_path):
    root, cat = _layout(tmp_path)
    real = tmp_path / "elsewhere"
    real.mkdir()
    smart = cat / bridge.PREVIEW_NAME
    smart.rmdir()
    try:
        smart.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not available on this Windows environment")
    with pytest.raises(ValueError, match="Smart Preview"):
        bridge.prepare(root_override=root)


def test_research_lua_auto_bridge_is_armed_only_for_exact_catalog():
    from pathlib import Path
    base = Path(__file__).resolve().parents[2] / (
        "integrations/lightroom_classic/spauto01/ProGrapherAutoNeutral.lrdevplugin"
    )
    worker = (base / "AutoWorker.lua").read_text(encoding="utf-8")
    info = (base / "Info.lua").read_text(encoding="utf-8")
    assert "LrForceInitPlugin = true" in info
    assert "LrLibraryMenuItems" in info
    assert "file = 'Status.lua'" in info
    assert (base / "Status.lua").is_file()
    assert "SP_01_AUTO_RETRY_01.lrcat" in worker
    assert "EXACTLY_ONE_MASTER_IN_DISPOSABLE_CATALOG" in worker
    assert "SP_01_AUTO_RETRY_01 Smart Previews.lrdata" in worker
    assert "catalog:getAllPhotos()" in worker
    assert "catalog:createVirtualCopies(" in worker
    assert "LrDevelopController.resetAllDevelopAdjustments()" in worker
    assert "catalog:getTargetPhoto() ~= copy" in worker
    assert "copy:getRawMetadata('masterPhoto') ~= master" in worker
    assert "LrFileUtils.isEmptyDirectory(exports)" in worker
    assert "master_develop_unchanged" in worker
    # Reset may be a no-op while Develop UI is still loading; never accept an
    # unverified copy or remove its original master target.
    assert "LrDevelopController.getValue" in worker
    assert "develop_wait_ready" in worker
    assert "develop_reset_readback" in worker
    assert "SPAUTO_RESET_NO_DEVELOP_CHANGE_AFTER_12S" in worker
    assert "SPAUTO_RESET_NONZERO_EXPOSURE_REQUIRES_BASELINE_POLICY" in worker
    assert "SPAUTO_RESET_CROP_STILL_ACTIVE" in worker
    assert "sourcePath" in worker and "checkPhotoAvailability()" in worker
    for forbidden in (
        "master:applyDevelopSettings(", "master:applyDevelopPreset(",
        "master:deleteSmartPreview(", "LrFileUtils.delete(",
    ):
        assert forbidden not in worker
