# PG-04.05 — JPEG Reference / Golden Render Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Added

- `backend/tests/fixtures/jpeg_golden_cases_v1.json`
- `backend/tests/test_jpeg_reference_renders.py`
- `docs/PG_04_05_JPEG_GOLDEN_RENDER_CONTRACT.md`

## Frozen cases

- identity,
- tone/color,
- clipping,
- large-image preview vs encoded-export agreement.

## Evidence required for V

- renderer RGB SHA/probe/mean/clipping goldens pass,
- encoded JPEG reopened-pixel budgets pass,
- large preview vs downsampled export budgets pass,
- no photographer-quality claim is inferred from these technical fixtures.

Hosted Actions remains intentionally unused while the monthly hosted-runner allowance is exhausted.
