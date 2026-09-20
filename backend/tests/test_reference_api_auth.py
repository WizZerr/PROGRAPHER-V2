from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app


TEST_SECRET = "phase8-part4-secret"
HEADERS = {"X-ProGrapher-Secret": TEST_SECRET}


def test_reference_roundtrip_requires_auth(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", TEST_SECRET)

    raw = tmp_path / "IMG.ARW"
    raw.write_bytes(b"RAW" * 100)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/reference/roundtrip",
            json={
                "raw_path": str(raw),
                "output_dir": str(tmp_path / "out"),
                "recipe": {
                    "exposure": 0,
                    "temperature": 5000,
                    "tint": 0,
                },
            },
        )

    assert response.status_code == 401


def test_reference_roundtrip_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", TEST_SECRET)

    raw = tmp_path / "IMG.ARW"
    raw.write_bytes(b"RAW" * 100)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/reference/roundtrip",
            headers=HEADERS,
            json={
                "raw_path": str(raw),
                "output_dir": str(tmp_path / "out"),
                "recipe": {
                    "exposure": 0,
                    "temperature": 5000,
                    "tint": 0,
                    "blacks": -40,
                    "process_version": "11.0",
                    "camera_profile": "Adobe Color",
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_unchanged"] is True
    assert body["recipe_matches"] is True
