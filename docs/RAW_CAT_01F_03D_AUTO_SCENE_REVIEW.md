# RAW-CAT-01F.03D — AI proposes semantic scene, human verifies

2026-10-11 | PRE-G0 ENGINEERING | code committed, Windows tests and actual inference pending | D-015/ D-016.

03C local Windows result: 16/16 tests passed, 12/12 private source-RAW previews generated, no errors. No human label/event/final Lightroom edit confirmed. User is non-photographer and requests model-first labels for review.

## What it does (and DOES NOT)
An optional LOCAL zero-shot image/text classifier CLIP ViT-B/32 (public pretrained `openai/clip-vit-base-patch32`, roughly 605 MB model weights) takes ONLY original camera RAW neutral-approximate previews. Prompts distinguish getting ready, ceremony, dancing, portrait, posed group, reception, decorations/details, other. This is an experiment. It does NOT use Lightroom developed JPEGs, previews, Develop controls or targets as vision inputs, upload any photo, infer identity or classify demographic attributes.

Separately, technical RAW brightness is a deterministic luminance proxy: it can suggest dark/bright but NOT indoors/outdoors or a wedding scene. CLIP softmax scores are RELATIVE ONLY within this set of prompts; they are NOT calibrated confidence/probability. Abstain to UNKNOWN if top score below 0.31 or top-second difference below 0.12, or top class OTHER. These thresholds are exploratory, not validated; every card requires human agreement/correction/unsure, default UNREVIEWED. Event, raw-to-LR identity and final-edit confirmations default UNKNOWN and require photographer validation.

Only user-opt-in --allow-model-download contacts Hugging Face to download model weights. Without this switch it loads previously cached model files only. No photos leave the computer via this command. Internet access/space needed first time; model loading on CPU may take minutes. Model download provenance and license must be reviewed for commercial shipping; none shipped in GitHub.

## Windows commands from repo root

    git pull --ff-only origin main
    cd backend
    .\.venv\Scripts\python.exe -m pytest -q tests/test_raw_auto_scene_review.py tests/test_raw_local_review.py tests/test_raw_context_catalog_pilot.py

Check local package:

    .\.venv\Scripts\python.exe -c "import transformers, torch; print(transformers.__version__, torch.__version__)"

If the import fails, install pinned transformers requirement:

    .\.venv\Scripts\python.exe -m pip install -r requirements-phase11-vision.txt

After explicit permission to analyze RAW locally AND explicit willingness to download the model weights once:

    .\.venv\Scripts\python.exe -m app.photographer.raw_auto_scene_review --private-manifest "$env:USERPROFILE\Desktop\RAW_CAT_01F_03B_PRIVATE.json" --raw-dir "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך" --out-dir "$env:USERPROFILE\Desktop\RAW_CAT_01F_03D_AUTO_REVIEW" --report "$env:USERPROFILE\Desktop\RAW_CAT_01F_03D_AGGREGATE.json" --consent-acknowledged --allow-model-download

The new output directory MUST be empty/new. View `RAW_CAT_01F_03D_AUTO_REVIEW\AI_REVIEW_PRIVATE.html` locally in browser. Model predicts candidates, but every card defaults UNKNOWN human scene, UNREVIEWED human decision, UNKNOWN Lightroom link and finality. To accept a reliable suggestion, select the agree decision; the UI copies a non-UNKNOWN scene. For other/unsure set human scene manually or leave UNKNOWN. Export private CSV before closing tab. No autosave.

UPLOAD ONLY `RAW_CAT_01F_03D_AGGREGATE.json` (counts, no names). KEEP LOCAL the PRIVATE 03B manifest, 03D preview images, HTML and annotation CSV. Never upload to public GitHub. Human labels remain experimental until photographer event/finality confirmation, licensing and G0/G1; no model training or quality claim.