# ProGrapher V2 — Project State

Updated: 2026-10-04

## Single source of truth

**Active execution plan:** `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` — **ProGrapher V2 Master Workflow v3.0**.

Historical plans and superseded planning notes live under `docs/archive/` and are not execution instructions.

## Repository / mainline

- Repository: `WizZerr/PROGRAPHER-V2`
- **Single development Source of Truth: `main`.**
- Verified pre-PG-04.02 main HEAD: `86b67d2e65a8cd2876a29eb10f85b88703b34f17`.
- Repository branch inventory at verification: **`main` only**.
- PR #1 is closed and is not the active development path.
- New work is committed directly to `main` unless a strong engineering reason requires a temporary branch.

## Current execution position

- Active phase: **Phase 04 — JPEG engine, preview truth and technical export**.
- **PG-03.02–PG-03.09 — V**: pre-photographer JPEG/data-safety package complete.
- **PG-06.01 — V**: photographer data-request package ready.
- **PG-06.02 — BLOCKED** until authorized photographer material arrives.
- **PG-04.01 — V**: shared JPEG EditRecipe/renderer contract verified in run `37176350329`.
- **PG-04.02 — V**: product preview/full-resolution rendering, revision cache and stale-revision protection verified by manual delta checks; parent backend regression/compile remains green in run `37176350329`.
- **PG-04.03 — V**: encoded JPEG quality/size/ICC/orientation/metadata/GPS contract verified by manual delta checks with reopen validation.
- **PG-04.04 — V**: safe separate-folder atomic export verified for collisions, disk/write failures, cleanup and source hash preservation.
- **PG-04.05 — V**: versioned renderer/export goldens verified, including large preview-vs-export deviation budgets.
- Residual PR1 manual QA remains paused by product-owner decision and is not restarted here.
- Do not start Auth/Supabase/Cloud or a new production Brain.

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

1. **PG-04.06 — ACTIVE / ◐** — versioned JPEG control mapping and real-render preview API implemented; wire the Darkroom JPEG panel and verify every control changes actual pixels.
2. Prove every supported control changes actual rendered pixels and unsupported RAW-only concepts are not exposed as JPEG equivalents.
3. Then continue to the remaining Phase-04 RAW/XMP boundary work.
4. **PG-06.02** remains blocked until real authorized photographer material arrives.

Do not start Auth/Cloud implementation or a new production Brain.

## Execution board

- `docs/EXECUTION_BOARD.md` — active lane, blockers, risk map and bug/research/product classification.

## Phase 01 preparation

- **PG-01.01 — ◐ DRAFT PREPARED:** `docs/RELEASE_1_PRODUCT_CONTRACT.md`.
- Draft locks the intended Release 1 shape for review: independent JPEG, assisted RAW, Windows x64 + Apple Silicon, local editing with narrow cloud control plane.
- It cannot become V before G0 and explicit product-owner ratification.
- This prepared Phase-01 contract is not the active development lane; current work follows Phase 04 as recorded above.

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

## Pre-photographer data safety gate complete

- **PG-03.09 — V:** consolidated fail-closed regression gate now covers PG-03.02–PG-03.08 plus locked-Test contamination.
- J1 performs immutable-data/provenance/leakage preflight before feature decoding or fitting.
- Candidate preparation with valid Train/Validation targets does not decode locked Test pixels.
- Corrupted snapshot, source-group leakage, unresolved near-duplicate and target tampering all block before feature decode.
- Evidence: `docs/PG_03_09_DATA_SAFETY_GATE_REPORT.md`; Windows backend + training-tool compile passed in run `37174673037`.
- **PG-03.02–PG-03.09 pre-photographer engineering package is complete.**
- Real-photographer G1 evidence remains pending until representative material arrives.

## Shared JPEG renderer and photographer request package

- **PG-04.01 — V:** JPEG EditRecipe/renderer semantics moved from J0 into `backend/app/rendering/jpeg_renderer.py`.
- J0, J1 synthetic, J1 real, locked Test and artifact provenance now share the same recipe/renderer contract.
- Renderer regression and backend training-tool compile passed in PR1 validation run `37176350329`.
- Evidence: `docs/PG_04_01_JPEG_RENDERER_CONTRACT.md` and `docs/PG_04_01_JPEG_RENDERER_REPORT.md`.
- **PG-06.01 — V:** photographer request package is ready before material arrives.
- Request artifacts: `docs/PHOTOGRAPHER_DATA_REQUEST_HE.md`, `docs/PHOTOGRAPHER_SUBMISSION_CHECKLIST_HE.md`, and `docs/templates/photographer_submission_manifest.template.json`.
- Evidence: `docs/PG_06_01_PHOTOGRAPHER_REQUEST_REPORT.md`.
- **PG-06.02 remains blocked until real authorized photographer material arrives.**
- **PG-04.02 — V:** product preview/full-resolution rendering is verified with revision/cache and stale-approval protection.
- **PG-04.03 — V:** encoded JPEG output is verified from original source + shared recipe with explicit metadata/color policy.
- **PG-04.04 — V:** safe filesystem export is verified; failed/partial writes are not returned as valid and source bytes remain protected.
- **PG-04.05 — V:** frozen semantic and encoded JPEG goldens now protect renderer/preview/export behavior.
- Next executable JPEG-engine Part without photographer material: **PG-04.06**.
