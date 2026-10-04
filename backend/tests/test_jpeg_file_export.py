from __future__ import annotations

import errno
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["PROGRAPHER_ENGINE_SECRET"] = "pg-04-04-test-secret"

from app.application import create_app  # noqa: E402
from app.datasets.jpeg_integrity import sha256_file  # noqa: E402
from app.rendering import jpeg_file_export  # noqa: E402
from app.rendering.jpeg_export import JpegExportOptions  # noqa: E402
from app.rendering.jpeg_file_export import (  # noqa: E402
    JpegExportDestinationExists,
    JpegExportDiskFull,
    JpegExportUnsafeDestination,
    JpegExportWriteFailed,
    export_jpeg_file,
)
from app.rendering.jpeg_product_render import render_jpeg_product  # noqa: E402
from app.rendering.jpeg_renderer import identity_polynomial_recipe  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "pg-04-04-test-secret"}


def _source_jpeg(path: Path, offset: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yy, xx = np.mgrid[0:240, 0:320].astype(np.float32)
    rgb = np.clip(
        np.stack(
            (
                20 + offset + 200 * (xx / 319.0),
                30 + 150 * (yy / 239.0),
                180 - 80 * (xx / 319.0),
            ),
            axis=2,
        ),
        0,
        255,
    ).astype(np.uint8)
    Image.fromarray(rgb).save(path, format="JPEG", quality=96)


def _open_event(client: TestClient, event_dir: Path):
    opened = client.post(
        "/api/events/open-folder",
        headers=HEADERS,
        json={"path": str(event_dir)},
    )
    assert opened.status_code == 200
    event_id = opened.json()["event"]["id"]

    listed = client.get(
        f"/api/events/{event_id}/files",
        headers=HEADERS,
    )
    assert listed.status_code == 200
    files = {
        Path(item["relative_path"]).as_posix(): item["fingerprint"]
        for item in listed.json()["files"]
    }
    return event_id, files


def _make_current(event_id: str, fingerprint: str):
    recipe = identity_polynomial_recipe()
    render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        mode="preview",
    )
    return recipe


def test_export_preserves_relative_paths_and_duplicate_basenames(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    first = event_dir / "ceremony" / "IMG_0001.jpg"
    second = event_dir / "reception" / "IMG_0001.jpg"
    _source_jpeg(first, offset=0)
    _source_jpeg(second, offset=20)
    before = {
        first: sha256_file(first),
        second: sha256_file(second),
    }

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    output = tmp_path / "exports"
    results = []
    for relative in (
        "ceremony/IMG_0001.jpg",
        "reception/IMG_0001.jpg",
    ):
        fingerprint = files[relative]
        recipe = _make_current(event_id, fingerprint)
        results.append(
            export_jpeg_file(
                event_id=event_id,
                fingerprint=fingerprint,
                recipe=recipe,
                revision=1,
                options=JpegExportOptions(),
                output_dir=output,
            )
        )

    assert (output / "ceremony" / "IMG_0001.jpg").is_file()
    assert (output / "reception" / "IMG_0001.jpg").is_file()
    assert {item.relative_path for item in results} == {
        "ceremony/IMG_0001.jpg",
        "reception/IMG_0001.jpg",
    }
    assert all(item.source_unchanged for item in results)
    assert sha256_file(first) == before[first]
    assert sha256_file(second) == before[second]


def test_existing_destination_fails_or_allocates_unique_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0002.jpg"
    _source_jpeg(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files["IMG_0002.jpg"]
    recipe = _make_current(event_id, fingerprint)
    output = tmp_path / "exports"
    output.mkdir()
    existing = output / "IMG_0002.jpg"
    existing.write_bytes(b"existing-user-file")
    existing_before = existing.read_bytes()

    with pytest.raises(JpegExportDestinationExists):
        export_jpeg_file(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            options=JpegExportOptions(),
            output_dir=output,
            collision_policy="fail",
        )

    result = export_jpeg_file(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        options=JpegExportOptions(),
        output_dir=output,
        collision_policy="unique",
    )

    assert existing.read_bytes() == existing_before
    assert Path(result.destination_path).name == "IMG_0002 (1).jpg"
    assert Path(result.destination_path).is_file()
    assert result.renamed_for_collision is True


def test_export_inside_event_root_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0003.jpg"
    _source_jpeg(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files["IMG_0003.jpg"]
    recipe = _make_current(event_id, fingerprint)

    with pytest.raises(JpegExportUnsafeDestination):
        export_jpeg_file(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            options=JpegExportOptions(),
            output_dir=event_dir / "exports",
        )


def test_disk_full_leaves_no_final_or_temporary_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0004.jpg"
    _source_jpeg(source)
    source_before = sha256_file(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files["IMG_0004.jpg"]
    recipe = _make_current(event_id, fingerprint)
    output = tmp_path / "exports"

    real_fsync = jpeg_file_export.os.fsync

    def disk_full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(jpeg_file_export.os, "fsync", disk_full)
    with pytest.raises(JpegExportDiskFull):
        export_jpeg_file(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            options=JpegExportOptions(),
            output_dir=output,
        )
    monkeypatch.setattr(jpeg_file_export.os, "fsync", real_fsync)

    assert not (output / "IMG_0004.jpg").exists()
    assert list(output.rglob("*.prographer-tmp")) == []
    assert sha256_file(source) == source_before


def test_promotion_failure_leaves_no_partial_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0005.jpg"
    _source_jpeg(source)
    source_before = sha256_file(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files["IMG_0005.jpg"]
    recipe = _make_current(event_id, fingerprint)
    output = tmp_path / "exports"

    def fail_replace(source_path, destination_path):
        raise OSError(errno.EIO, "simulated promotion failure")

    monkeypatch.setattr(jpeg_file_export.os, "replace", fail_replace)

    with pytest.raises(JpegExportWriteFailed):
        export_jpeg_file(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            options=JpegExportOptions(),
            output_dir=output,
        )

    assert not (output / "IMG_0005.jpg").exists()
    assert list(output.rglob("*.prographer-tmp")) == []
    assert sha256_file(source) == source_before


def test_write_api_reports_success_and_existing_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0006.jpg"
    _source_jpeg(source)
    output = tmp_path / "exports"

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)
        fingerprint = files["IMG_0006.jpg"]
        recipe = _make_current(event_id, fingerprint)

        payload = {
            "revision": 1,
            "recipe": recipe,
            "options": {},
            "output_dir": str(output),
            "collision_policy": "fail",
        }
        written = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-export/write",
            headers=HEADERS,
            json=payload,
        )
        conflict = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-export/write",
            headers=HEADERS,
            json=payload,
        )

    assert written.status_code == 200
    assert written.json()["status"] == "written"
    assert written.json()["source_unchanged"] is True
    assert Path(written.json()["destination_path"]).is_file()
    assert conflict.status_code == 409
