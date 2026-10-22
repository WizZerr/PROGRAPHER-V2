# PG-LI-02B.01 — Smart Previews: actual DNG pilot + SDK link research

**Status:** DRAFT; no Windows desktop build or actual Lightroom SDK smoke has yet been run for this new Part.  
**Source of truth:** user learning workflow stages 1–4; `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` §§4–5, DATA-01.  
**Model gate:** G1 **BLOCKED**, training-ready = **0**.

## Why two separate checks

Adobe Lightroom Classic Smart Previews are reduced-resolution lossy DNGs, stored in `<Catalog> Smart Previews.lrdata`. The fact that this directory exists is not proof it contains usable data, and the DNG filename need not equal the Lightroom photo UUID.

The Lightroom SDK offers `photo:getRawMetadata('smartPreviewInfo').smartPreviewPath` (SDK 5+). This creates a separate research route to connect a *selected* Lightroom photo UUID to a DNG path without guessing. It does **not** automatically prove source RAW identity, approved final edit, neutral Import/Reset baseline or model input safety.

## Capability A: DNG content probe (integrated, single click)

Inside the saved Lightroom catalog's **אימות מדגם תמונות** panel, the photographer selects `בדוק תוכן Smart Previews` — no RAW folder selection.

- Local backend `smart_preview_probe.py` walks the saved Smart Previews folder read-only.
- Max 100,000 file entries. Skips symlinks and Windows junctions; bounded read errors fail visibly.
- Checks TIFF/DNG container signatures and DNG sizes (no full content parse on all images).
- Uses pinned `rawpy==0.27.1` / LibRaw to **attempt** real pixel decode on at most four evenly distributed candidates. Has size/dimension caps. Computes a nonpersisted, sparse luma diagnostic — **not** a photographer style feature.
- If Lightroom's lossy-DNG codec is unsupported/corrupt, report `unsupported_or_corrupt_dng` and do not fall back to a final edited JPEG.
- Counts only; does not save decoded pixels, copy DNGs or include paths/filenames in the content-probe report.

Expected example statuses include `decoded_unverified`, `unsupported_or_corrupt_dng`, `decoder_unavailable`. `source_only_neutral_parity_verified` and `photo_to_dng_link_verified` remain FALSE.

## Capability B: Lightroom SDK UUID→DNG link research (manual pilot)

For research **only**, when ready to inspect image identity:

1. In Lightroom Classic, open **the same approved research catalog copy** that ProGrapher has ingested. Do not use a customer's live catalog.
2. Load the development plugin at `integrations/lightroom_classic/lb01/ProGrapherBridge.lrdevplugin` using File → Plug-in Manager → Add, or reload it if already installed. This research plugin also contains the existing *write-capable* LB-01 test, so **do not run that other menu command** on a valuable catalog.
3. Select **1–16 photos** in Library.
4. Run Library → Plug-in Extras → `ProGrapher Smart Preview Link Readback (Research ONLY)`.
5. Save the generated `*.json` **outside** Lightroom catalog, RAW or preview directories. Treat the JSON as private: it contains paths and Lightroom image UUIDs. Do not share/upload it.
6. In ProGrapher expand `אימות שיוך תמונות באמצעות Lightroom SDK · מחקר מתקדם`; choose this local JSON.
7. ProGrapher verifies that the JSON names the currently linked catalog, UUID exists uniquely among catalog RAW records, and SDK Smart Preview path actually resolves to a readable DNG under this profile's Smart Preview directory. It rejects foreign paths, duplicate UUIDs, invalid files.
8. Results are transient; no per-photo manifest saved, no training, Lightroom writes or edits.

The JSON is NOT signed, the bridge is still manually invoked and source RAW hashes were not compared. The UI reports `נתיבי DNG עם UUID תואם בקטלוג` rather than a falsely 'certified training pair'.

## Test gates

On the user's Windows worktree:
```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER-LEARNING-TEST"
git pull --ff-only
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests\test_smart_preview_probe.py tests\test_learning_preflight.py tests\test_learning_intake.py tests\test_photographer_setup.py
cd ..\frontend
npm.cmd run lint
npm.cmd run build
```

Then launch Tauri with the **separate ProGrapher-Learning-Test local data/cache environment** (as used before). On an authorized research catalog: run content probe, inspect decode count; **do not equate passing container signatures to successful decoding**. If no Smart Previews exist, give a clear no-source state.

This Part must be *held* in Draft if LibRaw crashes on real Smart Preview DNG or if the Lightroom SDK evidence export cannot be executed: isolate the failure, do not claim completion.

## Next Part: PG-LI-02B.02

Move SDK link readback to the future authenticated local Lightroom Bridge job protocol, then compare true pre-edit/Import state and edited targets (without consuming edited previews as source-only training data). Prove linkage + Lightroom parity on selected representative images including Virtual Copies. Only photographer-validated finality and whole-event split can advance the dataset gate.
