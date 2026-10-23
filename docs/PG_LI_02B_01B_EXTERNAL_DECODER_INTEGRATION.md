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

## Review fixes (2026-10-23)

- **SubIFD routing.** `dng_diagnostics` now follows SubIFDs (tag 330) written as TIFF type IFD (13) as well as LONG.
  In a Lightroom Smart Preview the JPEG XL image (52546) sits in a SubIFD. Before this fix, a file that wrote 330 as type IFD
  reported only the thumbnail's compression, was routed to LibRaw and failed as `unsupported_or_corrupt_dng`.
  Whether Lightroom itself writes LONG or IFD is still to be confirmed on a real file.
  Check with: `python -c "import tifffile; print(tifffile.TiffFile(r'<smart preview>.dng').pages[0].tags[330].dtype)"`.
- **Real decode test.** `test_real_bundled_decoder_on_synthetic_jpegxl_smart_preview` runs the probe with nothing mocked,
  on a synthetic Lightroom-layout Smart Preview: thumbnail IFD0, then a LinearRaw JPEG XL SubIFD, 3 cubic MapPolynomials and an embedded profile.
  It checks the routing and the decode status. It also checks that the pinned tifffile/imagecodecs return the stored JPEG XL samples
  unchanged: the layer-1 output must equal the hand-computed DNG-spec result. The test is skipped if the JPEG XL codec is unavailable.
- **Cache integrity.** On every load, `decoder_vendor` now re-hashes the cached decoder files against the verified archive.
  If a file was edited it rebuilds the cache, and it deletes cached bytecode before import.

Still open: Lightroom Reset colour parity was measured with the author's local package versions, not with the pinned ones.
To repeat it with the backend venv, run the author's `tools/validate_against_lightroom.py` on the camera-test catalog.

## Layer 2-3: the unedited "before" image (2026-10-23)

For every sample that decodes cleanly, the probe now also renders the Smart Preview the way Lightroom shows it after **Reset**, using the bundled `render_srgb`:
- Adobe Color look, As Shot white balance, BaselineExposure plus the author's calibration (−0.144 stops), and the learned default tone curve.
- The photographer's Develop settings are never read. The main Smart Preview image is the unedited sensor data. Its small embedded 256 px preview may show edits and is never used.
- `app/learning_intake/smart_preview_render.py` produces a 512 px JPEG. It is held **in memory** and returned as base64 in `decoded_samples[].reset_render`, and the panel shows it as "לפני עריכה". It is never written to disk.
- The render needs Adobe's `Adobe Color.xmp`, which is Adobe's file and is not bundled. It is looked up in this order:
  1. `PROGRAPHER_ADOBE_COLOR_XMP`
  2. `<data dir>/adobe_profiles/Adobe Color.xmp`
  3. Adobe's CameraRaw settings and Lightroom install folders, as a bounded read-only walk
- If the file is not found, the render falls back to the look table embedded in the Smart Preview's own profile and reports `look_source: "smart_preview_profile"`. In the author's benchmark this fallback was nearly as close to Lightroom: 3.57% pixel error versus 3.48% with Adobe Color.
- Lens vignetting is applied when the Smart Preview's EXIF (`LensModel`, `FocalLength`, `FNumber`) matches an Adobe RAW lens profile (`.lcp`) installed with Lightroom under `Adobe/CameraRaw/LensProfiles`. This matches Lightroom with lens profile corrections on, which is the setup of the Canon benchmark. The result is reported as `lens_vignetting: applied | no_lens_metadata | lens_profile_not_found`. Distortion is not applied. The lens name is never returned.
- Parity: the author benchmarked the rendering against Lightroom's own Smart Preview exports (Delta E 2.51 on 80 held-out Canon R6 II photos, 0.94–4.11 on 7 cameras). It has **not** been re-measured on this catalog. `source_only_neutral_parity_verified` stays `false`, and no sample becomes training-ready.

## Quality and product gates

The supplied author reports Reset-parity against Lightroom, including an 80-photo held-out sample, but we **have not independently repeated that benchmark** on this catalog.

Before training on this decoded data, we still must:
1. Verify real JPEG XL DNG decoding on the user's machine, report bounded diagnostic status.
2. Verify camera / lens / Adobe Color rendering and Lightroom Import-vs-Reset parity using controlled exports.
3. Verify Lightroom UUID-to-DNG identity (including virtual copies) and approved finality of the Develop recipe.
4. Hold out entire future events for validation and block data leakage.
5. Validate native JPEG XL codec crash isolation and Windows/macOS packaging before commercial distribution.

All operations in this Part are READ ONLY on Lightroom source paths. The automatic local cache contains *only the decoder's source code*, never photographer images.
