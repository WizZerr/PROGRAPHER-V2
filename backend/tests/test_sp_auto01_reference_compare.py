"""SP-AUTO-01 synthetic reference comparison tests; no real Lightroom files."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image
import pytest

from app.lightroom_bridge import sp_auto01 as bridge
from app.lightroom_bridge import sp_auto01_reference_compare as reference


def _fixture(tmp_path, *, change_manual=False, manual_size=None):
    root = tmp_path / bridge.RESEARCH_NAME
    catalog = root / bridge.CATALOG_PARENT
    catalog.mkdir(parents=True)
    (catalog / bridge.CATALOG_NAME).write_bytes(b"private test catalog" * 200)
    (catalog / bridge.PREVIEW_NAME).mkdir()
    job_path = bridge.prepare(root_override=root)
    job = bridge._fields(job_path)
    output = job_path.parent
    src = output / "exports" / "auto.jpg"
    manual = root / reference.MANUAL_RELATIVE
    manual.parent.mkdir(parents=True)
    rng = np.random.default_rng(222)
    img = rng.integers(0, 255, (128, 128, 3), dtype=np.uint8)
    Image.fromarray(img).save(src, "JPEG", quality=95)
    ref = img.copy()
    if change_manual:
        ref[:64, :64, :] = 0
    if manual_size:
        ref = ref[:manual_size[1], :manual_size[0], :]
    Image.fromarray(ref).save(manual, "JPEG", quality=95)

    target = output / "master_target_PRIVATE.txt"
    target.write_text(
        "schema=prographer.spauto01.master_target.v0\n"
        f"job_id={job['job_id']}\n"
        "master_uuid=master_reference\n"
        "photographer_target_training_approved=false\n"
        "full_develop_serialized_PRIVATE=" + "target_NEVER_SOURCE_" * 32 + "\n",
        encoding="utf-8",
    )
    data = {
        "status": "ok", "job_id": job["job_id"],
        "jpeg": str(src), "bytes": str(src.stat().st_size),
        "master_uuid": "master_reference", "copy_uuid": "virtual_copy",
        "raw_offline": "true", "smart_preview": "true",
        "master_develop_unchanged": "true",
        "neutral_exposure": "0.0", "neutral_cropped": "false",
        "target_snapshot": str(target),
    }
    (output / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in data.items()), encoding="utf-8"
    )
    assert bridge.verify(root_override=root)[0] is True
    return root, output, src, manual, target


def test_identical_reference_comparison_is_candidate_only(tmp_path):
    root, work, src, manual, target = _fixture(tmp_path)
    original = [x.read_bytes() for x in (src, manual, target)]
    result = reference.compare_verified_auto_to_manual(root_override=root)
    assert result["dimensions_match"] is True
    assert result["decoded_rgb_pixels_match"] is True
    assert result["mean_absolute_rgb_difference_8bit"] == 0
    assert result["render_equivalence_if_identical"] == "CANDIDATE_SAME_RENDER"
    assert result["no_leakage_proven"] is False
    assert result["training_ready"] is False
    assert original == [x.read_bytes() for x in (src, manual, target)]
    report = (work / reference.REPORT_DIR / reference.REPORT_NAME).read_text()
    assert str(src) not in report and str(manual) not in report
    assert "master_reference" not in report and "target_NEVER_SOURCE_" not in report
    assert json.loads(report)["decoded_rgb_pixels_match"] is True


def test_different_pixels_are_not_reported_as_same_render(tmp_path):
    root, _work, _src, _manual, _target = _fixture(tmp_path, change_manual=True)
    outcome = reference.compare_verified_auto_to_manual(root_override=root)
    assert outcome["decoded_rgb_pixels_match"] is False
    assert outcome["mean_absolute_rgb_difference_8bit"] > 0
    assert outcome["render_equivalence_if_identical"] == "REVIEW_EXPORT_POLICY_OR_BASELINE"


def test_mismatched_dimensions_fail_render_equivalence(tmp_path):
    root, _work, _src, _manual, _target = _fixture(tmp_path, manual_size=(120, 120))
    outcome = reference.compare_verified_auto_to_manual(root_override=root)
    assert outcome["dimensions_match"] is False
    assert outcome["decoded_rgb_pixels_match"] is False
    assert outcome["mean_absolute_rgb_difference_8bit"] is None


def test_no_overwrite_reference_evidence(tmp_path):
    root, work, _, _, _ = _fixture(tmp_path)
    reference.compare_verified_auto_to_manual(root_override=root)
    previous = (work / reference.REPORT_DIR / reference.REPORT_NAME).read_bytes()
    with pytest.raises(FileExistsError):
        reference.compare_verified_auto_to_manual(root_override=root)
    assert (work / reference.REPORT_DIR / reference.REPORT_NAME).read_bytes() == previous


def test_bridge_failure_blocks_comparison(tmp_path):
    root, work, _, _, _ = _fixture(tmp_path)
    state = bridge._fields(work / "result.txt")
    state["master_develop_unchanged"] = "false"
    (work / "result.txt").write_text(
        "".join(f"{k}={v}\n" for k, v in state.items()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unverified"):
        reference.compare_verified_auto_to_manual(root_override=root)
    assert not (work / reference.REPORT_DIR).exists()


def test_missing_reference_blocks_without_creating_result(tmp_path):
    root, work, _, manual, _ = _fixture(tmp_path)
    manual.unlink()
    with pytest.raises(ValueError, match="manual reference"):
        reference.compare_verified_auto_to_manual(root_override=root)
    assert not (work / reference.REPORT_DIR).exists()
