"""SP-AUTO-02 one-command synthetic research orchestration tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.lightroom_bridge import sp_auto01
from app.lightroom_bridge import sp_auto01_retry_setup as setup
from app.lightroom_bridge import sp_auto02_one_command as e2e


def _environment(tmp_path):
    root = tmp_path / sp_auto01.RESEARCH_NAME
    catalog_dir = root / sp_auto01.CATALOG_PARENT
    catalog_dir.mkdir(parents=True)
    (catalog_dir / sp_auto01.CATALOG_NAME).write_bytes(b"fake catalog" * 200)
    (catalog_dir / sp_auto01.PREVIEW_NAME).mkdir()
    return root, catalog_dir, catalog_dir / sp_auto01.WORK_NAME


def test_one_command_runs_all_stages_exactly_once_and_no_training(tmp_path, monkeypatch):
    root, cat, work = _environment(tmp_path)
    calls = []
    orig_prepare = sp_auto01.prepare

    def prepare(*, root_override=None):
        calls.append("prepare")
        return orig_prepare(root_override=root_override)

    def await_one(working, **kwargs):
        calls.append("poll")
        assert working == work
        assert (work / "result.txt").exists()
        return "ok"

    def verify(*, root_override=None):
        calls.append("verify")
        return True, "PASS_ONE_PHOTO_DISPOSABLE_CATALOG_ONLY_NO_TRAINING"

    def post(*, predictor=None, root_override=None):
        calls.append("source-only-model")
        assert predictor == "fake-local-clip"
        return {"analyzed": 1, "scene_status": "ZERO_SHOT_UNCALIBRATED_HUMAN_REVIEW_REQUIRED", "scene_abstained": True}

    def compare(*, root_override=None):
        calls.append("render")
        return {"dimensions_match": True, "decoded_rgb_pixels_match": False, "mean_absolute_rgb_difference_8bit": 0.048043}

    def forensic(*, root_override=None):
        calls.append("encoding")
        return {"diagnostic_status": "COMPLETED_CAUSE_NOT_PROVEN",
                "jpeg_quantization_tables_match": False,
                "jpeg_chroma_subsampling_match": True}

    monkeypatch.setattr(sp_auto01, "prepare", prepare)
    monkeypatch.setattr(sp_auto01, "verify", verify)
    monkeypatch.setattr(e2e, "wait_for_bridge", await_one)
    monkeypatch.setattr(e2e.postprocess, "analyze_completed_job", post)
    monkeypatch.setattr(e2e.reference, "compare_verified_auto_to_manual", compare)
    monkeypatch.setattr(e2e.forensics, "run", forensic)
    report = e2e.run_pipeline(predictor="fake-local-clip", root_override=root)
    assert calls == ["prepare", "poll", "verify", "source-only-model", "render", "encoding"]
    assert report["bridge_verified"] is True
    assert report["training_ready"] is False
    assert report["source_target_leakage_independently_proven"] is False
    assert report["photographer_target_provided_to_visual_ai"] is False
    assert report["auto_vs_manual_mae_8bit"] == 0.048043
    assert json.loads((work / e2e.SUMMARY_FILE).read_text()) == report
    with pytest.raises(FileExistsError):
        e2e.run_pipeline(predictor="fake-local-clip", root_override=root)
    assert calls == ["prepare", "poll", "verify", "source-only-model", "render", "encoding"]


def test_rejects_prior_job_before_any_side_effect(tmp_path, monkeypatch):
    root, _, work = _environment(tmp_path)
    work.mkdir()
    (work / "result.txt").write_text("status=ok\n")
    monkeypatch.setattr(sp_auto01, "prepare", lambda **kwargs: pytest.fail("should not prepare"))
    with pytest.raises(FileExistsError):
        e2e.run_pipeline(predictor=None, root_override=root)
    assert not (work / e2e.SUMMARY_FILE).exists()


def test_bridge_error_stops_before_postprocess(tmp_path, monkeypatch):
    root, _, work = _environment(tmp_path)
    monkeypatch.setattr(e2e, "wait_for_bridge", lambda *a, **kw: "error")
    monkeypatch.setattr(e2e.postprocess, "analyze_completed_job",
                        lambda **kwargs: pytest.fail("should not process failed bridge output"))
    with pytest.raises(RuntimeError, match="ERROR"):
        e2e.run_pipeline(predictor=None, root_override=root)
    assert (work / "result.txt").is_file()
    assert not (work / e2e.SUMMARY_FILE).exists()


def test_verify_failure_stops_before_ai(tmp_path, monkeypatch):
    root, _, work = _environment(tmp_path)
    monkeypatch.setattr(e2e, "wait_for_bridge", lambda *a, **kw: "ok")
    monkeypatch.setattr(sp_auto01, "verify", lambda **kw: (False, "BAD_JPEG"))
    monkeypatch.setattr(e2e.postprocess, "analyze_completed_job",
                        lambda **kwargs: pytest.fail("should not run AI on unverified JPEG"))
    with pytest.raises(RuntimeError, match="strict"):
        e2e.run_pipeline(predictor=None, root_override=root)


def test_wait_pending_then_ok_no_reprepare(tmp_path):
    path = tmp_path / "job"
    path.mkdir()
    status = path / "result.txt"
    status.write_text("status=prepared\njob_id=x\n")
    ticks = [0.0]
    polls = [0]

    def clock():
        return ticks[0]

    def pause(seconds):
        ticks[0] += seconds
        polls[0] += 1
        if polls[0] == 2:
            status.write_text("status=ok\njob_id=x\n")

    assert e2e.wait_for_bridge(path, timeout_seconds=10, poll_seconds=.1,
                                clock=clock, pause=pause) == "ok"
    assert polls[0] == 2


def test_wait_timeout_preserves_prepared_job(tmp_path):
    path = tmp_path / "job"
    path.mkdir()
    status = path / "result.txt"
    status.write_text("status=prepared\njob_id=x\n")
    ticks = [0.0]

    def pause(seconds):
        ticks[0] += seconds

    with pytest.raises(TimeoutError, match="DO NOT"):
        e2e.wait_for_bridge(path, timeout_seconds=.25, poll_seconds=.1,
                            clock=lambda: ticks[0], pause=pause)
    assert status.read_text().startswith("status=prepared")


def test_wait_rejects_unexpected_state(tmp_path):
    path = tmp_path / "job"
    path.mkdir()
    (path / "result.txt").write_text("status=invalid\n")
    with pytest.raises(ValueError, match="unexpected"):
        e2e.wait_for_bridge(path, timeout_seconds=.25, poll_seconds=.1)


def test_clone_only_explicit_research_pair(tmp_path):
    root = tmp_path / setup.ROOT_NAME
    folder = root / setup.PARENT / "SP_01_AUTO_RETRY_01"
    folder.mkdir(parents=True)
    (folder / "SP_01_AUTO_RETRY_01.lrcat").write_bytes(b"fake closed catalog" * 160)
    smart = folder / "SP_01_AUTO_RETRY_01 Smart Previews.lrdata"
    smart.mkdir()
    (smart / "preview.dat").write_bytes(b"smart" * 60)
    (folder / "SP_01_AUTO_BRIDGE").mkdir()
    (folder / "SP_01_AUTO_BRIDGE" / "result.txt").write_text("status=ok\n")
    result = setup.clone(private_root=root,
                         source_name="SP_01_AUTO_RETRY_01",
                         dest_name="SP_01_AUTO_E2E_01")
    assert result.name == "SP_01_AUTO_E2E_01.lrcat"
    assert (result.parent / "SP_01_AUTO_E2E_01 Smart Previews.lrdata" / "preview.dat").exists()
    assert not (result.parent / "SP_01_AUTO_BRIDGE").exists()
    assert (folder / "SP_01_AUTO_BRIDGE" / "result.txt").exists()
    with pytest.raises(FileExistsError):
        setup.clone(private_root=root,
                    source_name="SP_01_AUTO_RETRY_01",
                    dest_name="SP_01_AUTO_E2E_01")
    with pytest.raises(ValueError, match="unauthorized"):
        setup.clone(private_root=root, source_name="other", dest_name="SP_01_AUTO_E2E_01")
