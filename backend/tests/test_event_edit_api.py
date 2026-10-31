"""Event-edit HTTP API on a synthetic catalog: dry run first, explicit confirm, background job polling."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.test_event_edit_service import _build, _digest

HEADERS = {"X-ProGrapher-Secret": "pg-event-edit-api-test-secret"}


@pytest.fixture(autouse=True)
def _private_data_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))


def _wait(client, job_id: str, until=("planned", "completed", "failed", "outdated", "interrupted")) -> dict:
    for _ in range(200):
        job = client.get(f"/api/event-edit/jobs/{job_id}", headers=HEADERS).json()
        if job["status"] in until:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job stuck: {job}")


def test_api_requires_a_dry_run_and_an_explicit_confirmation(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.application import create_app

    (tmp_path / "cat").mkdir()
    catalog = _build(tmp_path / "cat" / "Studio.lrcat", {"EventA": 30, "EventB": 9})
    with TestClient(create_app()) as client:
        folders = client.post("/api/event-edit/folders", json={"catalog_path": str(catalog)}, headers=HEADERS).json()
        keys = [f["key"] for f in folders["folders"] if f["label"].endswith("EventA")]
        assert client.post("/api/event-edit/plan/anchors", json={"catalog_path": str(catalog), "folder_keys": []},
                           headers=HEADERS).status_code == 422  # no event chosen
        before = _digest(catalog)
        job = client.post("/api/event-edit/plan/anchors", json={"catalog_path": str(catalog), "folder_keys": keys},
                          headers=HEADERS).json()
        planned = _wait(client, job["job_id"])
        assert planned["status"] == "planned" and planned["plan"]["anchor_count"] == 10
        assert _digest(catalog) == before  # the dry run wrote nothing
        missing = client.post(f"/api/event-edit/jobs/{job['job_id']}/confirm", json={}, headers=HEADERS)
        assert missing.status_code == 422  # confirmation must be explicit
        assert _digest(catalog) == before
        ok = client.post(f"/api/event-edit/jobs/{job['job_id']}/confirm", json={"confirm": True}, headers=HEADERS)
        assert ok.status_code == 200
        done = _wait(client, job["job_id"], until=("completed", "failed"))
        assert done["status"] == "completed" and done["result"]["marked"] == 10
        twice = client.post(f"/api/event-edit/jobs/{job['job_id']}/confirm", json={"confirm": True}, headers=HEADERS)
        assert twice.status_code == 422
