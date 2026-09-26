from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase6-test-secret"

from app.application import create_app  # noqa: E402
from app.preview.embedded_jpeg import extract_embedded_jpeg  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "phase6-test-secret"}


def _jpeg(width: int = 320, height: int = 240, value: int = 120) -> bytes:
    image = np.full((height, width, 3), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )
    assert ok
    return encoded.tobytes()


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


def test_embedded_preview_prefers_larger_decodable_jpeg(tmp_path: Path) -> None:
    raw_path = tmp_path / "IMG_0002.DNG"
    small = _jpeg(160, 120, 40)
    large = _jpeg(1280, 853, 180)
    raw_path.write_bytes(b"HEAD" + small + b"MIDDLE" + large + b"TAIL")

    selected = extract_embedded_jpeg(raw_path)

    assert selected is not None
    image = cv2.imdecode(np.frombuffer(selected, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape[1] == 1280
    assert image.shape[0] == 853


def test_embedded_preview_ignores_broken_jpeg_markers(tmp_path: Path) -> None:
    raw_path = tmp_path / "IMG_0003.DNG"
    broken = b"\xff\xd8\xff" + (b"garbage" * 200) + b"\xff\xd9"
    valid = _jpeg(640, 480)
    raw_path.write_bytes(broken + b"MIDDLE" + valid)

    selected = extract_embedded_jpeg(raw_path)

    assert selected is not None
    image = cv2.imdecode(np.frombuffer(selected, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape[1] == 640
    assert image.shape[0] == 480


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
    jpeg = _jpeg(640, 480)
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
