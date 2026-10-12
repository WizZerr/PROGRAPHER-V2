"""Synthetic-only LB-01 tests. None of these tests run Lightroom Classic."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.lightroom_bridge import lb01_poc as bridge


@pytest.fixture
def test_root(tmp_path: Path):
    root = tmp_path / "ProGrapher_Research_Private"
    catalog = root / "ProGrapher_RAW_Test" / "ProGrapher_RAW_Test.lrcat"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"fake isolated SQLite catalog fixture")
    raw_dir = root / "RAW_Parity_Test"
    raw_dir.mkdir()
    raw = raw_dir / "fixture.CR3"
    raw.write_bytes(b"fake RAW fixture from non-photographer source")
    return root, catalog, raw


def result_file(root: Path) -> Path:
    return root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "result.txt"


def fake_success(root: Path, jpeg_bytes: bytes = b"\xff\xd8\xff" + b"x" * 2048) -> None:
    job = bridge._read_fields(root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "job.txt")
    jpeg = root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "exports" / "fixture.jpg"
    jpeg.write_bytes(jpeg_bytes)
    fields = {
        "status": "ok", "job_id": job["job_id"], "profile": job["profile"],
        **{key: job[key] for key in bridge.ADJUSTMENTS},
        "jpeg": str(jpeg), "bytes": str(len(jpeg_bytes)),
    }
    result_file(root).write_text(bridge._encode(fields), encoding="utf-8")


def test_prepare_only_research_copy_and_explicit_local_job(test_root):
    root, catalog, raw = test_root
    jobpath = bridge.prepare(research_root=root, raw_path=raw)
    fields = bridge._read_fields(jobpath)
    assert fields["catalog_path"] == str(catalog)
    assert fields["raw_path"] == str(raw)
    assert fields["raw_sha256"] == bridge._digest(raw)
    assert fields["profile"] == "Adobe Standard"
    assert len([key for key in fields if key in bridge.ADJUSTMENTS]) == 10
    assert bridge._read_fields(result_file(root))["status"] == "prepared"
    assert bridge.verify(research_root=root)[0] is False
    assert raw.read_bytes() == b"fake RAW fixture from non-photographer source"


def test_full_readback_and_jpeg_fixture_pass(test_root):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    fake_success(root)
    okay, message = bridge.verify(research_root=root)
    assert okay, message
    assert "10 Develop" in message


def test_reject_real_catalog_outside_allowlist(test_root, tmp_path):
    root, _, raw = test_root
    fake_catalog = tmp_path / "Original_Catalog.lrcat"
    fake_catalog.write_bytes(b"real photographer unsafe target")
    with pytest.raises(ValueError, match="SAFETY STOP"):
        bridge._context(tmp_path)
    extra = tmp_path / "other.CR3"
    extra.write_bytes(b"bytes")
    with pytest.raises(ValueError, match="SAFETY STOP"):
        bridge.prepare(research_root=root, raw_path=extra)
    assert not (root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "job.txt").exists()


def test_reject_duplicate_run_without_overwriting_previous_evidence(test_root):
    root, _, raw = test_root
    previous = bridge.prepare(research_root=root, raw_path=raw).read_bytes()
    with pytest.raises(FileExistsError, match="Previous LB-01 job"):
        bridge.prepare(research_root=root, raw_path=raw)
    assert (root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "job.txt").read_bytes() == previous


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 6.0, -6.0])
def test_reject_invalid_exposure(test_root, value):
    root, _, raw = test_root
    with pytest.raises(ValueError, match="Invalid exposure"):
        bridge.prepare(research_root=root, raw_path=raw, overrides={"exposure": value})


def test_reject_duplicate_and_overlarge_protocol(test_root):
    root, _, raw = test_root
    job = bridge.prepare(research_root=root, raw_path=raw)
    job.write_text(job.read_text() + "job_id=duplicate\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        bridge._read_fields(job)
    job.write_bytes(b"a" * 8193)
    with pytest.raises(ValueError, match="Oversized"):
        bridge._read_fields(job)


def test_detect_source_mutation_even_after_lightroom_reports_success(test_root):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    fake_success(root)
    raw.write_bytes(b"modified original! unacceptable")
    okay, msg = bridge.verify(research_root=root)
    assert not okay and "RAW bytes changed" in msg


def test_detect_readback_mismatch_and_stale_job_result(test_root):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    fake_success(root)
    result = result_file(root)
    result.write_text(result.read_text().replace("exposure=0.45", "exposure=2.45"))
    assert "readback mismatch" in bridge.verify(research_root=root)[1]
    result.write_text(result.read_text().replace("status=ok", "status=error").replace("job_id=", "job_id=wrong"))
    assert "stale" in bridge.verify(research_root=root)[1]


def test_reject_jpeg_outside_allowlist_and_invalid_bytes(test_root, tmp_path):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    fake_success(root)
    result = result_file(root)
    content = result.read_text()
    jpeg = root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "exports" / "fixture.jpg"
    escaped = tmp_path / "escaped.jpg"
    escaped.write_bytes(jpeg.read_bytes())
    result.write_text(content.replace(str(jpeg), str(escaped)))
    assert "outside destination" in bridge.verify(research_root=root)[1]
    result.write_text(content)
    jpeg.write_bytes(b"not a JPEG" + b"x" * 2048)
    assert "JPEG signature" in bridge.verify(research_root=root)[1]


def test_error_result_does_not_pass(test_root):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    job = bridge._read_fields(root / bridge.RAW_FOLDER / bridge.JOB_FOLDER / "job.txt")
    result_file(root).write_text(bridge._encode({"status": "error", "job_id": job["job_id"], "stage": "readback", "error": "test failure"}))
    okay, msg = bridge.verify(research_root=root)
    assert not okay and "LIGHTROOM STOPPED" in msg



def test_legacy_error_without_job_id_fails_closed(test_root):
    root, _, raw = test_root
    bridge.prepare(research_root=root, raw_path=raw)
    result_file(root).write_text("status=error\nstage=readback\nerror=example\n", encoding="utf-8")
    okay, message = bridge.verify(research_root=root)
    assert not okay and "stale result" in message


def test_sdk_error_result_correlates_only_a_validated_job():
    repo = Path(__file__).resolve().parents[2]
    source = (repo / "integrations" / "lightroom_classic" / "lb01" /
              "ProGrapherBridge.lrdevplugin" / "RunBridgeTest.lua").read_text(encoding="utf-8")
    assert source.index("local activeJobId = nil") < source.index("local function run()")
    assert source.index("activeJobId = fields.job_id") > source.index("pending.status ~= 'prepared'")
    assert source.index("activeJobId = fields.job_id") < source.index("stage='apply_recipe'")
    assert "if activeJobId then" in source
    assert "writeResult('status=error\\njob_id='..activeJobId" in source
    assert "activeJobId = nil -- success is terminal" in source

def test_sdk_source_guard_static_and_no_personal_filenames():
    repo = Path(__file__).resolve().parents[2]
    plugin = repo / "integrations" / "lightroom_classic" / "lb01" / "ProGrapherBridge.lrdevplugin"
    source = (plugin / "RunBridgeTest.lua").read_text(encoding="utf-8")
    assert "LrTasks.pcall(run)" in source
    assert "catalog:getPath()" in source
    assert "catalog:findPhotoByPath" in source
    assert "photo:applyDevelopSettings" in source
    assert "photo:getDevelopSettings" in source
    assert "LrExportSession" in source
    assert "SAFETY STOP" in source
    assert "LrDevelopController" not in source
    assert re.search(r"[A-Za-z0-9]{6,}\.CR3", source, re.IGNORECASE) is None
    assert "Downloads" not in source
    assert re.search(r"raw_sha256", source)
