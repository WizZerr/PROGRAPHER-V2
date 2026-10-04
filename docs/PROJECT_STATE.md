# ProGrapher V2 — Project State

Updated: 2026-10-04

## Single source of truth

**Active execution plan:** `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` — **ProGrapher V2 Master Workflow v3.0**.

Historical plans and superseded planning notes live under `docs/archive/` and are not execution instructions.

## Repository / PR

- Repository: `WizZerr/PROGRAPHER-V2`
- Working branch: `cursor/testing-ready-77c3`
- PR: #1 — Draft, state `open`
- Base: `ui-v2-overhaul`
- PR head observed immediately before PG-00.03 adoption: `953b0f1f05da7197c14141ff42f6f288d1c61420`
- `main` is not the active development baseline until PG-00.04 is completed.

## Current execution position

- Active phase: **Phase 00 — קיבוע נקודת ההתחלה והחלפת התוכנית**
- Latest completed Parts: **PG-00.03 — V**, **PG-00.06 — V**
- Open merge gate Part: **PG-00.02 — ◐**
- **PG-00.04 is blocked** until PG-00.02 is closed.
- Primary development Part: **PG-00.05 — ACTIVE / ◐**.
- Execution/governance Part: **PG-00.06 — V**.

## PG-00.02 — residual QA status

Windows PR1 QA has broad manual evidence recorded in `docs/PR1_TEST_CHECKLIST_HE.md`, including RAW/JPEG Gallery and Darkroom behavior, cache behavior, RAW previews, XMP safety, event deletion, startup and focused performance checks.

The product owner chose on 2026-10-04 to stop additional manual QA for now and batch remaining bugs later. This is **not** recorded as PASS.

Outstanding evidence includes:

- External-drive open/disconnect/reconnect flow.
- Relink to the correct folder, refusal of an unrelated folder, and Gallery/Darkroom recovery after relink.
- Final-head CI after the latest QA/test/documentation commits.
- JPEG edge-case checks added to automated coverage must be confirmed by CI.

## Release 1 architecture locked by Workflow v3.0

- Event editing, AI inference, rendering, review, export and local jobs run on the photographer's computer.
- Cloud handles identity, entitlement, profile/settings backup or sync, selected learning data and managed training.
- Do not automatically upload all photographer events.
- JPEG is the primary independent Release 1 editing path.
- RAW keeps the safe assisted RAW/XMP path; no claim of independent Adobe-equivalent RAW development.
- Windows x64 and macOS Apple Silicon are required Release 1 targets.
- Legacy V1 CLIP + ExtraTrees brain remains retired; new brain candidates are preserved for comparison.

## PG-00.05 progress

- Added automated backup-copy restore coverage for Event + RAW profile + saved Review; source RAW must remain byte-identical.
- Added `docs/PG_00_05_FIXTURE_RESTORE_MATRIX.md`.
- **BUG-PG00-001:** JPEG profile stores an absolute manifest path; portable restore is not yet proven.
- Real historical backup restore and real-camera licensed fixture evidence are still missing.

## Current blockers / gates

- **G0 is not signed.**
- PG-00.02 remains open.
- PG-00.04 merge/tag cannot start yet.
- Apple Silicon real-machine evidence is still required later by the workflow.
- Representative photographer material is still required before real learning/quality claims.

## Next executable work

1. **PG-00.05 — ACTIVE** — prepare/verify fixtures and restore checks where data is available.
2. Return to **PG-00.02** later for the remaining hardware/manual QA and final CI.
3. Only then execute **PG-00.04** merge/tag/baseline.
4. After G0, continue with Phase 01 according to Workflow v3.0.

Do not start Auth/Cloud implementation or a new production Brain merely because documentation migration is complete.

## Execution board

- `docs/EXECUTION_BOARD.md` — active lane, blockers, risk map and bug/research/product classification.

## Phase 01 preparation

- **PG-01.01 — ◐ DRAFT PREPARED:** `docs/RELEASE_1_PRODUCT_CONTRACT.md`.
- Draft locks the intended Release 1 shape for review: independent JPEG, assisted RAW, Windows x64 + Apple Silicon, local editing with narrow cloud control plane.
- It cannot become V before G0 and explicit product-owner ratification.
- Primary active development Part remains PG-00.05 while G0 is open.
