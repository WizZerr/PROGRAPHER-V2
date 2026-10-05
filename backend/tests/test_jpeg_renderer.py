from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from app.evaluation.artifact_provenance import RENDERER_CONTRACT_VERSION
from app.rendering.jpeg_renderer import (
    JPEG_EDIT_RECIPE_VERSION,
    JPEG_RENDERER_CONTRACT_VERSION,
    JpegRecipeValidationError,
    POLYNOMIAL_FEATURE_NAMES,
    build_polynomial_recipe,
    identity_polynomial_recipe,
    polynomial_features,
    render_coefficients_uint8,
    render_recipe_float,
    render_recipe_uint8,
    validate_jpeg_edit_recipe,
)


TRAINING_LAB = Path(__file__).resolve().parents[1] / "training_lab"
if str(TRAINING_LAB) not in sys.path:
    sys.path.insert(0, str(TRAINING_LAB))

from jpeg_j0_feasibility import _recipe_payload


def _image() -> np.ndarray:
    yy, xx = np.mgrid[0:96, 0:144].astype(np.float32)
    r = 30 + 180 * (xx / 143.0)
    g = 20 + 160 * (yy / 95.0)
    b = 40 + 90 * (1.0 - xx / 143.0) + 60 * (yy / 95.0)
    return np.clip(
        np.stack((r, g, b), axis=2),
        0,
        255,
    ).astype(np.uint8)


def _warm_coefficients() -> np.ndarray:
    coefficients = np.zeros(
        (len(POLYNOMIAL_FEATURE_NAMES), 3),
        dtype=np.float64,
    )
    coefficients[0] = [0.01, 0.0, -0.01]
    coefficients[1, 0] = 1.04
    coefficients[2, 1] = 1.00
    coefficients[3, 2] = 0.96
    return coefficients


def test_identity_recipe_is_pixel_identity() -> None:
    source = _image()
    recipe = identity_polynomial_recipe()

    rendered = render_recipe_uint8(source, recipe)

    assert recipe["recipe_version"] == JPEG_EDIT_RECIPE_VERSION
    assert (
        recipe["renderer_contract_version"]
        == JPEG_RENDERER_CONTRACT_VERSION
    )
    assert np.array_equal(rendered, source)


def test_coefficient_adapter_and_versioned_recipe_have_same_semantics() -> None:
    source = _image()
    coefficients = _warm_coefficients()
    recipe = build_polynomial_recipe(coefficients)

    via_recipe = render_recipe_uint8(source, recipe)
    via_adapter = render_coefficients_uint8(source, coefficients)

    assert np.array_equal(via_recipe, via_adapter)


def test_float_renderer_is_chunk_size_independent() -> None:
    source = _image().astype(np.float32) / 255.0
    recipe = build_polynomial_recipe(_warm_coefficients())

    small_chunks = render_recipe_float(
        source,
        recipe,
        chunk_pixels=37,
    )
    large_chunks = render_recipe_float(
        source,
        recipe,
        chunk_pixels=1_000_000,
    )

    assert np.array_equal(small_chunks, large_chunks)


def test_recipe_contract_rejects_incompatible_version_and_feature_order() -> None:
    recipe = build_polynomial_recipe(_warm_coefficients())

    wrong_version = {
        **recipe,
        "recipe_version": "jpeg-recipe-v999",
    }
    with pytest.raises(
        JpegRecipeValidationError,
        match="version",
    ):
        validate_jpeg_edit_recipe(wrong_version)

    wrong_order = {
        **recipe,
        "transform": {
            **recipe["transform"],
            "feature_order": list(reversed(POLYNOMIAL_FEATURE_NAMES)),
        },
    }
    with pytest.raises(
        JpegRecipeValidationError,
        match="feature order",
    ):
        validate_jpeg_edit_recipe(wrong_order)


def test_recipe_contract_rejects_invalid_coefficients() -> None:
    with pytest.raises(
        JpegRecipeValidationError,
        match="shape",
    ):
        build_polynomial_recipe(np.zeros((3, 3), dtype=np.float64))

    invalid = np.zeros(
        (len(POLYNOMIAL_FEATURE_NAMES), 3),
        dtype=np.float64,
    )
    invalid[0, 0] = np.nan
    with pytest.raises(
        JpegRecipeValidationError,
        match="finite",
    ):
        build_polynomial_recipe(invalid)


def test_renderer_rejects_invalid_input_domain() -> None:
    recipe = identity_polynomial_recipe()

    with pytest.raises(ValueError, match="uint8"):
        render_recipe_uint8(
            _image().astype(np.float32),
            recipe,
        )

    invalid_float = _image().astype(np.float32) / 255.0
    invalid_float[0, 0, 0] = 1.2
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        render_recipe_float(
            invalid_float,
            recipe,
        )


def test_j0_recipe_payload_is_a_shared_renderer_recipe(tmp_path: Path) -> None:
    coefficients = _warm_coefficients()
    payload = _recipe_payload(
        coefficients,
        source_path=tmp_path / "original.jpg",
        target_path=tmp_path / "edited.jpg",
        geometry_action="same_dimensions",
        sample_pixels=120000,
        ridge_lambda=1e-4,
    )

    recovered = validate_jpeg_edit_recipe(payload)

    assert np.allclose(recovered, coefficients)
    assert payload["kind"] == "jpeg_edit_recipe"
    assert payload["production_ready"] is False
    assert payload["fit"]["geometry_action"] == "same_dimensions"


def test_artifact_provenance_uses_shared_renderer_version() -> None:
    assert RENDERER_CONTRACT_VERSION == JPEG_RENDERER_CONTRACT_VERSION



def test_linear_recipe_fast_path_matches_explicit_polynomial_math() -> None:
    rng = np.random.default_rng(406)
    source = rng.random((37, 53, 3), dtype=np.float32)

    coefficients = np.zeros(
        (len(POLYNOMIAL_FEATURE_NAMES), 3),
        dtype=np.float64,
    )
    coefficients[0] = [0.01, -0.02, 0.03]
    coefficients[1] = [1.03, 0.0, 0.0]
    coefficients[2] = [0.0, 0.97, 0.0]
    coefficients[3] = [0.0, 0.0, 1.01]
    recipe = build_polynomial_recipe(coefficients)

    actual = render_recipe_float(source, recipe, chunk_pixels=211)

    flat = source.reshape(-1, 3)
    expected = np.clip(
        polynomial_features(flat) @ coefficients,
        0.0,
        1.0,
    ).astype(np.float32).reshape(source.shape)

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-7)
