# PG-LI-02B.01b — External Smart Preview JPEG XL decoder integration (research)

**Source:** Author-supplied `smart_preview_decoder_v1.zip` (2026-10-23).  
**Status:** OPTIONAL local adapter; full decoded-pixel tests and Lightroom parity still require the user's Windows environment.  
**Do not redistribute the third-party module.** The supplied ZIP includes no LICENSE file; secure written permission / a clear license from its author before shipping or committing its code in a commercial product.

## Audit summary

The author's decoder is NOT just generic rawpy: it supports TIFF/DNG 1.7 LinearRaw with Compression=52546 JPEG XL, applies embedded MapPolynomial/other stage-2 opcodes, crops/orientation, and optionally renders a Lightroom-Reset-like sRGB image using an embedded camera profile, Adobe Color look and a measured tone calibration.

Reported research results (not independently reproduced here):
- Canon R6 II 80 held-out wedding photos: ΔE 2.51 at **48 px** against Lightroom exported from Smart Preview; luminance difference −0.017 stops.
- Six additional camera types were tested with 2–4 photos each; Fuji X-T50 ΔE 4.11.
- Author admits empirical CALIBRATION_STOPS=−0.144 (unexplained), limited cross-camera/lens validation and no evidence the preview representation always equals photographer-approved pre-edit Import state.

The ZIP does NOT include real Smart Preview DNGs or Lightroom reference JPEGs. Synthetic tests exist and require `imagecodecs` with JPEGXL codec. The author source itself is not copied into this GitHub repository.

## Integration design

- Our existing `dng_diagnostics.inspect_dng_compression` reads bounded TIFF metadata (not full pixels).
- If a sampled DNG contains Compression=52546, route to an **optional** `smart_preview_decoder.decode_smart_preview`. Do **NOT** pass this DNG back into LibRaw, which already failed on the user's 4 pilot files.
- Use **only layer 1** `sp.linear` for the capability probe, capped to a 1024-px long edge and checked for shape/finiteness/crop/range. A successful state means JPEG XL DNG pixels decoded — not visual correctness or approved input for AI.
- If the module or codec isn't installed, show explicit local environment states instead of a generic corrupt-DNG error.
- If unhandled DNG opcodes remain, report `jpegxl_dng_unhandled_opcodes`; never certify image parity.
- The source remains profile-scoped, private and read-only. No native codec is bundled in distribution.

### Local developer installation on WINDOWS test worktree

Start PowerShell. Keep existing production ProGrapher closed, and use only the **separate** `PROGRAPHER-LEARNING-TEST` worktree and venv.

```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER-LEARNING-TEST"
git pull --ff-only
cd backend

# Requires access to the ORIGINAL ZIP on your PC:
$zip = "C:\PATH\TO\smart_preview_decoder_v1.zip"

# Research dependencies inside this test venv only; inspect wheel/version before production pinning.
.\.venv\Scripts\python.exe -m pip install tifffile imagecodecs
.\.venv\Scripts\python.exe tools\install_smart_preview_decoder_local.py --zip "$zip"

.\.venv\Scripts\python.exe -c "import imagecodecs, smart_preview_decoder; print('JPEGXL available:', imagecodecs.JPEGXL.available); print('module:',smart_preview_decoder.__version__)"
.\.venv\Scripts\python.exe -m pytest -q tests\test_smart_preview_probe.py tests\test_learning_preflight.py tests\test_learning_intake.py
cd ..\frontend
npm.cmd run lint
npm.cmd run build
```

For upstream synthetic unit tests, extract the original ZIP into a separate private temp directory and run its `tests/test_decoder.py` with the same venv (do not commit the samples). Real-photo Lightroom parity requires separate, consented research exports and an approved color reference pipeline.

### Runtime / app

Launch Tauri with the same local test DATA_DIR + CACHE_DIR. The new JPEG XL module is imported directly from this test venv — no PYTHONPATH changes, no modified .lrcat, no RAW selection.

Click `בדוק מדגם + Smart Previews אוטומטית`. Expected after a successful codec/install on compatible source files:
- 3,184 TIFF signature candidates (from prior research pilot)
- JPEG XL (Compression 52546) samples
- up to four `jpegxl_dng_decoded_unverified` rows if the external decoder supports the actual compression.
- `training_ready_samples=0`, photo identity and Lightroom Reset parity still FALSE.

If the module/codec is missing, the UI explains this. If there are ignored opcodes, it must not count as success.

## Gates still blocked

1. Confirm real JPEG XL DNG pixels on ≥4 consented research files.
2. Compare decoded pixels or rendered output against Lightroom **Reset / Import** with exact profile, WB, lens/tonal defaults, not just a 48-px color metric.
3. Verify Lightroom SDK UUID-to-DNG identity including Virtual Copies, finality, event grouping and original metadata.
4. Compare broad held-out photos by camera, venue, lighting and photographer before approving source-only learning.
5. Review legal usage/redistribution rights and pin Windows/macOS wheels; run decoding in an isolated worker to contain native JPEG XL crashes before commercial release.
6. Do NOT promote this as model-ready data or copy calibration curve into the Brain until all gates pass.
