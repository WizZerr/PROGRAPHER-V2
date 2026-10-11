# RAW-CAT-01F.03A — Private per-photo RAW→Lightroom candidate pilot

Date 2026-10-11. Scope D-015 / D-016. 01F.03A original pilot 10/10 focused synthetic tests and 12/12 RAW decodes succeeded on Windows. G0 unsigned; no training-ready samples.

## Evidence and hypothesis
01F.01A user Windows audit: 5208 filename-only matches, 0 ambiguous; 2 disk-only, 1815 catalog-only. 01F.02A user Windows experiment: 6/6 original CR3 decoded, 0 failed. Aggregated ranges do not connect any individual original to its Lightroom edit.

## Scope
Select at most 12 unique name+extension candidate files, round-robin over PROVISIONAL catalog groups. Hash and decode original camera RAW through existing fixed camera-WB linear-sRGB backend; private record stores input camera and source-image features in one namespace and UNAPPROVED Lightroom Develop targets in a separate namespace. Also include private source path/hash/record id and review flags: UNKNOWN scene, no photographer-confirmed event, finality or training eligibility.

Never use Lightroom Develop, edited JPEG, LR previews or XMP as visual-model input. Emit an AGGREGATE-only report plus a strictly PRIVATE per-photo JSON file. All personal paths/filenames/edit values stay private. Decode is original-RAW read-only. Name matching alone does not verify photo identity. This is not a production dataset, style predictor, scene detector, colorimetric Lightroom parity test or approved Brain training.

## Windows commands
Open PowerShell in the project root, update main, then from backend:

    .\.venv\Scripts\python.exe -m pytest -q tests/test_raw_context_catalog_pilot.py tests/test_raw_disk_catalog_audit.py tests/test_raw_visual_context_probe.py

After and only after explicit permission for LOCAL photographer RAW research, run from backend as a single command:

    .\.venv\Scripts\python.exe -m app.photographer.raw_context_catalog_pilot --raw-dir "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך" --catalog "C:\Users\Matann\Downloads\ProGrapher_Training_Catalog\ProGrapher_Training_Catalog.lrcat" --report "$env:USERPROFILE\Desktop\RAW_CAT_01F_03A_AGGREGATE.json" --private-manifest "$env:USERPROFILE\Desktop\RAW_CAT_01F_03A_PRIVATE.json" --max-files 12 --consent-acknowledged

Upload only RAW_CAT_01F_03A_AGGREGATE.json. Never upload RAW_CAT_01F_03A_PRIVATE.json to public GitHub/chat. Private records include photo names, paths, hashes and photographer editing choices.

## Quality and gates
Required next human work: confirm RAW identity independent of name; photograph final editing state, photographer permission, real whole-event membership, original scene annotation, local-mask support policy. Only then preregister held-out event comparisons under signed G0/G1. Current training-ready count is zero.

## 01F.03B selection fix (2026-10-11)

Actual PRIVATE sample review showed the old 01F.03A sampler selected three adjacent or near-adjacent filenames in EACH provisional catalog group, potentially overrepresenting a capture burst. 01F.03B keeps max 20, round-robin group quotas and all existing no-leakage rules, but samples START / MIDDLE / END evenly across each group's lexical range. It is a better coverage proxy, not proof of visual/lighting diversity or independent events. New synthetic regression tests cover lexical span and scarce groups. Rerun and use NEW output names ending 03B to preserve 03A evidence. 01F.03B pending Windows verification.
