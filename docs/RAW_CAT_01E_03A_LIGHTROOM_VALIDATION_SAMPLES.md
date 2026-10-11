# RAW-CAT-01E.03A — LOCAL Lightroom validation sampling

**Date:** 2026-10-11. **Lane:** RAW-first D-015 / isolated pre-G0 engineering research.

### Purpose
Select small photo-level candidate set from already-decoded catalog Develop data for **independent Adobe Lightroom Classic comparison**. This is **NOT** XMP equivalence, not source-RAW matching, not model training, and not a claim of true edited/final photos.

### Privacy and source safety
- Reads exported COPY of `.lrcat` in immutable/query-only mode using `inspect_catalog(..., include_private=True)`.
- Prints and writes only path-free, ID-free aggregate category counts to `--report`.
- Requires **separate** `--local-plan` containing photo names, IDs, current decoded scalar values, curve points and opaque fingerprints; NEVER upload this file or commit it to GitHub.
- Source catalog and camera photos are never written/modified.
- No external Adobe XMP references are produced or fabricated. Do not use our own generated XMP as Adobe parity ground truth.

### Categories
Linear/reference curves, nonlinear RGB composite and per-channel curves, HSL mixer, B&W conversion and gray mixer, Color Grading **excluding configuration Blending/Balance**, legacy Split Toning, and opaque mask/retouch evidence. Labels say **candidate** or **unverified**; no active/final-edit inference. Candidate groups are NOT confirmed events.

### Windows validation
1. Run `python -m pytest -q tests/test_curve_semantics.py tests/test_raw_catalog_intake.py tests/test_develop_color_semantics.py tests/test_lightroom_validation_plan.py`.
2. After closing Lightroom, run:
```powershell
python -m app.photographer.lightroom_validation_plan --catalog "PATH_TO_EXPORTED_CATALOG.lrcat" --report "AGGREGATE.json" --local-plan "PRIVATE_DO_NOT_UPLOAD.json" --per-category 2
```
3. Share **only aggregate**. Use private candidate plan locally to inspect Develop controls on a Lightroom catalog COPY **without modifying or syncing**; record any Adobe UI vs metadata mismatch locally.
4. True independent Lightroom XMP / full visual parity and 01E.03B comparison require original RAW or otherwise valid independent Adobe-exported reference. Source matching, event/finality/consent and G1 remain blocked pending approved RAW.

### Evidence boundary
Synthetic unit/integration tests were added; Windows and real-catalog run are pending. All training-ready counts remain zero.
