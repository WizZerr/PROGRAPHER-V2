# RAW-CAT-01F.03C — Local photographer RAW visual review

Date 2026-10-11 | D-015 + D-016 | PRE-G0 ENGINEERING | Code and synthetic tests committed; Windows tests and actual visual review pending.

## Evidence
03B passed 12/12 synthetic Windows tests and decoded 12/12 RAW originals with zero failures. Original sample is lexically spread across four PROVISIONAL Lightroom catalog groups (3 per group). The sample contains brightness/color variation but NO proven independent events or scene labels; 2 candidate rows contain opaque mask/local-edit structures. Matching source to catalog still relies on unique filename+extension only. Lightroom finality, photographer event identity and approved training data remain 0.

## Purpose
Create a PRIVATE, local offline review contact sheet with approximately display-encoded original camera RAW thumbnails for human scene, event and finality/identity labeling. The source is the PRIVATE 03B pilot manifest; run only after the photographer permitted local RAW visual research. Source RAW decode uses existing hash-verifying pipeline; each decoded source SHA is checked against the SHA recorded by the 03B pilot. Files that fail path/hash/decode checks get no preview. Outputs are HTML + derived private JPG thumbnails + a public-safe aggregate JSON. The browser review HTML has inline CSS/JavaScript, no network calls and saves annotations with a local CSV download button. No Lightroom developed/edited JPEG or LR preview input, no image uploads, no model training.

## Windows commands
Open PowerShell in repository root, then:

    git pull --ff-only origin main
    cd backend
    .\.venv\Scripts\python.exe -m pytest -q tests/test_raw_local_review.py tests/test_raw_context_catalog_pilot.py tests/test_raw_disk_catalog_audit.py tests/test_raw_visual_context_probe.py

Then, ONLY with confirmed photographer permission for LOCAL RAW image review:

    .\.venv\Scripts\python.exe -m app.photographer.raw_local_review --private-manifest "$env:USERPROFILE\Desktop\RAW_CAT_01F_03B_PRIVATE.json" --raw-dir "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך" --out-dir "$env:USERPROFILE\Desktop\RAW_CAT_01F_03C_REVIEW" --report "$env:USERPROFILE\Desktop\RAW_CAT_01F_03C_AGGREGATE.json" --consent-acknowledged

Open the generated `RAW_CAT_01F_03C_REVIEW\REVIEW_PRIVATE.html` in Windows browser (works offline). Photographer should identify the real type of scene and real event, and confirm inside Lightroom Classic the RAW/catalog identity and whether the Develop adjustments represent the final approved edit. Select YES only after actual independent check; UNKNOWN is the default. Click **ייצוא סימוני הצלם ל־CSV פרטי** to download annotations. No auto-save: export CSV BEFORE closing page, and store downloaded CSV locally.

Upload ONLY `RAW_CAT_01F_03C_AGGREGATE.json` if aggregate analysis is needed. NEVER upload PRIVATE 03B manifest, REVIEW_PRIVATE.html, preview JPEGs or private annotation CSV to GitHub, or publicly. Original RAWs are not modified. The neutral-approximate thumbnails are not Adobe-equivalent and MUST NOT be used as renderer parity targets.

## Gates
Even when human reviewer records YES, do not automatically set training_eligible=true. Reviewer confirmation must include authorization, independent identity/final edited state, verified whole-event membership, appropriate local edit coverage and G0/G1 contracts; no learned production Brain yet.