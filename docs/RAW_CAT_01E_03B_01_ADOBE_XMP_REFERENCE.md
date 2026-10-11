# RAW-CAT-01E.03B.01 — Independent Adobe XMP reference research

D-015 RAW-first, pre-G0 only. One photographer-owned RAW copy was checked against the source SHA-256, linked in an ISOLATED one-photo Lightroom validation catalog, and Adobe Lightroom wrote an XMP and a companion .acr. Neither content nor filenames nor user paths are stored in this repository. 10 Basic scalar fields agreed with the displayed Develop panel; one composite RGB curve looked qualitatively consistent. No numeric Adobe XMP comparison has yet run on Windows.

## Run with Lightroom CLOSED

From backend:

    python -m pytest -q tests/test_lightroom_adobe_xmp_comparison.py
    python -m app.photographer.lightroom_adobe_xmp_comparison --local-plan "LOCAL_PRIVATE_PLAN.json" --xmp "ADOBE_COPIED_EXPORT.xmp" --report "AGGREGATE_OUTSIDE_ADOBE_DIR.json"

Use absolute local paths in practice. The first input is the PRIVATE 01E.03A sampling plan. The second is an independently Adobe-generated XMP in the copied RAW folder, not a ProGrapher-generated sidecar.

The comparison requires a unique filename-stem match in the private plan (NOT photo identity proof), compares explicitly present global Adobe Camera Raw scalar fields plus flat supported ToneCurvePV2012 point curves, and marks omitted properties as not_exported rather than guessing zero. It ignores nested mask-local data. Companion .acr is only detected and never parsed or changed.

The output is AGGREGATE ONLY: field names/statuses and family counts, but never individual values, image IDs, private paths, dates or JPEG/RAW pixels. Share only the aggregate report; do NOT upload photographer RAW, XMP, .acr or private JSON plan. The source catalog and Adobe sidecars remain unchanged.

Numeric field agreement and matching coordinates do NOT establish tone interpolation/render parity, active masks, Look/profile interpretation, verified photographer finality, source provenance, or training eligibility. Only synthetic tests authored; Windows focused tests and real sidecar comparison PENDING.
