# PG-LI-00/01 — Catalog-first profile onboarding

**Branch:** `feature/pg-learning-onboarding-00-02`  
**Baseline:** `main` at `712b552`  
**Basis:** user-authored "ProGrapher — תהליך הלמידה מקצה לקצה" (2026-10-16), Stages 0–8.  
**Status:** Draft implementation; Windows and full-repo regression tests required before merge. No personal Brain has been trained.

## Contract: exactly what Stage 0–2 mean

| Stage from user document | This Part | Completion / next gate |
| --- | --- | --- |
| 0: Profile input | **Implemented for review** | Name, photography type, color/B&W, consent, one or more catalogs, optional Smart Previews or RAW fallback; versioning/multi-user permissions still pending |
| 1: Lightroom catalog reading | **Aggregate intake implemented for review** | SQLite consistent temporary backup; existing `inspect_catalog` summarizes RAW count, syntactically parsed Develop records and candidate groups. **Does not verify final edits, event labels, true source identity or Smart Preview pixels.** |
| 2: Starting point / Reset vs Import | **Blocked, not implemented** | Need safe 16-image Lightroom Bridge sampling per photographer, verify all applicable fields/initial preset/profile/camera conditions and store evidence |
| 3: Neutral rendering | **Not in scope** | Document describes rawpy + Adobe profiles and preferred Smart Previews; v4.0 GitHub plan keeps Lightroom Classic as definitive rendering engine and independent Adobe-equivalent JPEG renderer deferred. Research a source-only neutral feature preview with measured parity; don't substitute edited images. |
| 4: Features | **Not in scope** | numpy, YuNet, SigLIP 2, metadata, WB and camera/LR context must be consistently computed at training and inference |
| 5: Personalized learning | **Not in scope** | Per-slider Gradient Boosting candidates, fixed-value channels, persisted feature schema, train-only fitting and versioned artifacts |
| 6: Validation | **Not in scope** | Whole-event holdout, photographer-specific presets, no data leakage and gate-controlled fallback |
| 7: New-event edit | **Not in scope** | Recipe → supported Lightroom Bridge/sidecar → readback/verification/review/export. No direct SQLite writes. |
| 8: Learning loop | **Not in scope** | Photographer-approved final corrections, frozen evaluations, model promotion/rollback |

## Implementation

- `backend/app/learning_intake/service.py`: local SQLite tables, profile creation, consent guard, multiple catalog attachment; atomic SQLite consistent snapshot using source `mode=ro` and destination in private app directory; existing `raw_catalog_intake.inspect_catalog` on the snapshot. Temporary snapshot is deleted after audit.
- `backend/app/api/routes/learning_intake.py`: authenticated local engine endpoints under `/api/learning-intake` using existing middleware. No training APIs.
- `frontend/src/features/learning-intake`: Hebrew RTL wizard with source selectors and truthful aggregate report.
- `frontend/src/features/profile/ProfileScreen.tsx` RAW CTA enters catalog-first onboarding; previous JPEG flow preserved.
- `backend/tests/test_learning_intake.py`: consent, catalog-only read, source integrity, persisted multiple catalogs, rejection, Smart Preview path labels.

**Never claim:** "learned profile", "train-ready examples" or "Smart Preview decoded". An existing Smart Preview folder is recorded as `smart_previews_unverified`; RAW selection is `raw_fallback_unverified`; catalog-only is `catalog_only_limited`.

**No private uploads:** catalog paths and local aggregate summaries remain in local SQLite. No catalog, RAW, Smart Preview DNG, per-photo manifest or captured screenshot belongs in this repository, PR, CI artifact or logs.

## Security / technical limits

- Catalog probe is read-only; SQLite online backup reads committed source state into a private temporary `snapshot.lrcat`. Backing up a catalog of several gigabytes needs comparable free disk space and may take time.
- Intake reuses research parser with documented Adobe private-schema limitations; incompatibility must fail visibly. This is not yet an unattended/background durable job.
- File-system and Lightroom sidecar races, live Lightroom edit changes, source-to-catalog identity matching and source duplication have NOT been verified. For research, use a backed-up Lightroom catalog or closed/exported copy.
- No real DNG Smart Preview decode/parity test, original RAW signature validation, camera-scene AI, Reset versus Import baseline or approved model input.
- No changes to Lightroom SDK plugin, model registry or existing `main` product behavior except launching the new onboarding screen from the RAW profile CTA after merge.

## Review checklist

1. `cd backend`; with the project virtual environment and dependencies, run `python -m pytest -q tests/test_learning_intake.py tests/test_photographer_setup.py tests/test_raw_catalog_intake.py` (last path only if present; otherwise adjust).
2. `cd frontend && npm ci && npm run lint && npm run build`.
3. In a Windows Tauri session open "יצירת פרופיל למידה", create one profile and choose multiple **backed-up** valid LRCAT files. Reopen app to verify persistence.
4. Choose one `Smart Previews.lrdata` directory and/or RAW fallback. Verify status says **unverified**, no training starts and count remains zero.
5. Check malformed schemas/invalid path: show helpful error and no stored fake-success record. Confirm original catalog SHA remains unchanged and temporary copy gets deleted.
6. Validate that selecting RAW in existing "הפרופיל שלי" now navigates to the new flow; JPEG remains unchanged.
7. Record local test/build results against an exact commit; do NOT describe CI as green if GitHub quota prevents its execution.

## Next Part: PG-LI-02 — verified source/finality/baseline

On a COPY and with photographer authorization, verify catalog records against original RAW or correctly parsed Smart Previews using stable image identities; confirm actual delivered/final Develop state; validate Import versus Reset via a safe Lightroom Bridge sample (as specified in user document) before generating training-ready examples. Store evidence in a versioned private manifest; never infer initial state or finality from mere catalog presence.

This document describes the user's **learning flow**. The repository `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` remains the product/architecture execution source of truth. The old PG-BS-01 branch/PR uses RAW+XMP median baseline and should be superseded for this workflow, not merged.

## PG-LI-01 UX amendment — 2026-10-22

The photographer now **chooses the containing Lightroom catalog folder** (or a .lrcat directly) and ProGrapher discovers immediate catalog files without recursion.

- Exactly one .lrcat → select it; more than one → require explicit user selection, never choose "newest" arbitrarily.
- Adjacent sibling with exact case-insensitive Lightroom naming `<catalog stem> Smart Previews.lrdata` → link as `smart_previews_unverified`. Ignore `Previews.lrdata`, other catalogs' Smart Previews, symlinks and unrelated caches.
- Missing/renamed/moved Smart Previews → clearly state not found and show optional advanced manual selection/RAW fallback; never imply complete image coverage.
- Save API independently performs the same discovery, so clients cannot silently omit known adjacent Smart Previews.
- This is metadata/path **discovery only**, not the promised Smart Preview decode, index linkage, image count or training-ready validation. Those remain blocked until PG-LI-02/03.
- Tests added for exact sibling, multi-catalog selection, unrelated cache isolation, folder errors, symlinks and manual override.

Local check from project worktree:
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q tests\test_learning_intake.py tests\test_photographer_setup.py
cd ..\frontend
npm.cmd run lint
npm.cmd run build
npm.cmd run tauri dev
```

The previous 9/9 test run predates this amendment. **Run tests again on Windows; these updated results have not been verified yet.**

## PG-LI-01 UX fix — saved catalog and profile deletion

- The original "בדוק ושמור קטלוג" required a **new** selected catalog path even when the profile had an existing audited catalog. When exactly one saved catalog exists, the primary button now explicitly says "בדוק מחדש את הקטלוג השמור" and re-audits the original path, retaining saved Smart Preview and optional RAW metadata. Each saved catalog also has its own "בדוק מחדש" action to handle profiles with multiple catalogs.
- This is a **re-audit**, not advancement to Stage 2. Stage 2 Reset/Import remains unimplemented and disabled for training.
- Profiles can be deleted from the profile list or current profile, behind a clear second confirmation screen. `DELETE /api/learning-intake/profiles/{profile_id}` removes only `learning_intake_catalogs` metadata then the `learning_intake_profiles` row in the same local SQLite transaction. It never touches disk media, Lightroom's catalog or other profiles. API returns a JSON success response so the existing desktop `apiRequest()` handles it.
- Tests verify deleted profile metadata removed, other profiles intact, catalog/RAW/Smart Preview files byte-for-byte retained, unknown IDs return 404, and delete requires engine authentication.
- Pre-merge Windows checks: Python learning intake and setup tests, `npm.cmd run lint`, `npm.cmd run build`, interactive smoke with pre-existing saved catalog, multiple catalog selections, cancel delete and confirmed delete. Deletion should be tested only against a disposable **test profile**, not real photographer records. The original 13-pass + 1-skip run predates this change; do not claim these tests have passed yet.

## Windows API DELETE regression correction — 2026-10-22

The initial delete API regression test used `new_store(tmp_path,...)` which persisted the fixture profile in `profiles.sqlite3`, while real API endpoints instantiate `LearningProfileStore()` at `PROGRAPHER_DATA_DIR/prographer.sqlite3`. The user correctly observed `15 passed, 1 skipped, 1 failed`, where DELETE returned 404 because the API was looking in a different SQLite file.

Corrected test sets a dedicated `PROGRAPHER_DATA_DIR`, instantiates the same default `LearningProfileStore()` as the API, explicitly GETs the profile before deletion, then checks 401 without authentication, 200/JSON on delete, 404 for repeated deletion, and retention of a second profile.

No production deletion implementation or user Lightroom/RAW files were changed for this fix. The corrected test still requires a fresh Windows run; expected after passing: 16 passed, 1 skipped.
