# PG-04.01 — Shared JPEG Renderer Implementation Report

Date: 2026-10-04  
Status: **V**  
Relevant CI evidence: PR1 validation run `37176350329` — backend regression PASS, backend training-tool compile PASS.

## Deliverables

- `backend/app/rendering/jpeg_renderer.py`
- `backend/app/rendering/__init__.py`
- `backend/tests/test_jpeg_renderer.py`
- `docs/PG_04_01_JPEG_RENDERER_CONTRACT.md`

## Result

JPEG rendering semantics no longer belong to `training_lab/jpeg_j0_feasibility.py`.

The canonical renderer and EditRecipe contract now live under the application package.

Current contract:

- Recipe schema: `1`
- Recipe version: `jpeg-recipe-j0-polynomial-v1`
- Renderer version: `jpeg-polynomial-rgb-renderer-v1`
- Color domain: `sRGB_encoded_0_1`

## Wired consumers

The same renderer semantics are now used by:

- J0 reconstruction,
- J0 recipe generation/validation,
- J1 synthetic rendering,
- J1 real Validation rendering,
- locked-Test rendering,
- artifact provenance renderer versioning.

J0 retains compatibility wrappers only so old research imports do not break; the implementation behind those wrappers is the shared engine.

## Validation

The renderer regression proves:

- identity recipe is pixel-identical,
- coefficient adapter and versioned EditRecipe produce identical output,
- chunk size does not alter render output,
- incompatible versions/feature orders fail,
- invalid/non-finite coefficient matrices fail,
- invalid input domain fails,
- J0 recipe payload is accepted by the shared validator,
- provenance uses the renderer version exported by the shared engine.

## Boundary to next Parts

PG-04.01 owns the meaning of JPEG EditRecipe and rendering.

PG-04.02 adds product preview/full-resolution execution, revision/cache behavior and stale-preview protection.

PG-04.03/04.04 add JPEG encoding/export/filesystem semantics.

Those Parts must call this renderer rather than define another edit interpretation.
