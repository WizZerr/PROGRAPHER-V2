from __future__ import annotations

import time
from pathlib import Path

from app.services.event_scan_jobs import get_scan_job, start_scan_job


def test_progressive_scan_completes_and_reports_progress(
    tmp_path: Path,
    monkeypatch,
) -> None:
    event_dir = tmp_path / "אירוע"
    event_dir.mkdir()

    for index in range(12):
        (event_dir / f"IMG_{index:04d}.CR3").write_bytes(
            (f"RAW-{index}".encode("utf-8")) * 500
        )

    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))

    job = start_scan_job(str(event_dir))

    deadline = time.monotonic() + 5
    seen_total = 0
    seen_processed = 0

    while time.monotonic() < deadline:
        current = get_scan_job(job.id)
        assert current is not None

        seen_total = max(seen_total, current.total_files)
        seen_processed = max(seen_processed, current.processed_files)

        if current.status == "completed":
            assert current.result is not None
            assert current.result.event.raw_files == 12
            assert current.processed_files == 12
            assert current.total_files == 12
            assert seen_total == 12
            assert seen_processed <= 12
            return

        if current.status == "failed":
            raise AssertionError(current.error)

        time.sleep(0.01)

    raise AssertionError("scan job did not complete in time")
