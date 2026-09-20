from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app


TEST_SECRET = "phase8-test-secret"
HEADERS = {"X-ProGrapher-Secret": TEST_SECRET}


def test_dataset_preview_requires_auth(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", TEST_SECRET)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/dataset/preview",
            json={
                "raw_root": str(tmp_path),
                "edits_root": str(tmp_path),
                "event_id": "event",
            },
        )

    assert response.status_code == 401


def test_dataset_preview_does_not_claim_training_pairs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", TEST_SECRET)

    raw_root = tmp_path / "raw"
    edits_root = tmp_path / "edits"
    raw_root.mkdir()
    edits_root.mkdir()

    (raw_root / "IMG_0001.ARW").write_bytes(b"RAW" * 1000)
    (edits_root / "IMG_0001.xmp").write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/"
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
             <rdf:RDF><rdf:Description
               crs:Exposure2012="0"
               crs:Temperature="5000"
               crs:Tint="0" /></rdf:RDF>
           </x:xmpmeta>""",
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/dataset/preview",
            headers=HEADERS,
            json={
                "raw_root": str(raw_root),
                "edits_root": str(edits_root),
                "event_id": "event",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["matched_pairs"] == 1
    assert body["verified_training_pairs"] == 0
