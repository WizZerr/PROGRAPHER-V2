"""SP-AUTO-03B: synthetic crop-controlled four-render counterfactual checks.

Only synthetic random pixels and catalog bytes; never access real research data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto03b as experiment
from app.lightroom_bridge import sp_auto01_retry_setup as clone_tool


def private_layout(tmp_path):
    root = tmp_path / experiment.RESEARCH_NAME
    catalog = root / experiment.CATALOG_DIR
    catalog.mkdir(parents=True)
    (catalog / experiment.CATALOG_FILE).write_bytes(b"synthetic clean catalog" * 100)
    (catalog / experiment.SMART_DIR).mkdir()
    return root, catalog


def complete_case(tmp_path, *, pre_equal=False, post_diff=False, geo_mismatch=False):
    root, catalog = private_layout(tmp_path)
    work = experiment.prepare(root_override=root).parent
    seed = np.random.default_rng(917)
    unperturbed = seed.integers(0, 256, (160, 120, 3), dtype=np.uint8)
    perturbed = unperturbed.copy()
    if not pre_equal:
        perturbed[25:140, 30:105, :] = 255 - perturbed[25:140, 30:105, :]
    if geo_mismatch:
        perturbed = perturbed[4:-4, 4:-4]
    baseline = seed.integers(0, 256, (384, 256, 3), dtype=np.uint8)
    post_b = baseline.copy()
    if post_diff:
        post_b[14:35, 18:30] = 0
    for name, array in (("U", unperturbed), ("P", perturbed),
                        ("A", baseline), ("B", post_b)):
        Image.fromarray(array).save(work / "exports" / name / "test.jpg",
                                    format="JPEG", quality=95)
    job = experiment.earlier._fields(work / "job.txt")
    fields = {
        "status": "ok", "job_id": job["job_id"],
        "jpeg_a": str(work / "exports" / "A" / "test.jpg"),
        "jpeg_b": str(work / "exports" / "B" / "test.jpg"),
        "jpeg_perturbed": str(work / "exports" / "P" / "test.jpg"),
        "jpeg_unperturbed": str(work / "exports" / "U" / "test.jpg"),
        "master_uuid": "synthetic-master",
        "copy_a_uuid": "synthetic-copy-a",
        "copy_b_uuid": "synthetic-copy-b",
        "target_fingerprint_unchanged": "true",
        "pre_reset_variants_distinct": "true",
        "post_reset_full_develop_equal": "true",
        "post_reset_exposure_a": "0",
        "post_reset_exposure_b": "0",
        "post_reset_uncropped_a": "true",
        "post_reset_uncropped_b": "true",
        "source_raw_offline": "true",
        "smart_preview_present": "true",
    }
    (work / "result.txt").write_text(
        "".join(f"{key}={value}\n" for key, value in fields.items()),
        encoding="utf-8",
    )
    return root, work, fields


def test_controlled_pre_reset_geometry_can_differ_from_post_reset(tmp_path):
    root, work, fields = complete_case(tmp_path)
    ok, reason, report = experiment.verify(root_override=root)
    assert ok is True
    assert reason == "PASS_CROP_CONTROLLED_VC_RESET_INVARIANCE_NOT_BAKE_FREE"
    assert report["perturbation_dimensions_match"] is True
    assert report["perturbed_dimensions"] == report["neutral_dimensions"]
    assert report["perturbed_pixels_differ_from_reset_baseline"] is True
    assert report["counterfactual_perturbation_mean_absolute_rgb_difference_8bit"] > 0
    assert report["all_decoded_rgb_pixels_equal"] is True
    assert report["mean_absolute_rgb_difference_8bit"] == 0
    assert report["training_ready"] is False
    # Same controlled pre-reset crop, different post-reset resolution.
    from PIL import Image as PImage
    with PImage.open(work / "exports" / "U" / "test.jpg") as u:
        with PImage.open(work / "exports" / "A" / "test.jpg") as a:
            assert u.size != a.size


def test_no_perturbation_detected_fail_closed(tmp_path):
    root, _, _ = complete_case(tmp_path, pre_equal=True)
    ok, reason, report = experiment.verify(root_override=root)
    assert ok is False
    assert reason == "PERTURBATION_DID_NOT_CHANGE_RENDER"
    assert report["training_ready"] is False


def test_unmatched_pre_reset_crop_is_not_interpreted_as_no_effect(tmp_path):
    root, _, _ = complete_case(tmp_path, geo_mismatch=True)
    ok, reason, report = experiment.verify(root_override=root)
    assert ok is False
    assert reason == "PRE_RESET_CONTROL_GEOMETRY_MISMATCH"
    assert report["perturbation_dimensions_match"] is False


def test_identical_pre_reset_control_does_not_hide_bad_post_reset(tmp_path):
    root, _, _ = complete_case(tmp_path, post_diff=True)
    ok, reason, report = experiment.verify(root_override=root)
    assert ok is False
    assert reason == "COUNTERFACTUAL_RENDER_MISMATCH"
    assert report["training_ready"] is False


@pytest.mark.parametrize("key,value", [
    ("target_fingerprint_unchanged", "false"),
    ("pre_reset_variants_distinct", "false"),
    ("post_reset_full_develop_equal", "false"),
    ("post_reset_uncropped_a", "false"),
    ("source_raw_offline", "false"),
    ("smart_preview_present", "false"),
    ("copy_b_uuid", "synthetic-copy-a"),
    ("post_reset_exposure_b", "1.2"),
])
def test_fails_closed_on_required_sdk_guard(tmp_path, key, value):
    root, work, state = complete_case(tmp_path)
    state[key] = value
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in state.items()), encoding="utf-8"
    )
    ok, *_ = experiment.verify(root_override=root)
    assert ok is False


def test_one_shot_private_prepare(tmp_path):
    root, catalog = private_layout(tmp_path)
    created = experiment.prepare(root_override=root)
    assert created.name == "job.txt"
    assert {path.name for path in (created.parent / "exports").iterdir()} == {
        "U", "P", "A", "B"
    }
    assert (catalog / experiment.CATALOG_FILE).is_file()
    with pytest.raises(FileExistsError):
        experiment.prepare(root_override=root)


def test_rejects_redirected_image_path(tmp_path):
    root, work, state = complete_case(tmp_path)
    state["jpeg_unperturbed"] = state["jpeg_perturbed"]
    (work / "result.txt").write_text(
        "".join(f"{key}={value}\n" for key, value in state.items()),
        encoding="utf-8",
    )
    ok, reason, _ = experiment.verify(root_override=root)
    assert ok is False and reason == "INVALID_OR_REDIRECTED_JPEG"


def test_retry_uses_new_isolated_catalog_only(tmp_path):
    root = tmp_path / clone_tool.ROOT_NAME
    source = root / clone_tool.PARENT / "SP_01_AUTO_RETRY_01"
    source.mkdir(parents=True)
    (source / "SP_01_AUTO_RETRY_01.lrcat").write_bytes(
        b"synthetic clean Lightroom catalog" * 100
    )
    store = source / "SP_01_AUTO_RETRY_01 Smart Previews.lrdata"
    store.mkdir()
    (store / "preview.dng").write_bytes(b"synthetic lossy DNG" * 64)
    original_old = source / "SP_01_AUTO_BRIDGE"
    original_old.mkdir()
    (original_old / "result.txt").write_text("status=ok\n")
    dest = clone_tool.clone(private_root=root, source_name="SP_01_AUTO_RETRY_01",
                            dest_name="SP_01_AUTO_LEAK_02")
    assert dest.name == experiment.CATALOG_FILE
    assert (dest.parent / "SP_01_AUTO_LEAK_02 Smart Previews.lrdata" /
            "preview.dng").is_file()
    assert not (dest.parent / "SP_01_AUTO_BRIDGE").exists()
    assert not (dest.parent / experiment.WORK_DIR).exists()
    assert (original_old / "result.txt").read_text() == "status=ok\n"
    with pytest.raises(FileExistsError):
        clone_tool.clone(private_root=root, source_name="SP_01_AUTO_RETRY_01",
                         dest_name="SP_01_AUTO_LEAK_02")


def test_worker_exports_U_before_B_perturbation_and_preserves_master():
    plugin = (Path(__file__).resolve().parents[2] /
              "integrations/lightroom_classic/spauto03b" /
              "ProGrapherCounterfactualV2.lrdevplugin")
    worker = (plugin / "SpAuto03BWorker.lua").read_text(encoding="utf-8")
    info = (plugin / "Info.lua").read_text(encoding="utf-8")
    assert "SP_01_AUTO_LEAK_02.lrcat" in worker
    assert "SP_03B_BRIDGE" in worker
    assert "spauto03b-1" in worker
    assert "LrForceInitPlugin = true" in info
    assert "#allPhotos ~= 1" in worker
    assert "copyB:applyDevelopSettings(" in worker
    assert "master:applyDevelopSettings(" not in worker
    assert "catalog:withWriteAccessDo(" in worker
    assert "local function exportOne(" in worker
    assert worker.count("local function exportOne(") == 1
    assert worker.index("jpegUnperturbed = exportOne(copyA, exportU") < worker.index(
        "stage = 'perturb_copy_b'"
    ) < worker.index("jpegPerturbed = exportOne(copyB, exportP")
    assert "neutralA ~= neutralB" in worker
    assert "fingerprint(master) ~= originalFingerprint" in worker
