# RAW-CAT-01F.02A — Source-only RGB feature probe

2026-10-11 — D-015 / D-016. **Pre-G0 experiment, NOT production AI.** Current state: code + synthetic tests committed; real Windows sample test pending.

## Goal

Start answering how original photographs vary BEFORE editing. Reuse the existing hash-verifying rawpy/LibRaw decoder (fixed linear-sRGB, camera white balance, no automatic brighten, 16-bit intermediate), downsample deterministically to <=250,000 pixels, compute per-frame scalar features in-memory only, and publish ONLY aggregate min/median/max over at most 12 source CR3 files. This code does not consume Lightroom/edited JPEGs, perform aesthetic judgement, infer indoor/outdoor, or reconstruct Adobe pixels.

Source hash invariance is checked by the existing RAW decode backend. RGB highlight fractions are decoded image proxies, not actual sensor clipping. Camera white balance influences channel means; they are NOT a validated objective light-source classification.

Selection is evenly spaced across lexically sorted filenames — NOT a validated event or visual scene sample. Underlying image-level values, source file names, hashes and per-image paths are never serialized.

## Prerequisites and command

Require explicit permission from the photographer to analyze original camera RAWs locally. If not confirmed, DO NOT RUN this pixel-decoding step; you can still run 01F.01A's metadata/name readiness audit.

After git pull from ProGrapher repo, in backend PowerShell:

    .\.venv\Scripts\python.exe -m pytest -q tests/test_raw_disk_catalog_audit.py tests/test_raw_visual_context_probe.py

    .\.venv\Scripts\python.exe -m app.photographer.raw_visual_context_probe `
      --raw-dir "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך" `
      --report "C:\Users\Matann\Desktop\RAW_CAT_01F_02A_VISUAL_AGGREGATE.json" `
      --max-files 6 `
      --consent-acknowledged

The last switch acknowledges REAL photographer permission; do not use it without confirmation. Run with the python venv from backend. For very large CR3s processing can be slow/memory-intensive. Only 6 frames by default, never the 5,210 as a batch yet.

## Next review

Check all 6 decoded; inspect aggregate brightness/contrast/color proxies; validate on synthetic fixtures, then obtain photographer-confirmed scene/event labels and permissioned final editing targets before testing contextual predictor. G0 UNSIGNED, G1/G2/G3 unratified, 0 training-ready pairs.
