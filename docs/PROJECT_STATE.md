# ProGrapher V2 — Project State

## Source of Truth
`MASTER_PLAN_SOURCE_OF_TRUTH.md` — ProGrapher V2 Master Implementation Plan, 20 Sep 2026.

## Current execution position
- Current phase: Phase 0 — Freeze + Safety
- Status: IN PROGRESS
- Next execution step after Phase 0: Phase 4A (per the new master plan), then Phases 1–3, then Phase 4B.

## Frozen baseline
- Frontend: V18.0.5 TRUTH MODE
- Backend: V2.1.3 TRUTH MODE
- Frontend ZIP SHA-256: `458f51720398c3818ca350619bae50492825f03191a03c082f7b21c3e607e496`
- Backend ZIP SHA-256: `4cec4764e7677e38cb144de2720958b4499b560a490c35f08d1b41dfc505aba0`
- Master plan SHA-256: `a71f68b177a51897c5e8a75152a8fc74949799b32145c960bf9f695cc9e8303e`

## Verified in current audit environment
- Backend Python source compiles with `python -m compileall`: PASS.
- `verify_fresh_install.py`: correctly reports that the runtime DB is absent from the supplied ZIP; full runtime flow is therefore NOT TESTED from the archive alone.
- Frontend has no lockfile or installed dependencies in the ZIP; clean `npm build` remains NOT TESTED in this audit environment.
- `exifread` is imported in backend code but is not present in the supplied requirements files.
- Windows-specific operational assumptions remain in current code/UI (`.bat` instructions and `C:\...` placeholders).

## Required target matrix
- macOS Apple Silicon arm64: REQUIRED — NOT TESTED
- Windows x64: REQUIRED — NOT TESTED
- macOS Intel x86_64: FEASIBILITY/SUPPORT DECISION REQUIRED — NOT TESTED

## Phase 0 blockers / external evidence still needed
- Actual working database/profile backup and restore evidence.
- Clean runtime on a real Windows test machine.
- Clean runtime on a real Apple Silicon Mac.
- 30–50 licensed technical fixture files and known references where available.
- Full current flow evidence: install/build → runtime → import → event → export; personal prediction only if trained profile + matching inputs are available.

## Do not claim
- Phase 0 is not DONE.
- Mac support has not yet been proven.
- Model quality has not yet been measured by this Phase 0 audit.


## Active workstream — PR #1 QA / Merge Gate — 2026-10-02
- Branch: `cursor/testing-ready-77c3`.
- Base: `ui-v2-overhaul`.
- PR #1 is still Draft and remains the active integration branch.
- Production PR1 scope: safe RAW/XMP testing loop + separate JPEG Original/Edited Dataset path.
- Automated Windows gate has passed on the product/research head before the latest documentation-only QA update; the final documentation head must also be green before merge.
- Manual evidence already exists for source-safe XMP export, photographer-owned XMP overwrite refusal, ProGrapher-owned XMP update, draft/restart persistence, RAW preview fixes, event catalog-only deletion, training-results UI, and JPEG dataset creation.
- Remaining merge work is a focused final Windows manual smoke/regression pass, especially startup, full-screen navigation, RAW↔JPEG persistence, external-drive behavior, and practical large-event performance.

### JPEG research readiness while photographer material is pending
- `backend/training_lab/` now contains isolated J0/J1 research tools only; production behavior and product claims are unchanged.
- Synthetic J0/J1 and the real-folder smoke protocol were exercised through whole-event Train/Validation/locked-Test separation.
- A frozen synthetic smoke candidate generalized to held-out synthetic events, but this is engineering plumbing evidence only.
- No claim is made about real photographer style, editing quality, time savings, or production JPEG intelligence until representative photographer events are available.
