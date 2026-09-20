from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase6-test-secret"

from app.application import create_app  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "phase6-test-secret"}


def test_events_api_requires_auth(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))

    with TestClient(create_app()) as client:
        response = client.get("/api/events")

    assert response.status_code == 401


def test_open_and_list_event_folder(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    event_dir = tmp_path / "אירוע בדיקה"
    event_dir.mkdir()
    (event_dir / "IMG_0001.ARW").write_bytes(b"raw" * 500)

    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "phase6-test-secret")

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event_dir)},
        )
        listed = client.get(
            "/api/events",
            headers=HEADERS,
        )

    assert opened.status_code == 200
    assert opened.json()["event"]["raw_files"] == 1
    assert listed.status_code == 200
    assert len(listed.json()["events"]) == 1


def test_missing_folder_returns_explicit_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", "phase6-test-secret")

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(tmp_path / "does-not-exist")},
        )

    assert response.status_code == 422
    assert response.json()["detail"]
