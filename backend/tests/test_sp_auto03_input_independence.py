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
    for name in ("A", "B", "P"):
        arr = target.copy()
        if name == "P" or (variant and name == "B"):
            arr[40:80, 40:80] = 0
        Image.fromarray(arr).save(work / "exports" / name / "render.jpg",
                                  format="JPEG", quality=95)
    values = {
        "status": "ok", "job_id": fields["job_id"],
        "jpeg_a": str(work / "exports" / "A" / "render.jpg"),
        "jpeg_b": str(work / "exports" / "B" / "render.jpg"),
        "jpeg_perturbed": str(work / "exports" / "P" / "render.jpg"),
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
    assert (prepared.parent / "exports" / "P").is_dir()
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
    assert safe["perturbed_pixels_differ_from_reset_baseline"] is True
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
    assert "exportOne(copyB, exportP" in worker
    assert "LrDevelopController.resetAllDevelopAdjustments()" in worker
    assert "fingerprint(master) ~= originalFingerprint" in worker
    assert "#allPhotos ~= 1" in worker
    assert "deleteSmartPreview(" not in worker
    assert "LrFileUtils.delete(" not in worker

def test_fails_if_perturbation_export_did_not_change_pixels(tmp_path):
    root, _, work, fields = _completed(tmp_path)
    source = work / "exports" / "A" / "render.jpg"
    perturbed = work / "exports" / "P" / "render.jpg"
    perturbed.write_bytes(source.read_bytes())
    ok, status, evidence = sp03.verify(root_override=root)
    assert ok is False
    assert status == "PERTURBATION_DID_NOT_CHANGE_RENDER"
    assert evidence["perturbed_pixels_differ_from_reset_baseline"] is False
    assert evidence["training_ready"] is False


def _smart_dng_clone_layout(tmp_path, *, bad_raw=None):
    root = tmp_path / clone_tool.ROOT_NAME
    source = root / clone_tool.PARENT / "SP_01_AUTO_RETRY_01"
    source.mkdir(parents=True)
    (source / "SP_01_AUTO_RETRY_01.lrcat").write_bytes(b"synthetic clean catalog" * 150)
    previews = source / "SP_01_AUTO_RETRY_01 Smart Previews.lrdata"
    (previews / "0" / "00").mkdir(parents=True)
    (previews / "0" / "00" / "LOSSY_PREVIEW_BLOCK.dng").write_bytes(b"synthetic lossy smart preview" * 50)
    meta = source / "SP_01_AUTO_RETRY_01.lrcat-data"
    meta.mkdir()
    (meta / "mask-data.bin").write_bytes(b"synthetic metadata" * 80)
    if bad_raw:
        folder = previews if bad_raw[0] == "preview" else meta
        (folder / bad_raw[1]).write_bytes(b"synthetic copied original raw" * 40)
    return root, source


def test_clone_permits_lossy_dng_only_inside_smart_preview_store(tmp_path):
    root, source = _smart_dng_clone_layout(tmp_path)
    out = clone_tool.clone(
        private_root=root,
        source_name="SP_01_AUTO_RETRY_01",
        dest_name="SP_01_AUTO_LEAK_01",
    )
    preview = out.parent / "SP_01_AUTO_LEAK_01 Smart Previews.lrdata"
    assert (preview / "0" / "00" / "LOSSY_PREVIEW_BLOCK.dng").is_file()
    assert out.read_bytes() == (source / "SP_01_AUTO_RETRY_01.lrcat").read_bytes()
    assert not (out.parent / clone_tool.SOURCE).exists()


@pytest.mark.parametrize("folder,filename", [
    ("metadata", "original.dng"),
    ("metadata", "original.CR3"),
    ("preview", "original.CR3"),
])
def test_disallows_original_raw_outside_smart_dng_exception(tmp_path, folder, filename):
    root, _ = _smart_dng_clone_layout(tmp_path, bad_raw=(folder, filename))
    with pytest.raises(ValueError, match="original RAW"):
        clone_tool.clone(
            private_root=root, source_name="SP_01_AUTO_RETRY_01",
            dest_name="SP_01_AUTO_LEAK_01"
        )
    assert not (root / clone_tool.PARENT / "SP_01_AUTO_LEAK_01").exists()
    assert (root / clone_tool.PARENT / "SP_01_AUTO_LEAK_01.STAGING").is_dir()


def test_safe_finalize_of_exact_existing_dng_staging(tmp_path):
    root, source = _smart_dng_clone_layout(tmp_path)
    result = clone_tool.clone(private_root=root,
                              source_name="SP_01_AUTO_RETRY_01",
                              dest_name="SP_01_AUTO_LEAK_01")
    dest = result.parent
    staging = dest.with_name(dest.name + ".STAGING")
    dest.rename(staging)
    # Preserve/inspect the existing work rather than deleting or recopying it.
    final = clone_tool.finalize_leakage_staging(private_root=root)
    assert final == result and final.is_file()
    assert not staging.exists()
    assert (source / "SP_01_AUTO_RETRY_01.lrcat").is_file()
    assert (final.parent / "SP_01_AUTO_LEAK_01 Smart Previews.lrdata" /
            "0" / "00" / "LOSSY_PREVIEW_BLOCK.dng").is_file()
    with pytest.raises(FileExistsError):
        clone_tool.finalize_leakage_staging(private_root=root)


def test_tampered_staging_cannot_be_finalized(tmp_path):
    root, source = _smart_dng_clone_layout(tmp_path)
    result = clone_tool.clone(private_root=root,
                              source_name="SP_01_AUTO_RETRY_01",
                              dest_name="SP_01_AUTO_LEAK_01")
    dest = result.parent
    staging = dest.with_name(dest.name + ".STAGING")
    dest.rename(staging)
    preview = (staging / "SP_01_AUTO_LEAK_01 Smart Previews.lrdata" /
               "0" / "00" / "LOSSY_PREVIEW_BLOCK.dng")
    preview.write_bytes(b"tampered staging contents")
    with pytest.raises(ValueError, match="checksum mismatch"):
        clone_tool.finalize_leakage_staging(private_root=root)
    assert staging.is_dir()  # Forensic evidence must not be deleted.
    assert not dest.exists()


def test_no_existing_staging_no_finalization_or_copy(tmp_path):
    root, _ = _smart_dng_clone_layout(tmp_path)
    with pytest.raises(FileNotFoundError):
        clone_tool.finalize_leakage_staging(private_root=root)
    assert not (root / clone_tool.PARENT / "SP_01_AUTO_LEAK_01").exists()
    assert not (root / clone_tool.PARENT / "SP_01_AUTO_LEAK_01.STAGING").exists()


def test_staging_with_unexpected_file_is_blocked_without_cleanup(tmp_path):
    root, _ = _smart_dng_clone_layout(tmp_path)
    result = clone_tool.clone(private_root=root,
                              source_name="SP_01_AUTO_RETRY_01",
                              dest_name="SP_01_AUTO_LEAK_01")
    dest = result.parent
    staging = dest.with_name(dest.name + ".STAGING")
    dest.rename(staging)
    (staging / "unexpected.txt").write_text("not authorized")
    with pytest.raises(ValueError, match="unexpected/missing staging"):
        clone_tool.finalize_leakage_staging(private_root=root)
    assert staging.exists() and not dest.exists()


def test_cropped_pre_reset_render_is_uncomparable_not_no_perturbation(tmp_path):
    root, _, work, _ = _completed(tmp_path)
    # Simulate a historically cropped VC: before-reset P dimensions differ,
    # while both post-reset (uncropped) neutral renders match pixel-perfect.
    preview = work / "exports" / "P" / "render.jpg"
    with Image.open(preview) as img:
        img.crop((8, 8, img.width - 8, img.height - 8)).save(
            preview, format="JPEG", quality=95
        )
    ok, reason, report = sp03.verify(root_override=root)
    assert ok is False
    assert reason == "PERTURBATION_DIMENSIONS_MISMATCH_NOT_COMPARABLE"
    assert report["perturbation_dimensions_match"] is False
    assert report["counterfactual_perturbation_mean_absolute_rgb_difference_8bit"] is None
    assert report["all_decoded_rgb_pixels_equal"] is True
    assert report["mean_absolute_rgb_difference_8bit"] == 0
    assert report["training_ready"] is False
