# PG-04.05 — JPEG Reference / Golden Render Report

Date: 2026-10-04  
Status: **V**

## Added

- `backend/tests/fixtures/jpeg_golden_cases_v1.json`
- `backend/tests/test_jpeg_reference_renders.py`
- `docs/PG_04_05_JPEG_GOLDEN_RENDER_CONTRACT.md`

## Frozen semantic cases

- identity,
- tone/color,
- deliberate clipping.

For the deterministic 64x48 RGB fixture, all frozen:

- RGB SHA-256 values,
- mean RGB values,
- clipping fractions,
- selected pixel probes

matched exactly in the manual golden harness.

## Encoded JPEG budgets

Reopened JPEG pixel error versus reference rendered RGB:

- identity: mean 2.434, p95 7, max 20,
- tone/color: mean 2.481, p95 8, max 20,
- clipping: mean 2.225, p95 7, max 21.

Frozen limits:

- mean <= 3.0,
- p95 <= 10,
- max <= 30.

All PASS.

## Large-image preview agreement

Deterministic 2400x1600 tone/color case:

- preview maximum edge: 1600,
- preview vs reopened/full-export downsample mean error: 1.404,
- p95 error: 4,
- max error: 33.

Frozen limits:

- mean <= 2.0,
- p95 <= 6,
- max <= 40.

PASS.

## Interpretation

These results prove deterministic renderer/preview/export agreement within the frozen engineering budget.

They do not prove photographer preference, style learning or AI quality.

Hosted Actions was not triggered because the monthly hosted-runner allowance remains exhausted.

## Result

PG-04.05 is **V**.

Next executable Part: **PG-04.06 — JPEG UI controls -> renderer mapping**.
