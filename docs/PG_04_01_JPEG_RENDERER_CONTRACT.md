# PG-04.01 — Shared JPEG EditRecipe & Renderer Contract

Date: 2026-10-04  
Status: implementation prepared; verification by CI required before marking V.

## Purpose

The JPEG renderer is a product-side shared engine, not a helper owned by J0.

Research, prediction, preview and future export must interpret the same JPEG EditRecipe contract.

## Canonical module

`backend/app/rendering/jpeg_renderer.py`

The module owns:

- JPEG EditRecipe schema/version,
- renderer contract version,
- polynomial feature order,
- recipe validation,
- deterministic recipe rendering,
- identity recipe,
- compatibility adapters for existing coefficient-based research code.

## Current versions

- Recipe schema: `1`
- Recipe version: `jpeg-recipe-j0-polynomial-v1`
- Renderer contract: `jpeg-polynomial-rgb-renderer-v1`
- Recipe color domain: `sRGB_encoded_0_1`

These names describe the current narrow representation. They are not a promise that this will be the final commercial representation after real-photographer J0.

## EditRecipe shape

```json
{
  "schema_version": 1,
  "kind": "jpeg_edit_recipe",
  "recipe_version": "jpeg-recipe-j0-polynomial-v1",
  "renderer_contract_version": "jpeg-polynomial-rgb-renderer-v1",
  "color_space": "sRGB_encoded_0_1",
  "transform": {
    "type": "quadratic_rgb_polynomial",
    "feature_order": ["bias", "r", "g", "b", "r2", "g2", "b2", "rg", "rb", "gb"],
    "output_order": ["r", "g", "b"],
    "coefficients": "... 10x3 finite numeric matrix ...",
    "clip_output_0_1": true
  }
}
```

Unsupported versions, feature orders, output orders, coefficient shapes or non-finite values fail explicitly.

There is no silent clipping of recipe parameters into another contract.

## Rendering semantics

Input:

- H×W×3 RGB,
- either uint8 0–255 or float encoded RGB 0–1,
- already normalized to the JPEG working-space contract before rendering.

Transform:

1. generate the declared ordered polynomial feature vector,
2. multiply by the 10×3 coefficient matrix,
3. clip output to 0–1,
4. convert to uint8 only at the uint8 boundary.

Chunk size is an implementation detail and must not change output.

## Current consumers

### J0

`jpeg_j0_feasibility.py` still exposes compatibility wrappers for old research imports, but the actual polynomial feature/render implementation now delegates to the shared renderer.

J0 recipe JSON is produced by `build_polynomial_recipe()`, then extended only with J0 fit/evidence metadata.

### J0 Real Batch

Loaded J0 recipe files are validated with `validate_jpeg_edit_recipe()` before becoming target material.

### J1 Synthetic / J1 Real / Locked Test

Coefficient predictions are rendered through the shared renderer compatibility adapter, which materializes and validates the same versioned EditRecipe semantics before rendering.

### Artifact provenance

The renderer version used in target/candidate identity is sourced from the same shared renderer module. There is no second hard-coded renderer version in provenance.

## Product boundary

PG-04.01 defines the single rendering meaning.

PG-04.02 will make product preview/full-resolution rendering consume this engine and add revision/cache behavior.

PG-04.03/04.04 will add encoded JPEG export and atomic filesystem behavior without creating a second edit interpretation.

## Compatibility policy

A future material change to:

- feature order,
- transform type,
- clipping semantics,
- working color interpretation,
- coefficient meaning,

requires a new Recipe and/or Renderer contract version.

Old Candidates remain preserved under their original provenance and are not silently loaded through a newer incompatible renderer.

## Verification

`backend/tests/test_jpeg_renderer.py` verifies:

- exact identity rendering,
- coefficient adapter == versioned recipe rendering,
- chunk-size invariance,
- rejection of incompatible version/feature order,
- rejection of invalid/non-finite coefficients,
- rejection of invalid input domains,
- J0 recipe payload compatibility with the shared contract,
- artifact provenance uses the renderer version from the shared engine.
