# PG-04.06 — JPEG UI Control Mapping Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / DARKROOM WIRING PENDING**

## Backend added

- `backend/app/rendering/jpeg_controls.py`
- `backend/app/api/routes/jpeg_controls.py`
- `backend/tests/test_jpeg_controls.py`

## Current contract

JPEG controls are normalized, global controls:

- brightness,
- contrast,
- warmth,
- tint.

All are -100..100.

Temperature in Kelvin and Lightroom Tint equivalence are explicitly false in the contract.

## Remaining before V

- wire the JPEG Darkroom panel to the real control-preview API,
- replace PR1 JPEG view-only copy,
- ensure stale async preview responses cannot replace newer control state,
- run targeted backend/frontend delta verification.
