# PG-04.07 — RAW/XMP Safety and Truth Boundary

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Scope

Release-1 RAW remains an assisted Lightroom/XMP path.

PG-04.07 does not create an independent ProGrapher RAW developer and does not treat the on-screen approximation as an Adobe-equivalent final render.

## Existing round-trip contract retained

The existing Lightroom bridge already provides:

- known recipe -> separate reference XMP,
- XMP readback through the Dataset reader,
- field-by-field recipe comparison,
- missing remains missing / zero remains zero,
- RAW SHA-256 before and after,
- explicit Lightroom evidence/provenance contracts.

Reference XMP uses a `.prographer-reference.xmp` name in a separate work directory.

## Product sidecar protection

Testing/product-side XMP export:

- never opens RAW for writing,
- hashes RAW before and after,
- refuses to replace an XMP without the ProGrapher marker,
- writes through a temporary XMP,
- rechecks RAW before promotion,
- updates only XMP that ProGrapher previously created,
- preserves the previous good ProGrapher XMP when a RAW change is detected before promotion,
- rolls back the previous XMP if RAW changes after promotion,
- removes a first-time export if RAW changes after promotion,
- cleans temporary/rollback files.

A failed operation is not reported as a valid export.

## UI truth boundary

RAW Darkroom semantics remain Lightroom/XMP semantics:

- Exposure,
- Temperature in Kelvin,
- Lightroom/Camera Raw Tint.

The RAW preview is explicitly labeled as approximate:

`תצוגה משוערת בלבד · התוצאה הסופית נקבעת ב-Lightroom.`

RAW export remains labeled `ייצוא XMP`.

JPEG has its own real renderer path and normalized control semantics; the two are not presented as equivalent.

## Outside this Part

Real Lightroom Classic ingestion/render comparison and real macOS Lightroom evidence remain later hardware/reference gates.
