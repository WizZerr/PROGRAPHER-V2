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
- Latest completed Part: **PG-00.03 — V**
- Open merge gate Part: **PG-00.02 — ◐**
- **PG-00.04 is blocked** until PG-00.02 is closed.
- Work that does not depend on merge may continue with **PG-00.05 / PG-00.06**.

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

## Current blockers / gates

- **G0 is not signed.**
- PG-00.02 remains open.
- PG-00.04 merge/tag cannot start yet.
- Apple Silicon real-machine evidence is still required later by the workflow.
- Representative photographer material is still required before real learning/quality claims.

## Next executable work

1. **PG-00.05** — prepare/verify fixtures and restore checks where data is available.
2. **PG-00.06** — create the execution board, blockers and risk map.
3. Return to **PG-00.02** later for the remaining hardware/manual QA and final CI.
4. Only then execute **PG-00.04** merge/tag/baseline.

Do not start Auth/Cloud implementation or a new production Brain merely because documentation migration is complete.
