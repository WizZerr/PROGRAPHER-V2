# RAW-CAT-01E.04A — Lightroom Preview Index research

**Date:** 2026-10-11. **Scope:** isolated, pre-G0 D-015 research; not RAW training.

## Evidence observed locally (not yet reproduced in this code's Windows run)
- User's exported Lightroom catalog: 7,023 RAW records, Develop parsed with 0 exclusions.
- Preview folder: 15,811 files, 1.86 GB; 15,810 files without extensions all begin with JPEG signature, plus one approx. 7MB SQLite .db.
- Observed preview database tables: ImageCacheEntry(imageId, uuid, digest, orientation); Pyramid(uuid, digest, ...); PyramidLevel(uuid, digest, level, ...). This is schema evidence, NOT a proven photo-to-JPEG mapping.
- Lightroom Basic UI values matched ten extracted scalars for one missing-RAW entry; Tone Curve interface was disabled, therefore actual Adobe curve equivalence and Adobe XMP parity remain **UNVERIFIED**.

## Implementation
Run from backend with Lightroom CLOSED and the exported, finalized catalog and Preview cache COPY:

    python -m pytest -q tests/test_lightroom_preview_index.py
    python -m app.photographer.lightroom_preview_index --catalog "C:\path\to\catalog.lrcat" --previews-dir "C:\path\to\catalog Previews.lrdata" --report "C:\path\outside\RAW_CAT_01E_04A_REPORT.json"

The CLI reads BOTH SQLite databases in immutable/query-only mode; rejects a nonempty WAL; checks schema, raw key overlaps against imageId (both id_local and id_global), preview-index pyramid links and all file signatures, and emits **aggregate-only JSON**. It reads three JPEG header bytes, never decodes or exports an image. It never writes catalog/cache/RAW and refuses to put the report within the cache.

## Limits and gate
Overlapping numeric/string keys demonstrate candidate key linkage, not photographed-image identity. The cache may contain multiple levels or derivatives. Matching Pyramid/PyramidLevel proves DB linkage only; does NOT link an on-disk JPEG to a photo until separately verified with explicit version-specific mapping. Preview JPEGs may already contain edits and cannot stand in for source RAW/unedited Smart Previews. Photographer permission, source provenance, finality, event splits, XMP/Adobe parity and Brain training remain blocked. 01E.04A synthetic tests were authored; **Windows real-cache validation pending**. Share aggregate report only; never share personal photo IDs or paths.
