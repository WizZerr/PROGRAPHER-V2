from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ["PROGRAPHER_ENGINE_SECRET"] = "pg-04-02-test-secret"

from app.application import create_app  # noqa: E402
from app.datasets.jpeg_integrity import read_jpeg_working_rgb  # noqa: E402
from app.rendering.jpeg_product_render import (  # noqa: E402
    JPEG_PRODUCT_PREVIEW_MAX_EDGE,
    JpegRenderRevisionConflict,
    JpegRenderStaleRevision,
    assert_current_jpeg_revision,
    render_jpeg_product,
)
from app.rendering.jpeg_renderer import (  # noqa: E402
    POLYNOMIAL_FEATURE_NAMES,
    build_polynomial_recipe,
    identity_polynomial_recipe,
    render_recipe_uint8,
)


HEADERS = {"X-ProGrapher-Secret": "pg-04-02-test-secret"}


def _jpeg(path: Path, width: int = 2000, height: int = 1000) -> None:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    r = 30 + 190 * (xx / max(1, width - 1))
    g = 20 + 170 * (yy / max(1, height - 1))
    b = 50 + 80 * (1.0 - xx / max(1, width - 1))
    rgb = np.clip(np.stack((r, g, b), axis=2), 0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(
        ".jpg",
        bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), 96],
    )
    assert ok
    path.write_bytes(encoded.tobytes())


def _warm_recipe() -> dict:
    coefficients = np.zeros(
        (len(POLYNOMIAL_FEATURE_NAMES), 3),
        dtype=np.float64,
    )
    coefficients[0] = [0.01, 0.0, -0.01]
    coefficients[1, 0] = 1.04
    coefficients[2, 1] = 1.00
    coefficients[3, 2] = 0.96
    return build_polynomial_recipe(coefficients)


def _open_jpeg_event(
    client: TestClient,
    event_dir: Path,
) -> tuple[str, str, Path]:
    jpeg_path = event_dir / "IMG_0402.jpg"
    _jpeg(jpeg_path)

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
    fingerprint = listed.json()["files"][0]["fingerprint"]
    return event_id, fingerprint, jpeg_path


def _decode_png(payload: bytes) -> np.ndarray:
    bgr = cv2.imdecode(
        np.frombuffer(payload, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert bgr is not None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def test_full_render_uses_shared_renderer_on_working_space_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()

    with TestClient(create_app()) as client:
        event_id, fingerprint, jpeg_path = _open_jpeg_event(client, event_dir)

    recipe = _warm_recipe()
    artifact = render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        mode="full",
    )

    source_rgb, _ = read_jpeg_working_rgb(jpeg_path)
    expected = render_recipe_uint8(source_rgb, recipe)
    actual = _decode_png(artifact.payload)

    assert artifact.media_type == "image/png"
    assert artifact.width == source_rgb.shape[1]
    assert artifact.height == source_rgb.shape[0]
    assert np.array_equal(actual, expected)


def test_preview_is_bounded_and_revision_cache_is_reused(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()

    with TestClient(create_app()) as client:
        event_id, fingerprint, _ = _open_jpeg_event(client, event_dir)

    recipe = identity_polynomial_recipe()
    first = render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        mode="preview",
    )
    second = render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        mode="preview",
    )

    assert max(first.width, first.height) == JPEG_PRODUCT_PREVIEW_MAX_EDGE
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.payload == second.payload
    assert first.recipe_sha256 == second.recipe_sha256


def test_same_revision_cannot_be_rebound_to_another_recipe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()

    with TestClient(create_app()) as client:
        event_id, fingerprint, _ = _open_jpeg_event(client, event_dir)

    render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=identity_polynomial_recipe(),
        revision=1,
        mode="preview",
    )

    with pytest.raises(JpegRenderRevisionConflict):
        render_jpeg_product(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=_warm_recipe(),
            revision=1,
            mode="preview",
        )


def test_new_revision_makes_old_preview_and_approval_guard_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()

    with TestClient(create_app()) as client:
        event_id, fingerprint, _ = _open_jpeg_event(client, event_dir)

    identity = identity_polynomial_recipe()
    warm = _warm_recipe()

    render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=identity,
        revision=1,
        mode="preview",
    )
    render_jpeg_product(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=warm,
        revision=2,
        mode="preview",
    )

    with pytest.raises(JpegRenderStaleRevision):
        render_jpeg_product(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=identity,
            revision=1,
            mode="preview",
        )

    with pytest.raises(JpegRenderStaleRevision):
        assert_current_jpeg_revision(
            event_id=event_id,
            fingerprint=fingerprint,
            recipe=identity,
            revision=1,
        )

    digest = assert_current_jpeg_revision(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=warm,
        revision=2,
    )
    assert len(digest) == 64


def test_product_render_api_exposes_revision_and_rejects_stale_requests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    event_dir.mkdir()

    with TestClient(create_app()) as client:
        event_id, fingerprint, _ = _open_jpeg_event(client, event_dir)
        identity = identity_polynomial_recipe()
        warm = _warm_recipe()

        preview = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-render/preview",
            headers=HEADERS,
            json={"revision": 1, "recipe": identity},
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/png")
        assert preview.headers["x-prographer-recipe-revision"] == "1"
        assert preview.headers["cache-control"] == "private, no-store"

        full = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-render/full",
            headers=HEADERS,
            json={"revision": 2, "recipe": warm},
        )
        assert full.status_code == 200
        assert full.headers["x-prographer-recipe-revision"] == "2"

        stale = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-render/preview",
            headers=HEADERS,
            json={"revision": 1, "recipe": identity},
        )
        assert stale.status_code == 409

        current = client.post(
            f"/api/events/{event_id}/files/{fingerprint}/jpeg-render/assert-current",
            headers=HEADERS,
            json={"revision": 2, "recipe": warm},
        )
        assert current.status_code == 200
        assert current.json()["current"] is True
