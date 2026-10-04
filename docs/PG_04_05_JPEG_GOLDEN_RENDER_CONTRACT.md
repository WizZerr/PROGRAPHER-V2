# PG-04.05 — JPEG Reference / Golden Render Contract

Date: 2026-10-04  
Status: implementation committed; verification required before V.

## Purpose

PG-04.05 freezes technical reference cases so future changes to the JPEG renderer, preview path or encoder cannot silently change product output.

These are engineering goldens. They do not represent photographer style or AI quality.

## Two-layer golden strategy

### 1. Renderer semantic goldens

A deterministic 64x48 RGB source is generated with integer formulas.

For each frozen recipe:

- full rendered RGB SHA-256 is fixed,
- mean RGB is fixed,
- clipping fraction is fixed,
- selected pixel probes are fixed.

Cases:

- identity,
- tone/color transform,
- deliberate clipping.

This layer catches changes to the shared EditRecipe/renderer semantics independently of JPEG encoding.

### 2. Encoded JPEG error budgets

JPEG byte hashes are deliberately not frozen.

Different libjpeg/Pillow builds can produce different compressed bytes while decoding to equivalent pixels. The product truth is therefore measured after reopening the encoded JPEG.

For identity, tone/color and clipping cases the reopened JPEG is compared with the reference rendered RGB using:

- mean absolute channel error,
- 95th percentile absolute channel error,
- maximum absolute channel error.

The frozen budgets are stored in:

`backend/tests/fixtures/jpeg_golden_cases_v1.json`

## Large-image preview agreement

A deterministic 2400x1600 JPEG is rendered with the frozen tone/color recipe.

The test compares:

- product preview at its 1600-pixel maximum edge,
- full-resolution encoded JPEG reopened and then downsampled to preview dimensions.

Frozen budgets limit mean, p95 and maximum channel deviation.

This explicitly measures the known ordering difference:

- preview: downsample source -> render,
- export: render full resolution -> JPEG encode -> reopen -> downsample.

## Why no photographer images

PG-04.05 validates renderer/preview/export mechanics only.

Real photographer images remain reserved for PG-06+ quality gates and are not needed to prove deterministic technical behavior.

## Change policy

A future renderer/encoder change that breaks these goldens is not accepted by updating hashes automatically.

The change must state why the product contract changed, create a new versioned fixture if intentional, and retain the old reference for comparison.
