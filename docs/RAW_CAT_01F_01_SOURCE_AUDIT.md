# RAW-CAT-01F.01A — Read-only RAW source/catalog audit

Date: 2026-10-11. D-015 RAW-first, D-016 Photographer Fidelity First. G0 is not signed.

## What the new command proves

- Enumerates camera RAW extensions under one selected original-RAW folder, recursing read-only. Ignores AppleDouble "._" files, non-RAW and symlinks.
- Reuses the existing strict read-only .lrcat copied-catalog parser. Groups each candidate by unique case-insensitive filename stem PLUS raw extension, refusing ambiguous repeated names.
- Prints only aggregate counts; optional JSON report contains counts only, no filenames, user paths, Develop settings, hashes, photo pixels or capture dates.
- Does **NOT** decode RAW, verify SHA256/content identity, confirm event labels/photographer consent/finality, match edited JPEGs, classify lighting/scenes or train a Brain.
- Rejects report paths inside original RAW folder or overwriting the Lightroom .lrcat.
- Explicitly marked research, not G0/G1/G2 evidence of readiness.

## Run on user's Windows PC

Open PowerShell in local ProGrapher V2 repo root and run:

~~~powershell
git pull --ff-only origin main
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_raw_disk_catalog_audit.py
Test-Path "C:\Users\Matann\Downloads\ProGrapher_Training_Catalog\ProGrapher_Training_Catalog.lrcat"
Test-Path "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך"
.\.venv\Scripts\python.exe -m app.photographer.raw_disk_catalog_audit `
  --catalog "C:\Users\Matann\Downloads\ProGrapher_Training_Catalog\ProGrapher_Training_Catalog.lrcat" `
  --raw-dir "C:\Users\Matann\Desktop\New folder\ProGrapher_ALL_PHOTOS\לא ערוך" `
  --report "C:\Users\Matann\Desktop\RAW_CAT_01F_01A_AGGREGATE.json"
~~~

Use the actual catalog path if different. Run only on a finalized exported catalog COPY with Lightroom closed; the existing parser rejects nonempty WAL.

## Next

Check aggregate name-match coverage and ambiguous keys, then select a bounded **permissioned** original-RAW cohort for source-only color/luminance features and verified camera metadata. Preserve separately verified identities and event-split/photographer approvals. Never use Develop/JPEG preview data as model feature input. No Brain training until required gates.
