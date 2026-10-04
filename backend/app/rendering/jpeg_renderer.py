from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np


JPEG_EDIT_RECIPE_SCHEMA_VERSION = 1
JPEG_EDIT_RECIPE_VERSION = "jpeg-recipe-j0-polynomial-v1"
JPEG_RENDERER_CONTRACT_VERSION = "jpeg-polynomial-rgb-renderer-v1"
JPEG_RECIPE_COLOR_SPACE = "sRGB_encoded_0_1"

POLYNOMIAL_FEATURE_NAMES = (
    "bias",
    "r",
    "g",
    "b",
    "r2",
    "g2",
    "b2",
    "rg",
    "rb",
    "gb",
)
OUTPUT_NAMES = ("r", "g", "b")


class JpegRecipeValidationError(ValueError):
    pass


def _coefficient_array(raw: Any) -> np.ndarray:
    try:
        coefficients = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise JpegRecipeValidationError(
            "recipe coefficients must be a finite numeric matrix"
        ) from exc

    expected = (len(POLYNOMIAL_FEATURE_NAMES), 3)
    if coefficients.shape != expected:
        raise JpegRecipeValidationError(
            f"recipe coefficients must have shape {expected}, got {coefficients.shape}"
        )
    if not np.isfinite(coefficients).all():
        raise JpegRecipeValidationError(
            "recipe coefficients must contain only finite values"
        )
    return coefficients


def build_polynomial_recipe(coefficients: Any) -> dict[str, Any]:
    clean = _coefficient_array(coefficients)
    return {
        "schema_version": JPEG_EDIT_RECIPE_SCHEMA_VERSION,
        "kind": "jpeg_edit_recipe",
        "recipe_version": JPEG_EDIT_RECIPE_VERSION,
        "renderer_contract_version": JPEG_RENDERER_CONTRACT_VERSION,
        "color_space": JPEG_RECIPE_COLOR_SPACE,
        "transform": {
            "type": "quadratic_rgb_polynomial",
            "feature_order": list(POLYNOMIAL_FEATURE_NAMES),
            "output_order": list(OUTPUT_NAMES),
            "coefficients": clean.tolist(),
            "clip_output_0_1": True,
        },
    }


def validate_jpeg_edit_recipe(recipe: dict[str, Any]) -> np.ndarray:
    if not isinstance(recipe, dict):
        raise JpegRecipeValidationError("JPEG EditRecipe must be an object")

    if recipe.get("schema_version") != JPEG_EDIT_RECIPE_SCHEMA_VERSION:
        raise JpegRecipeValidationError(
            "unsupported JPEG EditRecipe schema_version"
        )
    if recipe.get("kind") != "jpeg_edit_recipe":
        raise JpegRecipeValidationError(
            "unsupported JPEG EditRecipe kind"
        )
    if recipe.get("recipe_version") != JPEG_EDIT_RECIPE_VERSION:
        raise JpegRecipeValidationError(
            "unsupported JPEG EditRecipe version"
        )
    if (
        recipe.get("renderer_contract_version")
        != JPEG_RENDERER_CONTRACT_VERSION
    ):
        raise JpegRecipeValidationError(
            "JPEG EditRecipe renderer contract is incompatible"
        )
    if recipe.get("color_space") != JPEG_RECIPE_COLOR_SPACE:
        raise JpegRecipeValidationError(
            "JPEG EditRecipe color space is incompatible"
        )

    transform = recipe.get("transform")
    if not isinstance(transform, dict):
        raise JpegRecipeValidationError(
            "JPEG EditRecipe is missing transform"
        )
    if transform.get("type") != "quadratic_rgb_polynomial":
        raise JpegRecipeValidationError(
            "unsupported JPEG transform type"
        )
    if tuple(transform.get("feature_order") or ()) != POLYNOMIAL_FEATURE_NAMES:
        raise JpegRecipeValidationError(
            "JPEG recipe feature order is incompatible"
        )
    if tuple(transform.get("output_order") or ()) != OUTPUT_NAMES:
        raise JpegRecipeValidationError(
            "JPEG recipe output order is incompatible"
        )
    if transform.get("clip_output_0_1") is not True:
        raise JpegRecipeValidationError(
            "JPEG recipe must declare clip_output_0_1=true"
        )

    return _coefficient_array(transform.get("coefficients"))


def clone_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    validate_jpeg_edit_recipe(recipe)
    return deepcopy(recipe)


def polynomial_features(rgb: np.ndarray) -> np.ndarray:
    values = np.asarray(rgb, dtype=np.float64).reshape(-1, 3)
    r = values[:, 0]
    g = values[:, 1]
    b = values[:, 2]
    return np.column_stack(
        (
            np.ones_like(r),
            r,
            g,
            b,
            r * r,
            g * g,
            b * b,
            r * g,
            r * b,
            g * b,
        )
    )


def render_recipe_float(
    rgb_float: np.ndarray,
    recipe: dict[str, Any],
    *,
    chunk_pixels: int = 1_000_000,
) -> np.ndarray:
    coefficients = validate_jpeg_edit_recipe(recipe)

    image = np.asarray(rgb_float, dtype=np.float32)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("JPEG renderer expects HxWx3 RGB")
    if not np.isfinite(image).all():
        raise ValueError("JPEG renderer input contains non-finite values")
    if image.size and (float(image.min()) < 0.0 or float(image.max()) > 1.0):
        raise ValueError(
            "JPEG float renderer expects encoded RGB values in [0, 1]"
        )
    if chunk_pixels <= 0:
        raise ValueError("chunk_pixels must be greater than zero")

    flat = image.reshape(-1, 3)
    output = np.empty_like(flat, dtype=np.float32)

    for start in range(0, len(flat), chunk_pixels):
        end = min(start + chunk_pixels, len(flat))
        features = polynomial_features(flat[start:end])
        predicted = features @ coefficients
        output[start:end] = np.clip(
            predicted,
            0.0,
            1.0,
        ).astype(np.float32)

    return output.reshape(image.shape)


def render_recipe_uint8(
    image: np.ndarray,
    recipe: dict[str, Any],
) -> np.ndarray:
    source = np.asarray(image)
    if source.dtype != np.uint8:
        raise ValueError("JPEG uint8 renderer expects uint8 RGB input")
    if source.ndim != 3 or source.shape[2] != 3:
        raise ValueError("JPEG renderer expects HxWx3 RGB")

    result = render_recipe_float(
        source.astype(np.float32) / 255.0,
        recipe,
    )
    return np.clip(
        np.rint(result * 255.0),
        0,
        255,
    ).astype(np.uint8)


def render_coefficients_float(
    rgb_float: np.ndarray,
    coefficients: Any,
    *,
    chunk_pixels: int = 1_000_000,
) -> np.ndarray:
    """
    Compatibility adapter for research code.

    The renderer still validates and materializes a versioned EditRecipe before
    applying coefficients, so research and product semantics cannot diverge.
    """
    return render_recipe_float(
        rgb_float,
        build_polynomial_recipe(coefficients),
        chunk_pixels=chunk_pixels,
    )


def render_coefficients_uint8(
    image: np.ndarray,
    coefficients: Any,
) -> np.ndarray:
    return render_recipe_uint8(
        image,
        build_polynomial_recipe(coefficients),
    )


def identity_polynomial_recipe() -> dict[str, Any]:
    coefficients = np.zeros(
        (len(POLYNOMIAL_FEATURE_NAMES), 3),
        dtype=np.float64,
    )
    coefficients[1, 0] = 1.0
    coefficients[2, 1] = 1.0
    coefficients[3, 2] = 1.0
    return build_polynomial_recipe(coefficients)
