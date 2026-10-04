from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["PROGRAPHER_ENGINE_SECRET"] = "pg-04-06-test-secret"

from app.application import create_app  # noqa: E402
from app.rendering.jpeg_controls import (  # noqa: E402
    JPEG_CONTROL_CONTRACT_VERSION,
    JpegControlValidationError,
    JpegGlobalControls,
    jpeg_control_contract,
    jpeg_controls_to_recipe,
)
from app.rendering.jpeg_renderer import (  # noqa: E402
    identity_polynomial_recipe,
    render_recipe_uint8,
)


HEADERS = {"X-ProGrapher-Secret": "pg-04-06-test-secret"}


def _rgb_fixture() -> np.ndarray:
    yy, xx = np.mgrid[0:48, 0:64].astype(np.uint16)
    return np.stack(
        (
            (xx * 7 + yy * 3) % 256,
            (xx * 5 + yy * 11 + 17) % 256,
            (xx * 13 + yy * 2 + 31) % 256,
        ),
        axis=2,
    ).astype(np.uint8)


def _write_jpeg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_rgb_fixture()).save(
        path,
        format="JPEG",
        quality=98,
        subsampling=0,
    )


def test_neutral_jpeg_controls_are_exact_identity_recipe() -> None:
    assert jpeg_controls_to_recipe(JpegGlobalControls()) == (
        identity_polynomial_recipe()
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("brightness", 25),
        ("contrast", 25),
        ("warmth", 25),
        ("tint", 25),
    ],
)
def test_each_supported_control_changes_rendered_pixels(
    name: str,
    value: float,
) -> None:
    source = _rgb_fixture()
    neutral = render_recipe_uint8(
        source,
        jpeg_controls_to_recipe(JpegGlobalControls()),
    )
    controls = JpegGlobalControls(**{name: value})
    changed = render_recipe_uint8(
        source,
        jpeg_controls_to_recipe(controls),
    )

    assert not np.array_equal(changed, neutral)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("brightness", -101),
        ("contrast", 101),
        ("warmth", float("inf")),
        ("tint", float("nan")),
    ],
)
def test_invalid_control_values_fail_without_clipping(
    name: str,
    value: float,
) -> None:
    with pytest.raises(JpegControlValidationError):
        jpeg_controls_to_recipe({name: value})


def test_contract_does_not_claim_raw_kelvin_or_lightroom_tint() -> None:
    contract = jpeg_control_contract()

    assert contract["contract_version"] == JPEG_CONTROL_CONTRACT_VERSION
    assert set(contract["controls"]) == {
        "brightness",
        "contrast",
        "warmth",
        "tint",
    }
    assert contract["raw_equivalence"]["temperature_kelvin"] is False
    assert contract["raw_equivalence"]["lightroom_tint"] is False


def test_control_preview_api_returns_real_renderer_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    event_dir = tmp_path / "event"
    source = event_dir / "IMG_0406.jpg"
    _write_jpeg(source)

    client = TestClient(create_app())
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
    fingerprint = listed.json()["files"][0]["fingerprint"]

    response = client.post(
        "/api/jpeg-controls/preview",
        headers=HEADERS,
        json={
            "event_id": event_id,
            "fingerprint": fingerprint,
            "revision": 1,
            "controls": {
                "brightness": 20,
                "contrast": 15,
                "warmth": 10,
                "tint": -5,
            },
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert (
        response.headers["x-prographer-jpeg-control-contract"]
        == JPEG_CONTROL_CONTRACT_VERSION
    )
    assert response.content.startswith(b"\x89PNG")
