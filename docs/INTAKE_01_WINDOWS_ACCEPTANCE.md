# INTAKE-01 — Windows acceptance contract

Status: OPEN. NOT WINDOWS VERIFIED. See D-022 and Issue #9.

## Required closure

- [ ] S1.01: Active historical intake uses .lrcat + matching Smart Previews.lrdata; NEVER requires historical RAW.
- [ ] S1.02: Hebrew RTL UI selects both, supports replacement/relink, state persists across full restart.
- [ ] S1.03: Safe SQLite snapshot read; schema/integrity checks; detect WAL/SHM/lock; no source mutation.
- [ ] S1.04: Genuine Adobe Smart Previews structure and readability validated on real test materials; ordinary Previews.lrdata must be rejected.
- [ ] S1.05: Catalog photo IDs ↔ Smart Preview image-level mapping verified, with every record accepted/absent/unsupported/quarantined and no silent loss. NOT IMPLEMENTED in this PR.
- [ ] S1.06: No private data uploaded, reliable local persistence, crash/restart recovery and source hash evidence.
- [ ] S1.07: Automated positive, negative, migration, relink and UI tests all pass with no skips of required cases.
- [ ] S1.08: Real Windows Tauri + Adobe Lightroom Classic E2E on representative large catalog; all source hashes unchanged; logs anonymized.
- [ ] S1.09: Master, Board, State, D-015/D-016/D-022, product UI and customer intake documents aligned.

## Implementation in candidate branch

- backend/app/photographer/smart_preview_probe.py — filename and folder inventory ONLY. A positive probe is NOT proven Smart Preview content, photo mapping or source neutrality.
- backend/app/photographer/lightroom.py — readonly SQLite, quick_check, active sidecar refusal.
- backend/app/photographer/setup_store.py — SQLite smart_previews_path column and stale binding invalidation.
- backend/app/services/photographer_setup_service.py and app/api/routes/photographer.py — local-only API for selection, no training side effects.
- frontend/src/features/training/TrainingScreen.tsx and RawTrainingView.tsx — historical Catalog + Smart Previews form, no original RAW.
- frontend/src/features/profile/ProfileScreen.tsx — status means source selection, never training readiness.
- .gitignore and backend/tools/check_private_assets.py — defense in depth, not a guarantee for pretracked or forced assets.

## Windows test sequence — NOT RUN

1. Clean disposable worktree based on this draft PR. Keep research worktrees intact. Close Lightroom, use only permissioned COPY of catalog and genuine Smart Previews.
2. From worktree root: python backend/tools/check_private_assets.py
3. With backend venv and PYTHONPATH=<worktree>/backend, run pytest -q -rs for tests/test_smart_preview_intake.py, tests/test_catalog_probe_safety.py, tests/test_private_asset_guard.py and existing photographer setup tests.
4. From frontend: npm ci; npx tsc --noEmit; npm run build. Test real Tauri desktop UI on Windows.
5. Test valid pair, wrong pair, normal Previews.lrdata, missing/empty folder, corrupt catalog, active Lightroom WAL/lock, symlink, permission errors, cancel, relink, replacement, full restart, crash/retry.
6. Record exact commit SHA, Windows/Lightroom versions, PASS/FAIL/SKIP, evidence of unchanged hashes, measured time/memory and anonymized coverage. No photographer assets in GitHub.
7. Complete version-specific image association research on real Smart Preview media. This is BLOCKED and not inferred from matching directory names.

Stage 1 can be signed WINDOWS VERIFIED only once all checked criteria pass. Stage 2 independently proves source-neutral visual inputs and Develop correctness. macOS final certification follows successful Windows core.