# PG-01.04 — Portable Profile Package Preparation Report

Date: 2026-10-04  
Status: **◐ ENGINEERING-VERIFIED / G0 RATIFICATION BLOCKED**

## Added

- `backend/app/profiles/package.py`
- `backend/app/profiles/__init__.py`
- `backend/tests/test_profile_package.py`
- `docs/PG_01_04_PROFILE_PACKAGE_CONTRACT.md`

## Implemented preparation

- portable ZIP package,
- canonical manifest,
- UUID identity,
- weights + normalizer required roles,
- model/feature/recipe/renderer versions,
- engine compatibility range,
- metrics,
- artifact size/SHA-256 integrity,
- safe archive paths,
- symlink/unexpected-member rejection,
- atomic import,
- immutable local ProfileVersion directory,
- fail-closed compatibility,
- optional whole-archive SHA verification against future ProfileVersion registry metadata,
- streaming artifact package/import for large weights,
- source-artifact mutation detection during package creation.

## Regression fixtures authored

- load after package move/rename,
- renderer incompatibility,
- engine incompatibility,
- tampered artifact,
- missing normalizer,
- duplicate immutable version install.

## Status rule

This implementation is intentionally **not V**.

Phase 01 requires G0. PG-00.02 remains paused by product-owner decision, so PG-01.04 may be prepared and tested but cannot be ratified/completed yet.

No Auth, Supabase or Cloud implementation was started.


## Manual engineering verification

A targeted local harness was executed against the exact committed `backend/app/profiles/package.py` from `main`.

PASS:

- package copied/renamed to a new path loads successfully,
- artifact bytes survive portable import,
- renderer-contract incompatibility rejects before final install,
- engine-version incompatibility rejects before final install,
- whole-archive registry SHA mismatch rejects before final install,
- tampered artifact bytes reject before final install,
- missing required normalizer role rejects package creation,
- an installed immutable ProfileVersion cannot be replaced,
- non-integer version numbers are rejected rather than truncated.

The latest implementation also streams artifact bytes during package creation/import rather than loading large weights wholesale into memory.

## Completion status

Engineering verification is green, but PG-01.04 remains **◐**, not V.

Reason: Phase 01 entry requires G0 and explicit ratification. PG-00.02/G0 remains paused by product-owner decision. No Cloud/Auth work is required or started here.
