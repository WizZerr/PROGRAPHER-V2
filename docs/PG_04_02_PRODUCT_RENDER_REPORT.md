# PG-04.02 — Product Render Implementation Report

Date: 2026-10-04  
Status: **V**

## Implemented

PG-04.02 provides the product-side JPEG render path on top of the exact PG-04.01 renderer contract.

Deliverables:

- `backend/app/rendering/jpeg_product_render.py`
- `backend/app/api/routes/jpeg_render.py`
- `backend/tests/test_jpeg_product_render.py`
- `docs/PG_04_02_PRODUCT_RENDER_CONTRACT.md`

## Verified behavior

Manual delta verification was run against the PG-04.02 implementation from `main` without starting a hosted GitHub Actions run.

The local verification covered:

- full-resolution output == the shared PG-04.01 renderer applied to the normalized source,
- preview maximum edge of 1600 px,
- revision-scoped cache reuse,
- rejection of same revision with a different recipe,
- rejection of an old revision after a newer revision becomes current,
- rejection of stale approval via `assert_current_jpeg_revision()`,
- acceptance of the current revision,
- preview API provenance/revision headers,
- stale API request -> HTTP 409,
- current-revision API guard,
- Python compile/import of the new render/route delta.

All targeted checks passed.

## Regression provenance

The immediate parent baseline used by PG-04.02 had already passed the backend regression and training-tool compile in GitHub Actions run `37176350329`.

PG-04.02 changed only:

- the new product-render module,
- the new render API route,
- route registration,
- its regression test,
- workflow documentation.

Because hosted Actions minutes are exhausted, no redundant hosted run was triggered. The newly introduced delta was verified locally instead of claiming an unrun Actions result.

This is engineering verification only; it is not photographer-quality evidence.

## Result

PG-04.02 is **V**.

The next executable Part is **PG-04.03 — encoded JPEG export contract**.


## Windows real-file compatibility follow-up — 2026-10-05

Local Desktop verification exposed a real camera `.JPG` that Pillow identified
as an MPO/MPF container. The old decoder rejected it because it required
`opened.format == "JPEG"` even though the primary frame was JPEG-compatible.

The source contract now accepts only Pillow `JPEG` and `MPO` containers for
tracked `.jpg` / `.jpeg` files. MPO processing is explicitly limited to
primary frame 0; auxiliary frames are ignored. EXIF orientation, ICC conversion,
no-ICC policy, source hashing, revision guards and renderer semantics are unchanged.

Regression coverage was added both at the working-space decoder level and at the
product preview API level. This is a compatibility bug fix, not a new rendering
representation.
