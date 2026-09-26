from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase6-test-secret"

from app.application import create_app  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "phase6-test-secret"}


def _jpeg(size: int = 900) -> bytes:
    payload = b"A" * size
    marker_size = len(payload) + 2
    return (
        b"\xff\xd8\xff\xfe"
        + marker_size.to_bytes(2, "big")
        + payload
        + b"\xff\xd9"
    )


def test_preview_reads_embedded_jpeg_without_changing_raw(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event = tmp_path / "event"
    event.mkdir()
    raw_path = event / "IMG_0001.ARW"
    preview = _jpeg()
    raw_path.write_bytes(b"RAWHEAD" + preview + b"RAWTAIL")
    original = raw_path.read_bytes()

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]
        listed = client.get(
            f"/api/events/{event_id}/files",
            headers=HEADERS,
        )
        fingerprint = listed.json()["files"][0]["fingerprint"]
        response = client.get(
            f"/api/events/{event_id}/files/{fingerprint}/preview",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content.startswith(b"\xff\xd8")
    assert raw_path.read_bytes() == original


def test_preview_rejects_unknown_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event = tmp_path / "event"
    event.mkdir()
    (event / "IMG_0001.ARW").write_bytes(b"raw" * 400)

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        event_id = opened.json()["event"]["id"]
        response = client.get(
            f"/api/events/{event_id}/files/missing/preview",
            headers=HEADERS,
        )

    assert response.status_code == 404

def test_preview_serves_real_jpeg_bytes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event = tmp_path / "jpeg-event"
    event.mkdir()
    jpeg_path = event / "IMG_0100.jpg"
    jpeg = _jpeg(1200)
    jpeg_path.write_bytes(jpeg)

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]
        listed = client.get(
            f"/api/events/{event_id}/files",
            headers=HEADERS,
        )
        fingerprint = listed.json()["files"][0]["fingerprint"]
        response = client.get(
            f"/api/events/{event_id}/files/{fingerprint}/preview",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert response.content == jpeg

