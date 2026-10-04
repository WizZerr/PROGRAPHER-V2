from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "phase6-test-secret"

from app.application import create_app  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "phase6-test-secret"}


def _xmp(
    path: Path,
    *,
    exposure: str | None,
    temperature: str | None,
    tint: str | None,
    raw_name: str,
    local: bool = False,
) -> None:
    fields = []
    if exposure is not None:
        fields.append(f'crs:Exposure2012="{exposure}"')
    if temperature is not None:
        fields.append(f'crs:Temperature="{temperature}"')
    if tint is not None:
        fields.append(f'crs:Tint="{tint}"')
    fields.append('crs:ProcessVersion="15.4"')
    fields.append('crs:CameraProfile="Adobe Color"')
    fields.append(f'crs:RawFileName="{raw_name}"')
    local_xml = ""
    if local:
        local_xml = "<crs:MaskGroupBasedCorrections></crs:MaskGroupBasedCorrections>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
 <rdf:RDF>
  <rdf:Description {' '.join(fields)}>
   {local_xml}
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
""",
        encoding="utf-8",
    )


def _raw(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_profile_uses_median_and_keeps_missing_targets_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "reference"
    root.mkdir()
    _raw(root / "IMG_0001.ARW", b"raw-a" * 400)
    _raw(root / "IMG_0002.ARW", b"raw-b" * 400)
    _raw(root / "IMG_0003.ARW", b"raw-c" * 400)
    _xmp(
        root / "IMG_0001.xmp",
        exposure="+0.20",
        temperature="5000",
        tint="+4",
        raw_name="IMG_0001.ARW",
    )
    _xmp(
        root / "IMG_0002.xmp",
        exposure="+0.60",
        temperature="5400",
        tint="+10",
        raw_name="IMG_0002.ARW",
    )
    _xmp(
        root / "IMG_0003.xmp",
        exposure="-1.00",
        temperature=None,
        tint="+2",
        raw_name="IMG_0003.ARW",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(root),
                "edits_root": str(root),
                "photographer_id": "studio",
                "event_label": "reference",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["quality_claim_allowed"] is False
    assert body["usable_pairs"] == 2
    assert body["excluded_missing_targets"] == 1
    assert body["baseline"]["exposure"] == 0.4
    assert body["baseline"]["temperature"] == 5200
    assert body["baseline"]["tint"] == 7
    assert body["baseline"]["temperature"] != 0


def test_shared_filename_is_not_trained_as_one_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "two-cameras"
    _raw(root / "cam-a" / "IMG_0001.ARW", b"camera-a" * 300)
    _raw(root / "cam-b" / "IMG_0001.ARW", b"camera-b" * 300)
    _xmp(
        root / "loose" / "IMG_0001.xmp",
        exposure="+0.10",
        temperature="4800",
        tint="0",
        raw_name="IMG_0001.ARW",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={"raw_root": str(root), "edits_root": str(root)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["baseline"] is None
    assert body["usable_pairs"] == 0
    assert any("אותו XMP" in warning for warning in body["warnings"])


def test_review_uses_separate_profile_xmp_root_and_keeps_prographer_suggestion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    raw_root = tmp_path / "raw"
    xmp_root = tmp_path / "xmp"
    raw_root.mkdir()
    xmp_root.mkdir()

    _raw(raw_root / "IMG_0001.ARW", b"raw-separate-xmp" * 400)
    _xmp(
        xmp_root / "IMG_0001.xmp",
        exposure="+0.20",
        temperature="5000",
        tint="+4",
        raw_name="IMG_0001.ARW",
    )

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(raw_root)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]

        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(raw_root),
                "edits_root": str(xmp_root),
                "learning_source": "raw",
            },
        )
        assert profile.status_code == 200

        sheet = client.get(
            f"/api/testing/events/{event_id}/review?learning_source=raw",
            headers=HEADERS,
        )
        assert sheet.status_code == 200
        file = sheet.json()["files"][0]
        assert file["photographer"]["exposure"] == 0.2
        assert file["photographer"]["temperature"] == 5000
        assert file["photographer"]["tint"] == 4
        assert file["suggested"]["exposure"] == 0.2
        assert file["suggested"]["temperature"] == 5000
        assert file["suggested"]["tint"] == 4

        saved = client.post(
            "/api/testing/review",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "item": {
                    "fingerprint": file["fingerprint"],
                    "exposure": 0.55,
                    "temperature": 5100,
                    "tint": 6,
                    "decision": "corrected",
                },
            },
        )
        assert saved.status_code == 200

        refreshed = client.get(
            f"/api/testing/events/{event_id}/review?learning_source=raw",
            headers=HEADERS,
        )
        assert refreshed.status_code == 200
        refreshed_file = refreshed.json()["files"][0]
        assert refreshed_file["saved_review"]["exposure"] == 0.55
        assert refreshed_file["suggested"]["exposure"] == 0.2
        assert refreshed_file["suggested"]["temperature"] == 5000
        assert refreshed_file["suggested"]["tint"] == 4


def test_review_and_export_leave_raw_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event = tmp_path / "wedding"
    event.mkdir()
    raw_path = event / "IMG_0100.ARW"
    _raw(raw_path, b"wedding-raw" * 500)
    original = raw_path.read_bytes()
    _xmp(
        event / "IMG_0100.xmp",
        exposure="+0.15",
        temperature="5100",
        tint="+3",
        raw_name="IMG_0100.ARW",
    )
    reference = tmp_path / "reference"
    reference.mkdir()
    _raw(reference / "IMG_0001.ARW", b"ref-raw" * 400)
    _xmp(
        reference / "IMG_0001.xmp",
        exposure="+0.50",
        temperature="5600",
        tint="+8",
        raw_name="IMG_0001.ARW",
    )
    output = tmp_path / "export"

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]

        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={"raw_root": str(reference), "edits_root": str(reference)},
        )
        assert profile.status_code == 200

        sheet = client.get(
            f"/api/testing/events/{event_id}/review",
            headers=HEADERS,
        )
        assert sheet.status_code == 200
        files = sheet.json()["files"]
        assert len(files) == 1
        assert files[0]["photographer"]["temperature"] == 5100
        assert files[0]["suggested"]["temperature"] == 5600
        assert files[0]["suggested"]["exposure"] == 0.5

        saved = client.post(
            "/api/testing/review",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "item": {
                    "fingerprint": files[0]["fingerprint"],
                    "exposure": 0.25,
                    "temperature": 5300,
                    "tint": 5,
                    "decision": "corrected",
                },
            },
        )
        assert saved.status_code == 200
        assert not output.exists()

        refreshed = client.get(
            f"/api/testing/events/{event_id}/review",
            headers=HEADERS,
        )
        assert refreshed.status_code == 200
        refreshed_file = refreshed.json()["files"][0]
        assert refreshed_file["saved_review"]["temperature"] == 5300
        assert refreshed_file["suggested"]["temperature"] == 5600
        assert refreshed_file["suggested"]["exposure"] == 0.5

        exported = client.post(
            "/api/testing/export",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "output_dir": str(output),
                "items": [
                    {
                        "fingerprint": files[0]["fingerprint"],
                        "exposure": 0.25,
                        "temperature": 5300,
                        "tint": 5,
                        "decision": "corrected",
                    }
                ],
            },
        )

    assert exported.status_code == 200
    body = exported.json()
    assert body["written"] == 1
    written = Path(body["files"][0]["path"])
    assert written.name == "IMG_0100.xmp"
    assert written.parent == (output / event_id).resolve()
    assert raw_path.read_bytes() == original
    text = written.read_text(encoding="utf-8")
    assert 'crs:Temperature="5300"' in text
    assert "testing-loop-v1" in text

    foreign_destination = event / event_id / "IMG_0100.xmp"
    _xmp(
        foreign_destination,
        exposure="+0.10",
        temperature="5000",
        tint="+1",
        raw_name="IMG_0100.ARW",
    )

    with TestClient(create_app()) as client:
        blocked = client.post(
            "/api/testing/export",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "output_dir": str(event),
                "items": [
                    {
                        "fingerprint": files[0]["fingerprint"],
                        "exposure": 0.25,
                        "temperature": 5300,
                        "tint": 5,
                        "decision": "approved",
                    }
                ],
            },
        )
    assert blocked.status_code == 200
    assert blocked.json()["skipped"] == 1
    assert "לא הוחלף" in blocked.json()["files"][0]["reason"]
    assert raw_path.read_bytes() == original


def _jpeg(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_jpeg_profile_counts_unique_pairs_and_has_no_baseline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    originals = tmp_path / "jpeg-originals"
    edits = tmp_path / "jpeg-edits"
    _jpeg(originals / "IMG_0001.jpg", b"jpeg-a" * 200)
    _jpeg(originals / "IMG_0002.jpeg", b"jpeg-b" * 200)
    _raw(originals / "IMG_0003.ARW", b"raw-ignored" * 200)
    _jpeg(edits / "IMG_0001.jpg", b"edit-a" * 200)
    _jpeg(edits / "IMG_0002.jpg", b"edit-b" * 200)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(originals),
                "edits_root": str(edits),
                "learning_source": "jpeg",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["learning_source"] == "jpeg"
    assert body["usable_pairs"] == 2
    assert body["matched_pairs"] == 2
    assert body["baseline"] is None
    assert body["raw_files"] == 2
    assert body["learning_material"] == "jpeg_pairs"
    manifest = Path(body["dataset_manifest_path"])
    assert manifest.is_file()
    stored_manifest = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    assert stored_manifest["kind"] == "jpeg_pairs"
    assert len(stored_manifest["pairs"]) == 2
    assert all(
        pair["original_path"] != pair["edited_path"]
        for pair in stored_manifest["pairs"]
    )
    assert all(
        pair["original_path"]
        and pair["edited_path"]
        and pair["original_fingerprint"]
        and pair["edited_fingerprint"]
        for pair in stored_manifest["pairs"]
    )
    assert any("אינם JPEG" in warning for warning in body["warnings"])
    assert "Lightroom" in body["note"]


def test_jpeg_profile_accepts_distinct_byte_identical_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    originals = tmp_path / "jpeg-originals"
    edits = tmp_path / "jpeg-edits"
    payload = b"intentionally-unchanged-jpeg" * 200
    _jpeg(originals / "IMG_0001.jpg", payload)
    _jpeg(edits / "IMG_0001.jpg", payload)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(originals),
                "edits_root": str(edits),
                "learning_source": "jpeg",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["matched_pairs"] == 1
    assert body["usable_pairs"] == 1

    manifest = Path(body["dataset_manifest_path"])
    stored_manifest = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    pair = stored_manifest["pairs"][0]
    assert pair["original_path"] != pair["edited_path"]
    assert pair["original_fingerprint"] == pair["edited_fingerprint"]


def test_jpeg_profile_does_not_merge_shared_filenames(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    originals = tmp_path / "two-cameras"
    edits = tmp_path / "edits"
    _jpeg(originals / "cam-a" / "IMG_0001.jpg", b"camera-a" * 200)
    _jpeg(originals / "cam-b" / "IMG_0001.jpg", b"camera-b" * 200)
    _jpeg(edits / "IMG_0001.jpg", b"one-edit" * 200)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(originals),
                "edits_root": str(edits),
                "learning_source": "jpeg",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["baseline"] is None
    assert body["usable_pairs"] == 0
    assert body["ambiguous_raw"] == 2


def test_jpeg_profile_review_lists_only_jpeg_and_refuses_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event = tmp_path / "event"
    _jpeg(event / "IMG_0200.jpg", b"event-jpeg" * 200)
    _raw(event / "IMG_0201.ARW", b"event-raw" * 200)
    originals = tmp_path / "originals"
    edits = tmp_path / "edits"
    _jpeg(originals / "IMG_0001.jpg", b"src" * 200)
    _jpeg(edits / "IMG_0001.jpg", b"dst" * 200)
    output = tmp_path / "export"

    with TestClient(create_app()) as client:
        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]
        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(originals),
                "edits_root": str(edits),
                "learning_source": "jpeg",
            },
        )
        assert profile.status_code == 200
        sheet = client.get(
            f"/api/testing/events/{event_id}/review",
            headers=HEADERS,
        )
        assert sheet.status_code == 200
        body = sheet.json()
        assert body["learning_source"] == "jpeg"
        assert body["baseline"] is None
        assert len(body["files"]) == 1
        assert body["files"][0]["filename"] == "IMG_0200.jpg"
        assert body["files"][0]["suggested"] is None
        exported = client.post(
            "/api/testing/export",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "output_dir": str(output),
                "items": [
                    {
                        "fingerprint": body["files"][0]["fingerprint"],
                        "exposure": 0.2,
                        "temperature": 5200,
                        "tint": 4,
                        "decision": "corrected",
                    }
                ],
            },
        )

    assert exported.status_code == 200
    assert exported.json()["written"] == 0
    assert exported.json()["skipped"] == 1
    assert not output.exists() or not any(output.rglob("*.xmp"))


def test_switching_learning_source_preserves_both_profiles_and_reviews(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    _raw(raw_root / "IMG_0001.ARW", b"raw-a" * 400)
    _xmp(
        raw_root / "IMG_0001.xmp",
        exposure="+0.20",
        temperature="5000",
        tint="+4",
        raw_name="IMG_0001.ARW",
    )

    jpeg_originals = tmp_path / "jpeg-originals"
    jpeg_edits = tmp_path / "jpeg-edits"
    _jpeg(jpeg_originals / "IMG_0001.jpg", b"jpeg-original" * 200)
    _jpeg(jpeg_edits / "IMG_0001.jpg", b"jpeg-edited" * 200)

    with TestClient(create_app()) as client:
        first = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={"raw_root": str(raw_root), "edits_root": str(raw_root)},
        )
        assert first.status_code == 200
        assert first.json()["learning_source"] == "raw"

        document = tmp_path / "data" / "testing_profile.json"
        stored = __import__("json").loads(document.read_text(encoding="utf-8"))
        stored["reviews"]["raw"]["event:abc"] = {"decision": "approved"}
        document.write_text(
            __import__("json").dumps(stored),
            encoding="utf-8",
        )

        second = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(jpeg_originals),
                "edits_root": str(jpeg_edits),
                "learning_source": "jpeg",
            },
        )
        assert second.status_code == 200

        activated = client.post(
            "/api/testing/profile/activate",
            headers=HEADERS,
            json={"learning_source": "raw"},
        )
        assert activated.status_code == 200
        assert activated.json()["learning_source"] == "raw"

        raw_profile = client.get(
            "/api/testing/profile?learning_source=raw",
            headers=HEADERS,
        )
        jpeg_profile = client.get(
            "/api/testing/profile?learning_source=jpeg",
            headers=HEADERS,
        )
        assert raw_profile.status_code == 200
        assert jpeg_profile.status_code == 200

    saved = __import__("json").loads(document.read_text(encoding="utf-8"))
    assert set(saved["profiles"]) == {"raw", "jpeg"}
    assert saved["active_source"] == "raw"
    assert saved["reviews"]["raw"]["event:abc"]["decision"] == "approved"
    assert saved["reviews"]["jpeg"] == {}


def test_jpeg_profile_rejects_identical_before_after_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    same = tmp_path / "same"
    _jpeg(same / "IMG_0001.jpg", b"same-jpeg" * 200)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(same),
                "edits_root": str(same),
                "learning_source": "jpeg",
            },
        )

    assert response.status_code == 422
    assert "שתי תיקיות נפרדות" in response.json()["detail"]



def test_same_named_exports_from_different_events_are_isolated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    reference = tmp_path / "reference"
    reference.mkdir()
    _raw(reference / "IMG_0001.ARW", b"reference" * 400)
    _xmp(
        reference / "IMG_0001.xmp",
        exposure="+0.30",
        temperature="5200",
        tint="+2",
        raw_name="IMG_0001.ARW",
    )

    event_a = tmp_path / "event-a"
    event_b = tmp_path / "event-b"
    event_a.mkdir()
    event_b.mkdir()
    _raw(event_a / "IMG_0100.ARW", b"event-a" * 500)
    _raw(event_b / "IMG_0100.ARW", b"event-b" * 500)
    output = tmp_path / "export"

    with TestClient(create_app()) as client:
        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={"raw_root": str(reference), "edits_root": str(reference)},
        )
        assert profile.status_code == 200

        event_ids = []
        for folder in (event_a, event_b):
            opened = client.post(
                "/api/events/open-folder",
                headers=HEADERS,
                json={"path": str(folder)},
            )
            assert opened.status_code == 200
            event_id = opened.json()["event"]["id"]
            event_ids.append(event_id)

            sheet = client.get(
                f"/api/testing/events/{event_id}/review",
                headers=HEADERS,
            )
            assert sheet.status_code == 200
            file = sheet.json()["files"][0]

            exported = client.post(
                "/api/testing/export",
                headers=HEADERS,
                json={
                    "event_id": event_id,
                    "output_dir": str(output),
                    "items": [
                        {
                            "fingerprint": file["fingerprint"],
                            "exposure": 0.3,
                            "temperature": 5200,
                            "tint": 2,
                            "decision": "approved",
                        }
                    ],
                },
            )
            assert exported.status_code == 200
            assert exported.json()["written"] == 1

    first = output / event_ids[0] / "IMG_0100.xmp"
    second = output / event_ids[1] / "IMG_0100.xmp"
    assert first.is_file()
    assert second.is_file()
    assert first != second


def test_explicit_jpeg_review_does_not_depend_on_active_raw_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))

    raw_reference = tmp_path / "raw-reference"
    raw_reference.mkdir()
    _raw(raw_reference / "IMG_0001.ARW", b"raw-reference" * 300)
    _xmp(
        raw_reference / "IMG_0001.xmp",
        exposure="+0.20",
        temperature="5100",
        tint="+3",
        raw_name="IMG_0001.ARW",
    )

    jpeg_event = tmp_path / "jpeg-event"
    _jpeg(jpeg_event / "IMG_1000.jpg", b"jpeg-event" * 300)

    with TestClient(create_app()) as client:
        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={
                "raw_root": str(raw_reference),
                "edits_root": str(raw_reference),
                "learning_source": "raw",
            },
        )
        assert profile.status_code == 200
        assert profile.json()["learning_source"] == "raw"

        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(jpeg_event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]

        sheet = client.get(
            f"/api/testing/events/{event_id}/review?learning_source=jpeg",
            headers=HEADERS,
        )

    assert sheet.status_code == 200
    body = sheet.json()
    assert body["learning_source"] == "jpeg"
    assert len(body["files"]) == 1
    assert body["files"][0]["filename"] == "IMG_1000.jpg"
    assert body["files"][0]["pair_status"] == "jpeg"


def test_delete_event_keeps_source_files_and_purges_reviews(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))

    reference = tmp_path / "reference"
    reference.mkdir()
    _raw(reference / "IMG_0001.ARW", b"reference-raw" * 300)
    _xmp(
        reference / "IMG_0001.xmp",
        exposure="+0.20",
        temperature="5100",
        tint="+3",
        raw_name="IMG_0001.ARW",
    )

    event = tmp_path / "event"
    event.mkdir()
    raw_path = event / "IMG_0200.ARW"
    _raw(raw_path, b"event-raw" * 400)
    original_bytes = raw_path.read_bytes()

    with TestClient(create_app()) as client:
        profile = client.post(
            "/api/testing/profile",
            headers=HEADERS,
            json={"raw_root": str(reference), "edits_root": str(reference)},
        )
        assert profile.status_code == 200

        opened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert opened.status_code == 200
        event_id = opened.json()["event"]["id"]

        sheet = client.get(
            f"/api/testing/events/{event_id}/review?learning_source=raw",
            headers=HEADERS,
        )
        assert sheet.status_code == 200
        file = sheet.json()["files"][0]

        saved = client.post(
            "/api/testing/review",
            headers=HEADERS,
            json={
                "event_id": event_id,
                "item": {
                    "fingerprint": file["fingerprint"],
                    "exposure": 0.4,
                    "temperature": 5300,
                    "tint": 5,
                    "decision": "corrected",
                },
            },
        )
        assert saved.status_code == 200

        removed = client.delete(
            f"/api/events/{event_id}",
            headers=HEADERS,
        )
        assert removed.status_code == 200
        body = removed.json()
        assert body["removed_from_catalog"] is True
        assert body["source_files_deleted"] is False

        listed = client.get("/api/events", headers=HEADERS)
        assert listed.status_code == 200
        assert all(item["id"] != event_id for item in listed.json()["events"])

        reopened = client.post(
            "/api/events/open-folder",
            headers=HEADERS,
            json={"path": str(event)},
        )
        assert reopened.status_code == 200
        assert reopened.json()["event"]["id"] == event_id

        fresh_sheet = client.get(
            f"/api/testing/events/{event_id}/review?learning_source=raw",
            headers=HEADERS,
        )
        assert fresh_sheet.status_code == 200
        assert fresh_sheet.json()["files"][0]["saved_review"] is None

    assert raw_path.is_file()
    assert raw_path.read_bytes() == original_bytes
