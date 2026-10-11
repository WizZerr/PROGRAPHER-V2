# ProGrapher V2 — Project State

Updated: 2026-10-06

## Single source of truth

**Active execution plan:** `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` — **ProGrapher V2 Master Workflow v3.0**.

Historical plans and superseded planning notes live under `docs/archive/` and are not execution instructions.

## Repository / mainline

- Repository: `WizZerr/PROGRAPHER-V2`
- **Single development Source of Truth: `main`.**
- Pre-PG-01.07 baseline verified on `main`: `1cfce09a3da06725088b981b9dfcc6f042fa8f67`.
- Repository branch inventory at verification: **`main` only**.
- PR #1 is closed and is not the active development path.
- New work is committed directly to `main` unless a strong engineering reason requires a temporary branch.

## RAW-first scope decision — D-015 / 2026-10-11

Product owner changed the active Release 1 learning scope to **original RAW + exported Lightroom Classic .lrcat**, with source-safe predicted RAW recipe/XMP and Lightroom as initial final renderer. **JPEG learning/rendering development is frozen** (existing evidence and code preserved). Final JPEG is NOT a training prerequisite. All pre-existing JPEG-first notes and Phase-01 draft promises below are superseded only to the extent they conflict with D-015. The existing gates/statuses are unchanged: G0 unsigned, PG-00.05 open, PG-06.02 blocked on RAW originals; production Brain, Auth, Cloud remain blocked.

Active isolated engineering prep: **RAW-CAT-01D → RAW-CAT-01E.01 → RAW-CAT-01E.02** completed structural research on the real exported catalogue (7,023 CR3 Develop rows; no parse exclusions; 30 Windows focused tests at commit `b5edc6c`). Tone curves were syntactically decoded (NOT Adobe validated); nonzero Color Grading adjustments appear in 30 candidate rows after separating 7,023 default-like Blending configuration values. **RAW-CAT-01E.03A** independent Lightroom manual validation sampling is implemented, Windows/real-catalog testing PENDING at this commit; future **01E.03B** independent Lightroom/XMP parity remains pending Adobe references. All photo-level manifests/plans remain LOCAL PRIVATE; 0 matched original RAW pairs, 0 training-ready samples, G0 unsigned. Refer to [D-015](D_015_RAW_FIRST_SCOPE.md).

## Current execution position

- **Phase 01 preparation package is complete at draft/engineering-prepared level (PG-01.01–PG-01.07).** Ratification remains blocked by G0. The next executable non-manual engineering lane is **PG-00.05 — portability/restore hardening**.
- **PG-03.02–PG-03.09 — V**: pre-photographer JPEG/data-safety package complete.
- **PG-06.01 — V**: photographer data-request package ready.
- **PG-06.02 — BLOCKED** until authorized photographer material arrives.
- **PG-04.01 — V**: shared JPEG EditRecipe/renderer contract verified in run `37176350329`.
- **PG-04.02 — V**: product preview/full-resolution rendering, revision cache and stale-revision protection verified by manual delta checks; parent backend regression/compile remains green in run `37176350329`.
- **PG-04.03 — V**: encoded JPEG quality/size/ICC/orientation/metadata/GPS contract verified by manual delta checks with reopen validation.
- **PG-04.04 — V**: safe separate-folder atomic export verified for collisions, disk/write failures, cleanup and source hash preservation.
- **PG-04.05 — V**: versioned renderer/export goldens verified, including large preview-vs-export deviation budgets.
- **PG-04.06 — V**: normalized JPEG controls are wired to the real renderer; every supported control changes pixels and RAW-only Kelvin/Tint semantics are not claimed for JPEG.
- **PG-04.07 — V**: RAW/XMP round-trip/source protection and truthful Lightroom-owned preview boundary verified; prior good ProGrapher sidecars are rolled back on mid-export source change.
- **Phase 04 — COMPLETE**.
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
- **BUG-PG00-001 / B-007 — CLOSED / VERIFIED:** portable JPEG manifest reference + legacy absolute-path rebinding passed the focused Windows restore suite (3/3 PASS) on `1fa7cca24dd01ee3fb32baf272402f1d2b2fa3db`.
- Real historical backup restore and real-camera licensed fixture evidence are still missing.

## Current blockers / gates

- **G0 is not signed.**
- PG-00.02 remains open.
- PG-00.04 merge/tag cannot start yet.
- Apple Silicon real-machine evidence is still required later by the workflow.
- Representative photographer material is still required before real learning/quality claims.

## Next executable work

1. **Phase 04 — COMPLETE** — PG-04.01 through PG-04.07 are V within their exact technical scope.
2. **PG-01.06 — PREP COMPLETE / ◐** — Evaluation Protocol 1.0 draft is frozen; V waits for G0 + ratification.
3. **PG-01.07 — PREP COMPLETE / ◐** — Release 1 hardware/OS matrix and Intel Mac decision are prepared; V waits for G0 + measurements/ratification.
4. **PG-01.05 — ◐ CONTRACT PREPARED / G0 BLOCKED** — lifecycle/consent contract remains ready for later ratification.
5. **Next executable non-manual lane: PG-00.05** — portability/restore hardening, including BUG-PG00-001; PG-00.02 manual QA remains intentionally paused.
6. **Phase 05 remains BLOCKED** until formal Phase-01 dependencies can be ratified after G0.
7. **PG-06.02** remains blocked until authorized photographer material arrives.

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
- **PG-04.06 — V:** JPEG Darkroom controls now drive the real renderer with stale-response protection and explicit normalized semantics.
- **PG-04.07 — V:** RAW/XMP safety and truth boundary closed.
- Phase 04 is complete. Phase 05 is formally blocked on Phase-01 entry dependencies; the active pre-G0 preparation lane is **PG-01.05**.


## PG-01.04 portable profile package preparation

- **PG-01.04 — ◐ ENGINEERING-VERIFIED / G0 BLOCKED.**
- Added a local portable `.pgprofile` package contract and implementation with immutable UUID identity, weights/normalizer roles, version contracts, metrics, hashes and compatibility gates; targeted local verification is green.
- Import is fail-closed and atomic; incompatible/tampered packages do not create a final ProfileVersion directory.
- This does not start Supabase/Auth/Cloud.
- Phase 05 must not be started as complete-entry work until PG-01.02 and PG-01.04 are ratified after G0.


## PG-01.05 data ownership/lifecycle preparation

- **PG-01.05 — ◐ CONTRACT PREPARED / G0 BLOCKED.**
- Added `docs/PG_01_05_DATA_LIFECYCLE_CONTRACT.md`.
- Every Release-1 data class now has an explicit source of truth and restore expectation.
- Source RAW/JPEG remains local by default; Event/PhotoAsset is not automatically mirrored to cloud.
- Profile sync is explicitly **not** photo backup.
- Consent is purpose-specific: local processing, profile sync, selected managed personal training, and broader/product-improvement learning are separate scopes.
- Broader/global-learning ingestion stays disabled until a later explicit policy.
- Quota behavior cannot silently delete source media or active profile data.
- Event/Profile/Device/Account deletion semantics are separate.
- No Supabase/Auth/Cloud implementation was started.


## PG-01.07 hardware / OS support preparation

- **PG-01.07 — ◐ CANDIDATE MATRIX PREPARED / G0 + MEASUREMENT PENDING.**
- `docs/TARGET_SYSTEM_MATRIX.md` now defines Release 1 support classes instead
  of the old Phase-0 three-row placeholder.
- Windows x64 and macOS Apple Silicon remain mandatory Release 1 targets.
- Intel Mac is evaluation-only under D-014 and does not block Release 1.
- Candidate floor: 16 GB RAM + SSD-class storage; 32 GB recommended. These are
  not final commercial requirements until measured.
- GPU/accelerator requirements intentionally remain model-dependent until a real
  Brain candidate exists.
- Current Windows session evidence is recorded: 118 backend tests, 27 focused
  JPEG tests, frontend lint/TS/build, Rust/Tauri and real desktop JPEG/RAW flow
  passed on the tested commits. Later UI-only corrections were manually verified;
  this is not claimed as one final-head certification run.
- Apple Silicon remains UNVERIFIED and is still required before relevant
  platform gates can close.


## PG-01.06 evaluation protocol preparation

- **PG-01.06 — ◐ PROTOCOL FROZEN AS DRAFT / G0 RATIFICATION PENDING.**
- `docs/EVALUATION_15A_PROTOCOL.md` is now Protocol 1.0 for Release 1.
- JPEG G2 representation, JPEG G3 source-only prediction, RAW-assisted safety,
  G4 local value and G6 beta value are evaluated separately.
- G3 primary metric is frozen as acceptance without manual correction.
- Frozen draft thresholds: G2 >=90% close-enough + >=80% representation
  coverage; G3 >=10 percentage-point acceptance improvement vs strong baseline
  with no serious-failure increase; G4 >=30% median active-time saving on at
  least two new Events; G6 >=70% median beta-Event saving and >=50% per
  Photographer, with 80%+ aspirational.
- Every primary rate now has an explicit denominator and exclusion reporting.
- Locked Test is confirmatory and cannot be repeatedly used for candidate
  selection.
- RAW time/quality evidence cannot be mixed into JPEG claims.
- D-015 records the draft threshold/primary-metric decision.
- Phase-01 preparation is now complete across PG-01.01–PG-01.07 at draft/
  engineering-prepared level; ratification remains blocked by G0.


## Frontend verification — 2026-10-06

Current UI baseline `18fb9438bc273dd9809aa23ce864c23384a3f91f` passed locally on Windows:

- `npm.cmd run lint` — PASS,
- `npx.cmd tsc --noEmit` — PASS,
- `npm.cmd run build` — PASS,
- Next.js 16.3.5 production build completed successfully.

The frontend cleanup package is therefore engineering-verified on Windows at
that baseline. Further UI work should be driven by a concrete UX defect rather
than general polishing.

## PG-00.05 — BUG-PG00-001 implementation

- JPEG profile persistence now stores the managed manifest as a relative
  `testing_datasets/<profile_id>/manifest.json` reference.
- Runtime/API resolution binds it to the active `PROGRAPHER_DATA_DIR`.
- Legacy absolute managed-manifest paths are rebound by profile identity so a
  restored backup does not silently keep reading the old app-data copy.
- Two focused restore regressions plus the existing RAW restore regression passed locally on Windows: **3 passed / 0 failed in 1.11s**. B-007 is closed.


## Account-ready frontend identity — 2026-10-07

- Added a frontend `AccountIdentity` seam with `firstName`, `displayName`
  and optional `profileName`.
- Dashboard greeting now derives from that identity contract:
  `שלום, {firstName}`.
- The profile screen derives its owner label from `profileName` when present,
  otherwise from `firstName`.
- Identity is local-only for now and editable from profile settings.
- This is forward-compatibility work only; Auth/Supabase/Cloud implementation
  remains gated and is **not started**.
- Profile UX is reorganized around the two expected initial JPEG learning
  paths, with RAW secondary and technical settings hidden behind the profile
  settings dialog.


## Profile learning UX refinement — 2026-10-07

- Dashboard greeting grammar corrected to `שלום {firstName},`.
- The Profile screen is now intended to show two equal top-level capabilities:
  `למידה לפי JPEG` and `למידה לפי RAW`.
- Each capability exposes exactly two route statuses on the Profile screen.
- Entering learning uses progressive disclosure:
  media type → learning method → required material → result.
- JPEG routes: before/after pairs or JPEG source + Lightroom Catalog.
- RAW routes: RAW + Lightroom/XMP edits or RAW source + Lightroom Catalog.
- Pair counts/catalog record counts are shown only when backed by real data.
- No fake learning percentage is displayed before a real trained Brain exposes
  meaningful progress/metrics.
- Catalog route setup is preparation only until its separate training Brain is
  implemented and evaluated.


## RAW/JPEG learning navigation correction — 2026-10-07

- Fixed the learning handoff so Profile → JPEG and Profile → RAW enter distinct
  flows directly instead of falling back to a shared "choose file type" page.
- The media choice is now made only once, on the Profile screen.
- JPEG remains two separate learning routes:
  Original/Edited pairs and JPEG + Lightroom Catalog.
- RAW is one RAW + Lightroom learning capability.
- XMP and LRCAT are treated as two sources for Lightroom edit metadata inside
  that RAW capability, not as two RAW learning Brains.
- Profile status therefore reports JPEG as 0/2..2/2 and RAW as 0/1..1/1.
