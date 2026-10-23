# PG-LI-02B.01b — Git-bundled Smart Preview JPEG XL decoder (research)

**Branch:** `feature/pg-learning-onboarding-00-02`  
**Scope:** Author-supplied decoder integrated into ProGrapher V2's local backend.  
**Authorization:** The user expressly confirmed permission and lawful use in chat on 2026-10-23. This is not a replacement for documenting commercial redistribution terms with the rights holder before release.

## Exactly what was imported

The *seven unchanged decoder source/data files* supplied in `smart_preview_decoder_v1.zip` are committed as one reproducible, source-only archive:
`backend/vendor/smart_preview_decoder_source.tar.xz`

- Contains: `__init__.py`, `dng.py`, `profile.py`, `render.py`, `lens.py`, `metrics.py`, `data/tone_curve.json`.
- Archive SHA-256: `0eddbb1b6dfa0806c8df5e8e2c0325fb39de84cd1a4e4d8d4de7eda2313e6c9b`.
- Original developer's README, VALIDATION, research scripts and test fixture are not runtime dependencies; conclusions were summarized in this document and earlier PR notes. The source-only archive is a source distribution, not a proprietary compiled binary.
- The tone curve and calibration code are included for provenance but **not invoked** by the primary DNG preflight. Only `decode_smart_preview(..., long_edge=1024).linear` is used to prove pixel extraction.

## How it now works (no manual ZIP)

`app.learning_intake.decoder_vendor.load_decoder_package()` automatically:
1. Finds the source archive checked out from Git.
2. Validates its SHA-256 before extracting.
3. Extracts only the seven allowlisted files to `PROGRAPHER_DATA_DIR/vendor_cache/` using a temporary staging directory and an integrity marker.
4. Imports `smart_preview_decoder` from that local cache. It does **not** need a `Downloads` ZIP or separate installation command.
5. If the archive is missing/altered, refuses to use it; originals remain untouched.

`smart_preview_probe.py` identifies DNG JPEG XL Compression=52546 using bounded TIFF IFD metadata. This path routes to the bundled decoder instead of `rawpy`. Other compression tags still use the previous LibRaw research path.

### Native Python dependencies

`backend/requirements-lock.txt` now includes:
- `imagecodecs==2026.10.10` (JPEG XL support available in the Windows CPython 3.12 wheel)
- `tifffile==2026.9.20`

**A Git pull does not automatically install Python dependencies into an existing virtualenv.** From the existing Windows test worktree after `git pull --ff-only`:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q tests\test_smart_preview_probe.py tests\test_learning_preflight.py tests\test_learning_intake.py
cd ..\frontend
npm.cmd run lint
npm.cmd run build
```

Then run Tauri using the previously separated test DATA_DIR and CACHE_DIR. In the existing learning profile, choose **בדוק מדגם + Smart Previews אוטומטית**. The first probe automatically extracts the bundled decoder to local application cache.

### Expected output

- 3,184 DNG TIFF-signature candidates in the user-provided prior sample (not guaranteed across future catalogs)
- Compression 52546 detected if the sample actually uses JPEG XL
- At most four `jpegxl_dng_decoded_unverified` if real DNG decoding succeeds
- Clear error if JPEG XL codec unavailable, package checksum mismatch, or unsupported DNG opcodes
- Zero training-ready samples; raw identity, Lightroom baseline and final photographer edits still unverified.

## Quality and product gates

The supplied author reports Reset-parity against Lightroom, including an 80-photo held-out sample, but we **have not independently repeated that benchmark** on this catalog.

Before training on this decoded data, we still must:
1. Verify real JPEG XL DNG decoding on the user's machine, report bounded diagnostic status.
2. Verify camera / lens / Adobe Color rendering and Lightroom Import-vs-Reset parity using controlled exports.
3. Verify Lightroom UUID-to-DNG identity (including virtual copies) and approved finality of the Develop recipe.
4. Hold out entire future events for validation and block data leakage.
5. Validate native JPEG XL codec crash isolation and Windows/macOS packaging before commercial distribution.

All operations in this Part are READ ONLY on Lightroom source paths. The automatic local cache contains *only the decoder's source code*, never photographer images.
