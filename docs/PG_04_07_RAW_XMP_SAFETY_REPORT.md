# PG-04.07 — RAW/XMP Safety Report

Date: 2026-10-04  
Status: **V**

## Existing round-trip evidence retained

The repository already contains:

- `test_lightroom_roundtrip.py`,
- `test_lightroom_roundtrip_missing_values.py`,
- XMP mapping tests,
- testing-loop coverage proving RAW bytes stay unchanged,
- testing-loop coverage that foreign/unmarked XMP is not replaced.

## Hardening verified

`backend/app/testing/sidecar.py` now protects a previous good ProGrapher XMP across mid-export source changes.

Focused manual harness PASS:

- normal marked XMP write,
- foreign/unmarked XMP remains byte-identical,
- RAW change before promotion leaves previous ProGrapher XMP untouched,
- RAW change after promotion restores the previous ProGrapher XMP,
- first-time export is removed if RAW changes after promotion,
- temporary and rollback files are cleaned.

## UI truth verification

Committed Darkroom source confirms:

- RAW preview is labeled `תצוגה משוערת בלבד · התוצאה הסופית נקבעת ב-Lightroom.`,
- RAW action remains `ייצוא XMP`,
- JPEG preview is separately labeled as a real shared-renderer preview,
- JPEG and RAW control semantics are not presented as equivalent.

## Boundary

This closes the ProGrapher-side RAW/XMP safety/truth requirement only.

Real Lightroom Classic ingestion/render evidence and real macOS Lightroom evidence remain later hardware/reference gates and are not claimed here.

## Result

PG-04.07 is **V**.

**Phase 04 is complete.**
