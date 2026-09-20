from pathlib import Path

from fastapi.testclient import TestClient

from app.application import create_app


TEST_SECRET = "phase8-part2-secret"
HEADERS = {"X-ProGrapher-Secret": TEST_SECRET}


def test_manifest_endpoint_keeps_unreviewed_pair_out_of_training(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_ENGINE_SECRET", TEST_SECRET)

    raw = tmp_path / "raw"
    edits = tmp_path / "edits"
    raw.mkdir()
    edits.mkdir()

    (raw / "IMG_0001.CR3").write_bytes(b"RAW" * 1000)
    (edits / "IMG_0001.xmp").write_text(
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
            "/api/dataset/manifest",
            headers=HEADERS,
            json={
                "raw_root": str(raw),
                "edits_root": str(edits),
                "event_id": "event",
                "decisions": [],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["matched_pairs"] == 1
    assert body["verified_training_pairs"] == 0
    assert body["excluded_pairs"] == 1
