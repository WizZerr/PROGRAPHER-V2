from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

os.environ["PROGRAPHER_ENGINE_SECRET"] = "pg-04-03-test-secret"

from app.application import create_app  # noqa: E402
from app.rendering.jpeg_export import (  # noqa: E402
    JPEG_EXPORT_CONTRACT_VERSION,
    JpegExportOptions,
    encode_jpeg_export,
)
from app.rendering.jpeg_product_render import render_jpeg_product  # noqa: E402
from app.rendering.jpeg_renderer import identity_polynomial_recipe  # noqa: E402


HEADERS = {"X-ProGrapher-Secret": "pg-04-03-test-secret"}
GPS_TAG = 34853
ORIENTATION_TAG = 274
MAKE_TAG = 271


def _source_jpeg(
    path: Path,
    *,
    orientation: int = 1,
    include_gps: bool = True,
) -> None:
    yy, xx = np.mgrid[0:480, 0:640].astype(np.float32)
    rgb = np.clip(
        np.stack(
            (
                20 + 220 * (xx / 639.0),
                40 + 160 * (yy / 479.0),
                180 - 100 * (xx / 639.0),
            ),
            axis=2,
        ),
        0,
        255,
    ).astype(np.uint8)

    exif = Image.Exif()
    exif[ORIENTATION_TAG] = orientation
    exif[MAKE_TAG] = "ProGrapher Test Camera"
    if include_gps:
        exif[GPS_TAG] = {
            1: "N",
            2: (31.0, 58.0, 0.0),
            3: "E",
            4: (34.0, 47.0, 0.0),
        }

    Image.fromarray(rgb).save(
        path,
        format="JPEG",
        quality=98,
        exif=exif,
    )


def _open_event(
    client: TestClient,
    event_dir: Path,
) -> tuple[str, dict[str, str]]:
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
    by_name = {
        item["filename"]: item["fingerprint"]
        for item in listed.json()["files"]
    }
    return event_id, by_name


def _jpeg(payload: bytes) -> Image.Image:
    image = Image.open(BytesIO(payload))
    image.load()
    return image


def _make_current(
    event_id: str,
    fingerprint: str,
    *,
    revision: int = 1,
):
    recipe = identity_polynomial_recipe()
    render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=revision,
        mode="preview",
    )
    return recipe


def test_export_reopens_with_normalized_orientation_metadata_and_icc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    source = event_dir / "IMG_0403.jpg"
    _source_jpeg(source, orientation=6, include_gps=True)
    before = source.read_bytes()

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files[source.name]
    recipe = _make_current(event_id, fingerprint)
    artifact = encode_jpeg_export(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        options=JpegExportOptions(),
    )

    with _jpeg(artifact.payload) as encoded:
        assert encoded.format == "JPEG"
        assert encoded.mode == "RGB"
        # Stored 640x480 + EXIF orientation 6 becomes display 480x640.
        assert encoded.size == (480, 640)
        assert encoded.info.get("icc_profile")
        exif = encoded.getexif()
        assert exif.get(ORIENTATION_TAG) == 1
        assert exif.get(MAKE_TAG) == "ProGrapher Test Camera"
        assert GPS_TAG not in exif

    assert artifact.contract_version == JPEG_EXPORT_CONTRACT_VERSION
    assert artifact.gps_included is False
    assert source.read_bytes() == before


def test_export_resize_strip_metadata_and_omit_icc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    source = event_dir / "IMG_0403.jpg"
    _source_jpeg(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    fingerprint = files[source.name]
    recipe = _make_current(event_id, fingerprint)
    artifact = encode_jpeg_export(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        options=JpegExportOptions(
            quality=88,
            max_edge=320,
            icc_policy="omit",
            metadata_policy="strip",
        ),
    )

    with _jpeg(artifact.payload) as encoded:
        assert max(encoded.size) == 320
        assert not encoded.info.get("icc_profile")
        assert len(encoded.getexif()) == 0

    assert artifact.quality == 88
    assert artifact.gps_included is False


def test_gps_is_opt_in_and_missing_gps_does_not_fail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    with_gps = event_dir / "WITH_GPS.jpg"
    without_gps = event_dir / "WITHOUT_GPS.jpg"
    _source_jpeg(with_gps, include_gps=True)
    _source_jpeg(without_gps, include_gps=False)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)

    recipe = identity_polynomial_recipe()

    for source, expected_gps in (
        (with_gps, True),
        (without_gps, False),
    ):
        fingerprint = files[source.name]
        render_jpeg_product(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            mode="preview",
        )
        artifact = encode_jpeg_export(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=1,
            options=JpegExportOptions(include_gps=True),
        )
        with _jpeg(artifact.payload) as encoded:
            assert (GPS_TAG in encoded.getexif()) is expected_gps
        assert artifact.gps_included is expected_gps


def test_export_api_returns_encoded_jpeg_and_rejects_stale_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    source = event_dir / "IMG_0403.jpg"
    _source_jpeg(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)
        fingerprint = files[source.name]
        recipe = _make_current(event_id, fingerprint)

        response = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-export/encode",
            headers=HEADERS,
            json={
                "revision": 1,
                "recipe": recipe,
                "options": {
                    "quality": 91,
                    "max_edge": 300,
                    "icc_policy": "embed_srgb",
                    "metadata_policy": "preserve",
                    "include_gps": False,
                },
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/jpeg")
        assert (
            response.headers["x-prographer-jpeg-export-contract"]
            == JPEG_EXPORT_CONTRACT_VERSION
        )
        assert response.headers["x-prographer-jpeg-quality"] == "91"
        assert response.headers["x-prographer-export-width"]
        assert response.headers["x-prographer-export-height"]

        render_jpeg_product(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=recipe,
            revision=2,
            mode="preview",
        )

        stale = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-export/encode",
            headers=HEADERS,
            json={
                "revision": 1,
                "recipe": recipe,
                "options": {},
            },
        )

    assert stale.status_code == 409


def test_metadata_strip_cannot_request_gps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    source = event_dir / "IMG_0403.jpg"
    _source_jpeg(source)

    with TestClient(create_app()) as client:
        event_id, files = _open_event(client, event_dir)
        fingerprint = files[source.name]
        recipe = _make_current(event_id, fingerprint)

        response = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-export/encode",
            headers=HEADERS,
            json={
                "revision": 1,
                "recipe": recipe,
                "options": {
                    "metadata_policy": "strip",
                    "include_gps": True,
                },
            },
        )

    assert response.status_code == 422
