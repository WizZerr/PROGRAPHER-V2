# PG-04.02 — Product Render Implementation Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Implemented

PG-04.02 now has a product-side JPEG render path based on the exact PG-04.01 renderer contract.

Added:

- `backend/app/rendering/jpeg_product_render.py`
- `backend/app/api/routes/jpeg_render.py`
- `backend/tests/test_jpeg_product_render.py`
- `docs/PG_04_02_PRODUCT_RENDER_CONTRACT.md`

Updated:

- API router registration,
- Master Plan status,
- Project State,
- Execution Board.

## Behavior

- preview and full-resolution consume the same normalized source and the same JPEG EditRecipe semantics,
- preview is bounded to 1600 px maximum edge,
- full-resolution preserves normalized source dimensions,
- transient render transport is PNG so PG-04.02 does not pre-empt PG-04.03 JPEG export policy,
- cache is scoped by immutable revision/provenance,
- same revision + different recipe is rejected,
- old revision is rejected after a newer revision becomes current,
- `assert_current_jpeg_revision()` is the required guard for future approval/save behavior.

## Verification state

Automated tests are authored but no hosted GitHub Actions run was started.

Reason: hosted Actions usage is already at the monthly limit, and the project policy is to avoid wasting runs until reset or manual CI is available.

Therefore this Part is not marked V yet.

## Exact remaining gate for V

Run:

- `backend/tests/test_jpeg_product_render.py`,
- backend regression suite,
- training-tool / backend compile checks used by the current workflow.

If all pass on the committed main SHA, update PG-04.02 from `◐` to `V` and continue to PG-04.03.
