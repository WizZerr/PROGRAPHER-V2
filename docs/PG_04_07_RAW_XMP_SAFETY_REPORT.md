# PG-04.07 — RAW/XMP Safety Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Existing evidence retained

The repository already contains:

- `test_lightroom_roundtrip.py`
- `test_lightroom_roundtrip_missing_values.py`
- XMP mapping tests,
- testing-loop coverage proving RAW bytes stay unchanged,
- coverage that foreign/unmarked XMP is not replaced.

## Hardening added

`backend/app/testing/sidecar.py` now protects a previous good ProGrapher sidecar across mid-export source changes.

New regression file:

`backend/tests/test_pg_04_07_raw_xmp_safety.py`

Cases:

- foreign XMP never replaced,
- RAW change before promotion preserves previous sidecar,
- RAW change after promotion restores previous sidecar,
- first-time export is removed when RAW changes after promotion,
- temp/rollback artifacts are cleaned.

## Remaining before V

Run the focused RAW/XMP safety harness and verify the committed Darkroom still labels RAW preview as approximate/Lightroom-owned and exports XMP rather than claiming a final standalone RAW render.
