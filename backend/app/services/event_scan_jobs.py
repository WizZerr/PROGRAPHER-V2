from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from app.catalog.event_store import EventOpenResult, EventStore
from app.ingest.scanner import scan_event_folder


@dataclass(frozen=True)
class EventScanJob:
    id: str
    path: str
    name: str | None
    status: str  # discovering | scanning | finalizing | completed | failed
    processed_files: int
    total_files: int
    current_file: str
    error: str | None
    result: EventOpenResult | None


_jobs: dict[str, EventScanJob] = {}
_lock = threading.Lock()


def _put(job: EventScanJob) -> None:
    with _lock:
        _jobs[job.id] = job


def _update(job_id: str, **changes) -> EventScanJob:
    with _lock:
        current = _jobs[job_id]
        updated = replace(current, **changes)
        _jobs[job_id] = updated
        return updated


def get_scan_job(job_id: str) -> EventScanJob | None:
    with _lock:
        return _jobs.get(job_id)


def _run_scan(job_id: str) -> None:
    job = get_scan_job(job_id)
    if job is None:
        return

    def progress(processed: int, total: int, current_file: str) -> None:
        _update(
            job_id,
            status="scanning",
            processed_files=processed,
            total_files=total,
            current_file=current_file,
        )

    try:
        sources = scan_event_folder(job.path, progress_callback=progress)

        _update(
            job_id,
            status="finalizing",
            processed_files=len(sources),
            total_files=len(sources),
            current_file="",
        )

        root = Path(job.path).expanduser().resolve(strict=True)
        result = EventStore().open_folder(root, sources, name=job.name)

        _update(
            job_id,
            status="completed",
            processed_files=len(sources),
            total_files=len(sources),
            current_file="",
            result=result,
        )
    except Exception as exc:
        # A background job must never die silently and leave the UI polling
        # forever at 100%.
        _update(
            job_id,
            status="failed",
            current_file="",
            error=str(exc) or "קליטת האירוע נכשלה.",
        )


def start_scan_job(path: str, name: str | None = None) -> EventScanJob:
    root = Path(path).expanduser()
    if not root.exists():
        raise ValueError("תיקיית האירוע לא קיימת.")
    if not root.is_dir():
        raise ValueError("הנתיב שנבחר אינו תיקייה.")

    job = EventScanJob(
        id=uuid.uuid4().hex,
        path=str(root),
        name=name,
        status="discovering",
        processed_files=0,
        total_files=0,
        current_file="",
        error=None,
        result=None,
    )
    _put(job)

    thread = threading.Thread(
        target=_run_scan,
        args=(job.id,),
        name=f"prographer-scan-{job.id[:8]}",
        daemon=True,
    )
    thread.start()

    return job
