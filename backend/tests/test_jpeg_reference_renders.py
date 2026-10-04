from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.datasets.jpeg_integrity import read_jpeg_working_rgb
from app.rendering.jpeg_export import JpegExportOptions, encode_jpeg_export
from app.rendering.jpeg_product_render import render_jpeg_product
from app.rendering.jpeg_renderer import (
    build_polynomial_recipe,
    render_recipe_uint8,
)
from app.services.event_service import list_event_files, open_event_folder


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "jpeg_golden_cases_v1.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _reference_rgb(width: int, height: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.uint32)
    red = (xx * 7 + yy * 3) % 256
    green = (xx * 5 + yy * 11 + 17) % 256
    blue = (xx * 13 + yy * 2 + 31) % 256
    return np.stack((red, green, blue), axis=2).astype(np.uint8)


def _write_source(
    path: Path,
    *,
    width: int,
    height: int,
    quality: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_reference_rgb(width, height)).save(
        path,
        format="JPEG",
        quality=quality,
        subsampling=0,
        optimize=False,
        progressive=False,
    )


def _decode(payload: bytes) -> np.ndarray:
    with Image.open(BytesIO(payload)) as opened:
        opened.load()
        return np.asarray(opened.convert("RGB"), dtype=np.uint8).copy()


def _current_file(
    event_dir: Path,
    recipe: dict,
):
    result = open_event_folder(str(event_dir))
    records = list_event_files(result.event.id)
    assert len(records) == 1
    record = records[0]
    preview = render_jpeg_product(
        event_id=result.event.id,
        fingerprint=record.fingerprint,
        recipe=recipe,
        revision=1,
        mode="preview",
    )
    return result.event.id, record.fingerprint, preview


def _diff_metrics(actual: np.ndarray, expected: np.ndarray) -> dict:
    assert actual.shape == expected.shape
    delta = np.abs(
        actual.astype(np.int16) - expected.astype(np.int16)
    )
    return {
        "mean": float(delta.mean()),
        "p95": float(np.percentile(delta, 95)),
        "max": int(delta.max()),
    }


def test_renderer_matches_frozen_semantic_goldens() -> None:
    fixture = _fixture()
    source = _reference_rgb(
        fixture["source_generator"]["renderer_width"],
        fixture["source_generator"]["renderer_height"],
    )

    for case in fixture["cases"]:
        recipe = build_polynomial_recipe(case["coefficients"])
        rendered = render_recipe_uint8(source, recipe)

        assert (
            sha256(rendered.tobytes()).hexdigest()
            == case["expected_rgb_sha256"]
        )

        means = rendered.reshape(-1, 3).mean(axis=0)
        assert means == pytest.approx(
            case["expected_mean_rgb"],
            abs=1e-9,
        )
        assert float((rendered == 255).mean()) == pytest.approx(
            case["expected_clip_fraction"],
            abs=1e-12,
        )

        for key, expected_rgb in case["expected_probes"].items():
            y_text, x_text = key.split(",")
            actual = rendered[int(y_text), int(x_text)].tolist()
            assert actual == expected_rgb


@pytest.mark.parametrize(
    "case_id",
    ["identity", "tone_color", "clipping"],
)
def test_encoded_export_matches_reference_render_within_budget(
    case_id: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    fixture = _fixture()
    budget = fixture["encoded_export_budget"]
    case = next(
        item for item in fixture["cases"] if item["id"] == case_id
    )
    recipe = build_polynomial_recipe(case["coefficients"])

    event_dir = tmp_path / f"event-{case_id}"
    source_path = event_dir / f"{case_id}.jpg"
    _write_source(
        source_path,
        width=budget["source_width"],
        height=budget["source_height"],
        quality=budget["source_jpeg_quality"],
    )

    event_id, fingerprint, _ = _current_file(event_dir, recipe)
    working_rgb, _ = read_jpeg_working_rgb(source_path)
    expected = render_recipe_uint8(working_rgb, recipe)

    artifact = encode_jpeg_export(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        options=JpegExportOptions(
            quality=budget["export_jpeg_quality"],
            icc_policy="omit",
            metadata_policy="strip",
        ),
    )
    encoded_rgb = _decode(artifact.payload)
    metrics = _diff_metrics(encoded_rgb, expected)

    assert metrics["mean"] <= budget["mean_abs_error_max"]
    assert metrics["p95"] <= budget["p95_abs_error_max"]
    assert metrics["max"] <= budget["max_abs_error_max"]

    if case_id == "clipping":
        assert float((expected == 255).mean()) >= 0.25


def test_large_preview_tracks_downsampled_encoded_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PROGRAPHER_DATA_DIR", str(tmp_path / "data"))
    fixture = _fixture()
    budget = fixture["large_preview_budget"]
    case = next(
        item
        for item in fixture["cases"]
        if item["id"] == budget["recipe_case"]
    )
    recipe = build_polynomial_recipe(case["coefficients"])

    event_dir = tmp_path / "event-large"
    source_path = event_dir / "LARGE_0001.jpg"
    _write_source(
        source_path,
        width=budget["source_width"],
        height=budget["source_height"],
        quality=budget["source_jpeg_quality"],
    )

    event_id, fingerprint, preview = _current_file(
        event_dir,
        recipe,
    )
    preview_rgb = _decode(preview.payload)

    export = encode_jpeg_export(
        event_id=event_id,
        fingerprint=fingerprint,
        recipe=recipe,
        revision=1,
        options=JpegExportOptions(
            quality=budget["export_jpeg_quality"],
            icc_policy="omit",
            metadata_policy="strip",
        ),
    )
    export_rgb = _decode(export.payload)

    assert max(preview_rgb.shape[:2]) == budget["preview_max_edge"]
    assert export_rgb.shape[:2] == (
        budget["source_height"],
        budget["source_width"],
    )

    preview_height, preview_width = preview_rgb.shape[:2]
    export_downsampled = cv2.resize(
        export_rgb,
        (preview_width, preview_height),
        interpolation=cv2.INTER_AREA,
    )
    metrics = _diff_metrics(preview_rgb, export_downsampled)

    assert metrics["mean"] <= budget["mean_abs_error_max"]
    assert metrics["p95"] <= budget["p95_abs_error_max"]
    assert metrics["max"] <= budget["max_abs_error_max"]
