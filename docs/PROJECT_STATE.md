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

## PG-01.02 preparation

- **PG-01.02 — ◐ CONTRACT PREPARED:** `docs/PG_01_02_DATA_IDENTITY_CONTRACT.md`.
- Initial cloud provider selected: **Supabase Auth + PostgreSQL + private Storage**.
- Local operational source of truth remains **SQLite** for Event/PhotoAsset/Run/RecipeRevision/Review/Export.
- Current migration gaps are explicit: path-derived Event identity, singleton photographer setup, non-durable jobs/exports/reviews and BUG-PG00-001.
- No Supabase production resources are provisioned by this documentation Part; actual cloud implementation remains gated later in the workflow.

## PG-01.03 preparation

- **PG-01.03 — ◐ CONTRACT PREPARED:** `docs/PG_01_03_PIPELINE_CONTRACT.md`.
- One versioned training/inference spine is defined.
- JPEG and RAW remain separate; inference cannot read edited targets.
- Existing Brain V2 contracts are retained as foundations but require media-neutral/generalized evolution.
- Ratification/implementation remains gated by G0.

## Pre-photographer JPEG integrity

- **PG-03.02 — V:** visual geometry/orientation contract now blocks crop/rotation/mirror/wrong-copy and permits verified resize.
- **PG-03.03 — V:** JPEG ICC/EXIF is normalized into the declared sRGB working contract; unsafe unknown color cases fail explicitly.
- **PG-03.04 — V:** full-SHA dataset snapshot is frozen at Intake and revalidated before J0/J1/locked Test.
- Evidence: `docs/PG_03_02_04_JPEG_INTEGRITY_REPORT.md`; Windows backend regression passed in Actions run `37171832248`.
- These are engineering/data-integrity results, not photographer-quality claims.
- Next pre-photographer data Part: **PG-03.05**.

## Approved unchanged-final targets

- **PG-03.05 — V:** byte-identical JPEG finals are learning targets only with explicit approval provenance.
- Unverified identical copies remain excluded.
- Approved identity targets pass into J0 as real No-Edit targets.
- Evidence: `docs/PG_03_05_IDENTITY_TARGETS_REPORT.md`, backend regression run `37172073037`.
- Next pre-photographer data Part: **PG-03.06**.

## Source-group leakage protection

- **PG-03.06 — V:** exact/near-duplicate source derivatives are grouped before Train/Validation/Test assignment.
- Source-group connected Events cannot cross splits.
- Unverified near-duplicates require explicit human review.
- New Events do not silently move locked Test Events.
- Evidence: `docs/PG_03_06_SOURCE_GROUPS_REPORT.md`, backend regression run `37172785201`.
- Next pre-photographer Part: **PG-03.07 — Coverage Report**.

## Dataset coverage reporting

- **PG-03.07 — V:** Intake produces a truthful coverage report that separates files, matched pairs, usable pairs and exclusions.
- Camera/lighting/edit-scope coverage is visible per Event and globally.
- Hard/excluded groups remain explicit.
- Evidence: `docs/PG_03_07_COVERAGE_REPORT.md`, backend regression run `37173058568`.
- Next pre-photographer Part: **PG-03.08 — Candidate/target provenance identity**.

## Immutable experiment provenance

- **PG-03.08 — V:** J0 targets and J1 candidates now have deterministic, version-bound artifact identities.
- Exact Git commit, dependency lock, color/feature/recipe/renderer contracts and material config are part of provenance.
- Candidate files are sealed by SHA-256 manifest and verified before locked Test.
- Existing immutable artifacts are not overwritten; non-promoted/rejected candidates remain preserved.
- Evidence: `docs/PG_03_08_ARTIFACT_PROVENANCE_REPORT.md`, backend + compile success in run `37174158871`.
- Next pre-photographer Part: **PG-03.09 — consolidated corruption/leakage/Test-guard regression**.
