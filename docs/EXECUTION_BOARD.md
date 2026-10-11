# ProGrapher V2 — Execution Board

Updated: 2026-10-11  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` — Master Workflow v3.1 with D-015 and D-016 amendments

This board implements **PG-00.06**. It is an execution view, not a second master plan.

## Operating rule

At any moment each development lane has at most one active Part. A bug, research experiment and product capability are tracked separately and never silently promoted into each other.

Status vocabulary:

- **ACTIVE** — current work.
- **READY** — executable when the active Part finishes or capacity is available.
- **PAUSED** — intentionally stopped; evidence remains incomplete.
- **BLOCKED** — dependency or hardware/data gate prevents completion.
- **DONE** — exact Part completion criteria have evidence.

## Scope override / product owner decision — D-015 (2026-10-11)

**RAW-first / Photographer Fidelity**: original RAW + Lightroom exported catalog is the active learning dataset (D-015); the goal is to preserve the photographer's own style using scene context from SOURCE ONLY (D-016). JPEG edited targets are not required; JPEG feature work paused, historical work kept. G0, PG-00.05 and PG-06.02 statuses do NOT change. RAW-CAT-01D is a pre-G0 **research/engineering preparation lane**, not permission to train a production Brain. Private photographer inputs must never be committed. See [D-015](D_015_RAW_FIRST_SCOPE.md).

## Current lanes

| Lane | Part | Status | Exact next output |
|---|---|---|---|
| RAW catalog research | **RAW-CAT-01F.03A** | ACTIVE / Windows pilot pending | 01F.01A: real 5,208 name-only pairs out of 5,210 disk RAW, 0 ambiguous; 01F.02A: 6/6 original CR3 decoded successfully; 01F.03A code committed to build max-12 PRIVATE original-only features + separate catalog targets, training remains blocked and G0 unsigned |
| JPEG development | **FROZEN by D-015** | PAUSED | Preserve existing code/tests and fix only safety regressions |
| Primary development | **PG-00.05** | READY / ◐ | Resume non-manual portability/restore hardening when continuing development; BUG-PG00-001 is the concrete code blocker |
| Photographer intake | **PG-06.02** | BLOCKED | Authorized photographer material |
| Residual PR1 QA | **PG-00.02** | PAUSED | Only resume when product owner returns to the remaining hardware/manual QA |
| Cloud/Auth | **PG-12+** | BLOCKED / NOT STARTED | Do not start before workflow gate permits |
| Brain | **PG-07/08+** | BLOCKED / NOT STARTED | No new production Brain before required data/gates |

## Blockers

| ID | Blocks | Blocker | Resolution evidence |
|---|---|---|---|
| B-001 | PG-00.02 / PG-00.04 / G0 | No external drive available for disconnect/reconnect QA | Real external drive test or later explicitly approved equivalent hardware QA |
| B-002 | PG-00.02 / PG-00.04 / G0 | Final-head CI not yet recorded after the latest PR1 QA/test/doc commits | Green PR1 validation on the final merge candidate SHA |
| B-003 | Platform gates later in workflow | No real Apple Silicon run evidence | App/engine smoke on supported Apple Silicon Mac |
| B-004 | PG-00.05 full completion | No verified copy of the user's historical DB/profile backup has been restored in this workflow | Restore on a copy; profile/events/reviews readable; source files unchanged |
| B-005 | G1/G2/G3 quality work | Representative photographer dataset is not yet available | Authorized events split by whole event/source group with provenance |
| B-006 | Commercial claims | No real photographer quality/time-savings measurement | Gate-specific evaluation on unseen photographer events |
| B-007 | PG-00.05 | **CLOSED 2026-10-06** — portable manifest reference + legacy rebinding verified on Windows | 3/3 focused restore regressions PASS on `1fa7cca24dd01ee3fb32baf272402f1d2b2fa3db`; restored JPEG manifest resolves under restored data dir, not old copy |
| B-008 | PG-00.05 | No small real-camera fixture set with explicit product-safe provenance/license is recorded | Add licensed/provenanced camera fixtures without committing restricted photographer material |

## Risk map

| Risk | Severity | Current control | Next mitigation Part |
|---|---|---|---|
| Source RAW/JPEG mutation or unsafe overwrite | Critical | PR1 source-safety/XMP evidence; export separation | PG-00.05 restore fixtures, later PG-04/05 hardening |
| Wrong JPEG pair because of duplicate names/path ambiguity | High | pairing ambiguity + visual geometry/wrong-copy guards; PG-03.02 V | PG-03.05–03.09 / G1 |
| Source changes after intake but before training | High | fingerprints exist; full revalidation gap documented in v3 | PG-03 |
| ICC/color mismatch makes J0/J1 targets invalid | High | ICC/EXIF→sRGB contract + explicit rejection; PG-03.03 V | PG-03.09 regression + real-data G1 |
| Crop/geometry mismatch passes weak checks | High | visual ORB/RANSAC + consensus/edge checks; PG-03.02 V | PG-03.09 + real-data review |
| Research result accidentally presented as product AI | High | J0/J1 isolated; PR1 labels JPEG as viewing/dataset path | PG-06–08 gates |
| External-drive disappearance/relink regression | High | backend tests exist; manual hardware evidence missing | PG-00.02 later, PG-05 hardening |
| Crash loses local scan/job progress | High | current scan job is in-memory; risk documented | PG-05 after Phase-05 entry dependencies are ratified |
| Mac-specific packaging/runtime failure | High | target is mandatory; not yet tested | PG-02 |
| 2,000-photo event memory/latency regression | Medium/High | progressive gallery/cache evidence exists | PG-05/09/11 |
| Cloud scope creep before local value is proven | High | D-008 + G4 requirement | PG-12–15 only after G4 |
| Premature Brain replacement | High | V1 retired; candidate preservation policy | PG-07/08/18 |
| Stale/conflicting execution documents | Medium | PG-00.03 single-source migration complete | Keep README/PROJECT_STATE synchronized |

## Work classification

Every new item must use exactly one primary class:

### BUG
A behavior contradicts the current accepted product contract or regresses previously working behavior.

Required record:
- reproduction,
- expected vs actual,
- severity,
- affected Part/Gate,
- fix commit,
- regression evidence.

### RESEARCH
An experiment tests an uncertain hypothesis and does not create a product claim by itself.

Required record:
- hypothesis,
- frozen input/split,
- baseline,
- metric,
- stop/promote rule,
- artifact/candidate identity.

### PRODUCT CAPABILITY
A user-visible behavior intended for Release 1.

Required record:
- owner Part,
- entry dependency,
- acceptance criteria,
- failure/recovery behavior,
- test evidence,
- documentation impact.

### GATE / EVIDENCE
A proof required to cross G0–G6. Evidence cannot be replaced by implementation status.

## Bug batching policy

The product owner chose on 2026-10-04 to stop additional manual PR1 QA and batch remaining bugs later.

Therefore:

1. New non-blocking issues discovered during ongoing work go into a bug batch with severity and reproduction.
2. Do not silently fix unrelated bugs inside a Part.
3. Critical data-loss/security/corruption bugs stop the active Part immediately.
4. A bug that invalidates a Gate must be fixed before that Gate can pass.
5. PR1 residual QA remains visible; it is not converted to PASS merely because development continues.

## Part completion discipline

A Part can be marked DONE/V only when:

1. its exact output exists,
2. its completion check is evidenced,
3. relevant regression tests are green,
4. open failures are either fixed or explicitly block the Part,
5. `PROJECT_STATE.md` points to the next executable Part/Gate.

## RAW-CAT-01E research progress (2026-10-11)

- **01D**: read-only Lightroom catalog intake structurally verified, 7,023 RAW scanned/parsed, no exclusions.
- **01E.01**: point-curve syntax structurally verified on same catalog, all four curve tables per RAW decoded; 112 nonlinear composite tone curves. NOT Adobe parity.
- **01E.02**: 30/30 focused tests passed on Windows at `b5edc6c`; 7,023 records read without exclusions; 371 HSL candidates, 177 B&W mixer candidates, 30 Color Grading candidates (47 nonzero adjustments, excluding 7,023 nonzero Blending configuration values), 618 mask payloads opaque.
- **01E.03A**: Windows sample selector verified; 34/34 prior tests passed; 20 unique examples across 6 provisional groups, 10/10 evidence categories. All private sample-level data remains local.
- **01E.04A**: real aggregate DB report: 7,020/7,023 RAW local IDs overlap cache; all 7,472 cached images have exactly one Pyramid+level. Tests included in 44/44 focused Windows PASS. On-disk JPEG/photo identity still unproven.
- **01E.03B.01**: Windows 44/44 focused tests PASS; independent Adobe XMP from an isolated one-photo Lightroom catalog gave 48 exact field-expression matches, 0 mismatches, and 1 not-exported Boolean. Four point curves matched coordinates. 76 other top-level Camera Raw XMP fields remain untested; .acr/masks/Look/Profile and pixel rendering are NOT proven.
- **01E.03B.02 V2**: Windows 48/48 focused tests PASS; real Adobe XMP inventory V2 PASS: 124 global crs properties; 48 matched in one sample, 76 additional untested (71 scalar, 3 shallow sequences, 2 nested/ambiguous), one catalog-only property not exported. The corrected schema groups HSL LuminanceAdjustments separately from noise and Camera Calibration separately from HSL; labels are triage hints, NOT Adobe semantics.
- **01E.03C.01 (visible UI inspection COMPLETE)**: isolated Lightroom shows Adobe Color UI vs low-level Adobe Standard CameraProfile string (still unresolved). ONE mask is listed; Select Subject component with Invert checked, outside-subject overlay. Exactly TWO local Tone controls are nonzero among visible Tone/Color/Effects/Detail controls, all other visible local corrections are zero. Grain Amount zero; Grain Size/Roughness are shared global Grain-tool settings, NOT local mask effects. No photo IDs, mask quantities or pixels committed. This does NOT verify Adobe mask geometry, active-state semantics, original AI algorithm, .acr payload, full Profile/Look mapping or rendered pixels.
- **01E.03C.02 (PAUSED by D-016 priority)**: lrcat/XMP/.acr local-mask-structure research remains planned with all existing evidence preserved, but does not block basic context-aware GLOBAL edit investigation.
- **01F.01 (ACTIVE / PRE-G0)**: Photographer Style Fidelity First accepted as D-016; define source-only image+camera+event-context contract, prohibit edited preview/Develop leakage, support UNKNOWN/no-op and local-mask review flags. No actual visual feature extractor or learned model has been validated. A single matched RAW example is insufficient for scene model validity or training.
- **01F.03A (CODE COMMITTED / WINDOWS TEST AND RUN PENDING)**: strictly bounded PRIVATE original-RAW source-feature / Lightroom catalog target candidate manifest with input-target segregation, provisional group round-robin, local hash, and aggregate-only report. No content-identity or finality/event verification or training. See 01F.03A documentation.
- **01F.02A (CODE COMMITTED / WINDOWS VALIDATION PENDING)**: consent-gated, bounded CR3 source-only fixed rawpy linear-sRGB luminosity/decoded-RGB channel feature pilot with aggregate-only output. No arbitrary scenes inferred, no Lightroom preview/target leakage, no real RAW run or G0/G1/G2 proof.
- **01F.01A (CODE COMMITTED / WINDOWS VALIDATION PENDING)**: read-only RAW filename/extension ↔ Lightroom catalog candidate audit. Synthetic pytest cases committed; no claim of passed tests on Windows or catalog file-content matching. 0 approved training pairs. Next actual local aggregate-only audit then fixed-neutral RAW context feature pilot.

## Next action

**Phase 04 is complete.**

Phase-01 preparation is now complete at draft/engineering-prepared level through PG-01.07. PG-01.06 Evaluation Protocol 1.0 and PG-01.07 hardware/OS matrix are ready for later ratification, but G0 remains unsigned. The next executable non-manual engineering lane is **PG-00.05 portability/restore hardening**; PG-00.02 manual QA remains intentionally PAUSED. Phase 05 is not marked ready prematurely.

PG-06.02 stays BLOCKED on authorized photographer files. Residual PG-00.02 QA stays PAUSED. No Auth/Cloud implementation and no new production Brain begins here.

## Current bug batch

- **BUG-PG00-001 — CLOSED / VERIFIED:** relative managed-manifest reference + legacy absolute-path rebinding passed the focused Windows restore suite (3/3 PASS).

## Phase 01 contract risks

- **R-IDENTITY-001 — Path-derived Event identity:** current Event ID derives from root path; target contract requires stable UUID independent of Relink.
- **R-IDENTITY-002 — Singleton photographer state:** current local setup does not represent Account → Photographer → Profile as separate identities.
- **R-IDENTITY-003 — Mixed persistence:** Reviews/testing profiles/jobs/exports are not yet represented by durable versioned domain entities.
- **R-CLOUD-001 — Provider coupling:** Supabase is the initial provider, but provider URLs/table IDs must not become canonical product identities.

## Pipeline contract risks

- **R-PIPELINE-001 — RAW-centric BrainInput:** existing Brain V2 input contracts encode RAW-specific fields and must evolve without breaking candidate provenance.
- **R-PIPELINE-002 — Multiple manifest generations:** current dataset manifests use more than one historical schema; future training must consume one declared contract/version.
- **R-PIPELINE-003 — Product preview wiring:** shared versioned JPEG renderer is implemented in PG-04.01; current Darkroom illustration still is not product-quality renderer evidence until PG-04.02 wires preview/full-resolution execution.

## Current pre-photographer engineering lane

- **PG-03.02 — V**
- **PG-03.03 — V**
- **PG-03.04 — V**
- **PG-03.05 — V:** explicit approved unchanged-final identity targets are first-class; arbitrary copies remain excluded.
- **PG-03.06 — V:** source groups + exact/near-duplicate leakage guard verified.
- **PG-03.07 — V:** truthful coverage/exclusion reporting verified.
- **PG-03.08 — V:** immutable target/candidate provenance + file integrity verified.
- **PG-03.09 — V:** consolidated corruption/leakage/provenance/Locked-Test gate verified.
- **PG-03.02–PG-03.09 — PRE-PHOTOGRAPHER PACKAGE COMPLETE.** Real-photographer G1 evidence waits for representative material.

## JPEG engine / photographer-material readiness

- **PG-04.01 — V:** shared versioned JPEG EditRecipe + renderer implemented and used by J0/J1/Locked Test.
- **PG-06.01 — V:** photographer request package ready to send.
- **PG-06.02 — BLOCKED:** waits for real authorized photographer files.
- **PG-04.02 — V:** product preview/full-resolution render API, revision cache, stale/replaced-revision protection and current-approval guard verified by manual delta checks.
- **PG-04.03 — V:** encoded JPEG export quality/resize/ICC/orientation/metadata/GPS contract and reopen verification passed manual delta checks.
- **PG-04.04 — V:** safe atomic filesystem export passed exact-module manual delta/integration verification.
- **PG-04.05 — V:** renderer semantic goldens, encoded JPEG budgets and large preview-vs-export budgets passed.
- **PG-04.06 — V:** normalized JPEG controls are wired to the real renderer; stale async responses cannot replace newer state; RAW-only semantics remain separate.
- **PG-04.07 — V:** RAW/XMP boundary verified; Phase 04 complete.


## PG-01.07 platform preparation

- Windows x64 + macOS Apple Silicon are mandatory Release 1 target families.
- Windows now has one real local engineering evidence run, but not broad
  commercial hardware certification.
- Apple Silicon remains UNVERIFIED and retains blocker B-003.
- Intel Mac is EVALUATION ONLY under D-014; it is not a Release 1 blocker.
- Candidate hardware floor is 16 GB RAM + SSD; 32 GB is the recommended
  professional planning tier. These values are not final until measured.
- GPU requirements stay open until a real Brain candidate is benchmarked.


## PG-01.06 evaluation preparation

- Evaluation Protocol 1.0 draft is frozen before candidate quality results.
- G2: >=90% close-enough reconstruction + >=80% representation coverage.
- G3 primary: acceptance without correction; >=10 percentage-point improvement
  over a frozen strong simple baseline, with no serious-failure increase or new
  systematic serious failure.
- G4: >=30% median active-time saving on at least two new Events of the target
  Photographer with approved delivery quality and required platform evidence.
- G6: >=70% median beta-Event active-time saving, >=50% median per Photographer,
  initial evidence target >=3 Photographers x 3 new Events; 80%+ aspirational.
- RAW stays a separate assisted/safety evaluation path and is not blended into
  JPEG claims.
- PG-01.06 remains ◐ until G0 + ratification.
