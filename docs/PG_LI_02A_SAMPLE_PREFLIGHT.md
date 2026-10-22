# PG-LI-02A — local-only verified-source research preflight

**Status:** Draft implementation for Windows validation; not a completed DATA-01 or G1.  
**Base:** user learning stages 1→2, `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` §5.3 / DATA-01, existing RAW-CAT parser.  
**Rule:** no production training, finality approval or Lightroom editing in this Part.

## Why

The catalog-only intake correctly counted parsed Develop records but returned **zero training-ready** because no original identity, final approved edit, event boundaries or Import/Reset initial state were verified.

This Part adds a local "אימות מדגם תמונות" panel after catalog intake. It returns a bounded, representative **sample of up to 16 records**, rotated across candidate Lightroom folder/day groups. This is designed to expose evidence gaps before processing thousands.

## Implemented for review

- Reuses the existing private `raw_catalog_intake.inspect_catalog(..., include_private=True)` only on a temporary consistent SQLite snapshot.
- Returns per-photo metadata to the authenticated local engine UI **transiently**: catalog local/global image IDs, candidate group, file stem/extension, capture day, supported parsed Develop field names and warnings (Virtual Copy, parse failure, opaque local edits).
- Optional user-selected RAW event folder is scanned *read-only* with bounded traversal (100k file cap, no symlink traversal), matching **filename + extension case-insensitively**. Duplicate filenames are reported as ambiguous, never resolved arbitrarily.
- For a **single filename candidate only**, records a SHA-256 of observed RAW bytes (up to 400 MiB per file), with race detection if size/mtime change while hashing.
- **Every record still says** source_identity_verified=false, photographer_finality_verified=false, import_reset_baseline_verified=false, event_identity_verified=false, training_eligible=false. Even a unique name plus SHA is only a *candidate*, not a verified Lightroom↔source mapping.
- No private per-image manifests are persisted in the regular profile DB, added to git, or uploaded.

## Explicitly out of scope

- The current `Smart Previews.lrdata` directory is discovered but still **not decoded**. Local pilot can run catalog-only even without RAW.
- No true original RAW identity proof (requires Lightroom Bridge original reference/readback + consistent hash/metadata), no event-level photographer validation, no final edit approval, no Import-vs-Reset baseline and no split assignment.
- Hashes are not compared to a Lightroom-proven hash; do not treat this as identity verification. A file with the same filename can still be the wrong RAW.
- No synchronous sample result should be cached across changed Lightroom catalogs; report is transient and must be refreshed manually. A future persisted evidence manifest requires its own versioned artifact/evidence policy.

## Windows review commands

From the user's existing worktree `PROGRAPHER-LEARNING-TEST`:

```powershell
git pull --ff-only
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests\test_learning_preflight.py tests\test_learning_intake.py tests\test_photographer_setup.py tests\test_raw_catalog_intake.py
cd ..\frontend
npm.cmd run lint
npm.cmd run build
# then launch Tauri with separated PROGRAPHER_DATA_DIR as in existing workflow
```

In ProGrapher:
1. Select an **existing**, already-audited catalog.
2. Select "הפעל בדיקת מדגם 16 תמונות" with no RAW to verify representative group/finality questions. No new training-ready count.
3. Optionally choose a **copy** of source RAW event folder, rerun to inspect unique/ambiguous/no-filename candidates and SHA-256 evidence.
4. Verify original files unchanged, no private filenames in the public intake aggregate, and temporary catalog snapshot deleted.

## Next: PG-LI-02B

Implement an explicit controlled Lightroom Bridge research readback for **10–16 photographer-approved images**: exact source identity including catalog photo ID/version and source hash, *final delivered edit* confirmation, ambiguity resolution of Virtual Copies and event identity, controlled Import-versus-Reset baseline. Only after corroborated evidence should a versioned private per-image training manifest be allowed, and train/validation/test splits must remain whole-event.
