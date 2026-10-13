"""SP-AUTO-03: no Lightroom/private data — synthetic counterfactual safety gates."""
from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto01_retry_setup as clone_tool
from app.lightroom_bridge import sp_auto03 as sp03


def _layout(tmp_path):
    root = tmp_path / sp03.RESEARCH_NAME
    base = root / sp03.CATALOG_DIR
    base.mkdir(parents=True)
    (base / sp03.CATALOG_FILE).write_bytes(b"synthetic counterfactual catalog\0" * 90)
    (base / sp03.SMART_DIR).mkdir()
    return root, base


def _completed(tmp_path, *, variant=False):
    root, base = _layout(tmp_path)
    job = sp03.prepare(root_override=root)
    work = job.parent
    fields = sp03.earlier._fields(job)
    target = np.random.default_rng(244).integers(0, 255, (128, 128, 3), dtype=np.uint8)
    for name in ("A", "B"):
        arr = target.copy()
        if variant and name == "B":
            arr[40:80, 40:80] = 0
        Image.fromarray(arr).save(work / "exports" / name / "render.jpg",
                                  format="JPEG", quality=95)
    values = {
        "status": "ok", "job_id": fields["job_id"],
        "jpeg_a": str(work / "exports" / "A" / "render.jpg"),
        "jpeg_b": str(work / "exports" / "B" / "render.jpg"),
        "master_uuid": "master-1", "copy_a_uuid": "copy-1", "copy_b_uuid": "copy-2",
        "target_fingerprint_unchanged": "true",
        "pre_reset_variants_distinct": "true",
        "post_reset_full_develop_equal": "true",
        "post_reset_exposure_a": "0", "post_reset_exposure_b": "0",
        "post_reset_uncropped_a": "true", "post_reset_uncropped_b": "true",
        "source_raw_offline": "true", "smart_preview_present": "true",
    }
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8"
    )
    return root, base, work, values


def test_prepare_is_private_one_shot_and_never_mutates_catalog(tmp_path):
    root, base = _layout(tmp_path)
    original = base / sp03.CATALOG_FILE
    fingerprint = hashlib.sha256(original.read_bytes()).hexdigest()
    prepared = sp03.prepare(root_override=root)
    assert sp03.earlier._fields(prepared)["operation"] == "COUNTERFACTUAL_VC_RESET"
    assert (prepared.parent / "exports" / "A").is_dir()
    assert (prepared.parent / "exports" / "B").is_dir()
    with pytest.raises(FileExistsError):
        sp03.prepare(root_override=root)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == fingerprint


def test_two_distinct_vcs_converge_identical_decoded_pixels_but_stay_not_training(tmp_path):
    root, base, work, result = _completed(tmp_path)
    before_a = (work / "exports" / "A" / "render.jpg").read_bytes()
    before_b = (work / "exports" / "B" / "render.jpg").read_bytes()
    ok, message, safe = sp03.verify(root_override=root)
    assert ok is True
    assert message == "PASS_VC_ONLY_RESET_INVARIANCE_NOT_BAKE_FREE"
    assert safe["all_decoded_rgb_pixels_equal"] is True
    assert safe["mean_absolute_rgb_difference_8bit"] == 0
    assert safe["historical_smart_preview_bake_free_proven"] is False
    assert safe["training_ready"] is False
    assert (work / "exports" / "A" / "render.jpg").read_bytes() == before_a
    assert (work / "exports" / "B" / "render.jpg").read_bytes() == before_b


def test_pixel_mismatch_is_never_accepted_with_full_develop_agreement(tmp_path):
    root, _, _, _ = _completed(tmp_path, variant=True)
    ok, msg, evidence = sp03.verify(root_override=root)
    assert ok is False and msg == "COUNTERFACTUAL_RENDER_MISMATCH"
    assert evidence["all_decoded_rgb_pixels_equal"] is False
    assert evidence["training_ready"] is False


@pytest.mark.parametrize("key,value", [
    ("target_fingerprint_unchanged", "false"),
    ("pre_reset_variants_distinct", "false"),
    ("post_reset_full_develop_equal", "false"),
    ("post_reset_uncropped_a", "false"),
    ("post_reset_uncropped_b", "false"),
    ("source_raw_offline", "false"),
    ("smart_preview_present", "false"),
    ("post_reset_exposure_a", "0.2"),
    ("post_reset_exposure_b", "-0.2"),
    ("copy_a_uuid", "master-1"),
    ("copy_b_uuid", "copy-1"),
])
def test_fails_closed_on_any_critical_sdk_guard(tmp_path, key, value):
    root, _, work, fields = _completed(tmp_path)
    fields[key] = value
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in fields.items()), encoding="utf-8"
    )
    ok, _message, _safe = sp03.verify(root_override=root)
    assert ok is False


def test_refuses_stale_jobs_and_unverified_artifacts(tmp_path):
    root, _, work, fields = _completed(tmp_path)
    fields["job_id"] = "0" * 32
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in fields.items()), encoding="utf-8"
    )
    assert sp03.verify(root_override=root)[0] is False


def test_refuses_output_outside_dedicated_variant_folder(tmp_path):
    root, _, work, fields = _completed(tmp_path)
    fields["jpeg_a"] = fields["jpeg_b"]
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in fields.items()), encoding="utf-8"
    )
    assert sp03.verify(root_override=root)[1] == "INVALID_OR_REDIRECTED_JPEG"


def test_clone_reuses_only_known_clean_private_research_master(tmp_path):
    root = tmp_path / clone_tool.ROOT_NAME
    origin = root / clone_tool.PARENT / "SP_01_AUTO_RETRY_01"
    origin.mkdir(parents=True)
    cat = origin / "SP_01_AUTO_RETRY_01.lrcat"
    cat.write_bytes(b"prior test catalog" * 120)
    prev = origin / "SP_01_AUTO_RETRY_01 Smart Previews.lrdata"
    prev.mkdir()
    (prev / "block.bin").write_bytes(b"smart-preview" * 30)
    old_work = origin / "SP_01_AUTO_BRIDGE"
    old_work.mkdir()
    (old_work / "result.txt").write_text("status=ok\n")
    new_catalog = clone_tool.clone(
        private_root=root, source_name="SP_01_AUTO_RETRY_01",
        dest_name="SP_01_AUTO_LEAK_01"
    )
    assert new_catalog.name == sp03.CATALOG_FILE
    assert new_catalog.read_bytes() == cat.read_bytes()
    assert not (new_catalog.parent / "SP_01_AUTO_BRIDGE").exists()
    assert not (new_catalog.parent / sp03.WORK_DIR).exists()
    assert (old_work / "result.txt").read_text() == "status=ok\n"
    with pytest.raises(FileExistsError):
        clone_tool.clone(private_root=root, source_name="SP_01_AUTO_RETRY_01",
                         dest_name="SP_01_AUTO_LEAK_01")


def test_sdk_worker_explicitly_changes_only_b_copy_and_requires_full_fingerprint():
    from pathlib import Path
    plugin = (Path(__file__).resolve().parents[2] /
              "integrations/lightroom_classic/spauto03/ProGrapherCounterfactual.lrdevplugin")
    worker = (plugin / "SpAuto03Worker.lua").read_text(encoding="utf-8")
    info = (plugin / "Info.lua").read_text(encoding="utf-8")
    assert "SP_01_AUTO_LEAK_01.lrcat" in worker
    assert "SP_03_BRIDGE" in worker
    assert "LrForceInitPlugin = true" in info
    assert "copyB:applyDevelopSettings(" in worker
    assert "master:applyDevelopSettings(" not in worker
    assert "master:applyDevelopPreset(" not in worker
    assert "catalog:withWriteAccessDo(" in worker
    assert "copyA = createCopy(" in worker and "copyB = createCopy(" in worker
    assert "beforeB == beforeA" in worker
    assert "neutralA ~= neutralB" in worker
    assert "resetExportOne(copyA" in worker and "resetExportOne(copyB" in worker
    assert "LrDevelopController.resetAllDevelopAdjustments()" in worker
    assert "fingerprint(master) ~= originalFingerprint" in worker
    assert "#allPhotos ~= 1" in worker
    assert "deleteSmartPreview(" not in worker
    assert "LrFileUtils.delete(" not in worker
