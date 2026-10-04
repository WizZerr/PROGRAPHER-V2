# ProGrapher V2 — Execution Board

Updated: 2026-10-04  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` — Master Workflow v3.0

This board implements **PG-00.06**. It is an execution view, not a second master plan.

## Operating rule

At any moment each development lane has at most one active Part. A bug, research experiment and product capability are tracked separately and never silently promoted into each other.

Status vocabulary:

- **ACTIVE** — current work.
- **READY** — executable when the active Part finishes or capacity is available.
- **PAUSED** — intentionally stopped; evidence remains incomplete.
- **BLOCKED** — dependency or hardware/data gate prevents completion.
- **DONE** — exact Part completion criteria have evidence.

## Current lanes

| Lane | Part | Status | Exact next output |
|---|---|---|---|
| Primary development | **PG-00.05** | ACTIVE | Fixture/restore matrix; identify what can be proven now and what requires real user backup/licensed source material |
| PR1 QA | **PG-00.02** | PAUSED | Later: External Drive/Relink manual evidence + final-head CI; do not mark PASS until both are resolved |
| Integration | **PG-00.04** | BLOCKED | Review/merge/tag only after PG-00.02 closes |
| Planning/governance | **PG-00.06** | DONE | This board + blockers + risk map + work classification |
| Next product phase | **PG-01.01** | BLOCKED BY G0 | Release 1 product contract becomes executable only after G0 |

## Blockers

| ID | Blocks | Blocker | Resolution evidence |
|---|---|---|---|
| B-001 | PG-00.02 / PG-00.04 / G0 | No external drive available for disconnect/reconnect QA | Real external drive test or later explicitly approved equivalent hardware QA |
| B-002 | PG-00.02 / PG-00.04 / G0 | Final-head CI not yet recorded after the latest PR1 QA/test/doc commits | Green PR1 validation on the final merge candidate SHA |
| B-003 | Platform gates later in workflow | No real Apple Silicon run evidence | App/engine smoke on supported Apple Silicon Mac |
| B-004 | PG-00.05 full completion | No verified copy of the user's historical DB/profile backup has been restored in this workflow | Restore on a copy; profile/events/reviews readable; source files unchanged |
| B-005 | G1/G2/G3 quality work | Representative photographer dataset is not yet available | Authorized events split by whole event/source group with provenance |
| B-006 | Commercial claims | No real photographer quality/time-savings measurement | Gate-specific evaluation on unseen photographer events |
| B-007 | PG-00.05 | JPEG profile stores an absolute dataset manifest path, so backup copied to a new app-data location may reference the old path | Define portable manifest reference/migration and prove restore |
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
| Crash loses local scan/job progress | High | current scan job is in-memory; risk documented | PG-05 |
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

## Next action

**PG-00.05 is the only ACTIVE primary-development Part.**

PG-00.02 stays PAUSED until the owner returns to the remaining PR1 hardware/manual QA. PG-00.04 stays BLOCKED. No Auth/Cloud implementation and no new production Brain begins from Phase 00.

## Current bug batch

- **BUG-PG00-001** — JPEG manifest backup path is absolute and may not survive restore to a different app-data location. High backup/restore risk; batch-fix later before PG-00.05 can close.

## Phase 01 contract risks

- **R-IDENTITY-001 — Path-derived Event identity:** current Event ID derives from root path; target contract requires stable UUID independent of Relink.
- **R-IDENTITY-002 — Singleton photographer state:** current local setup does not represent Account → Photographer → Profile as separate identities.
- **R-IDENTITY-003 — Mixed persistence:** Reviews/testing profiles/jobs/exports are not yet represented by durable versioned domain entities.
- **R-CLOUD-001 — Provider coupling:** Supabase is the initial provider, but provider URLs/table IDs must not become canonical product identities.

## Pipeline contract risks

- **R-PIPELINE-001 — RAW-centric BrainInput:** existing Brain V2 input contracts encode RAW-specific fields and must evolve without breaking candidate provenance.
- **R-PIPELINE-002 — Multiple manifest generations:** current dataset manifests use more than one historical schema; future training must consume one declared contract/version.
- **R-PIPELINE-003 — Renderer gap:** current Darkroom visual illustration is not a versioned JPEG renderer and cannot serve as product-quality evidence.

## Current pre-photographer engineering lane

- **PG-03.02 — V**
- **PG-03.03 — V**
- **PG-03.04 — V**
- **PG-03.05 — V:** explicit approved unchanged-final identity targets are first-class; arbitrary copies remain excluded.
- **PG-03.06 — ACTIVE PRE-PHOTOGRAPHER:** harden whole-event split against source groups, copies and near-duplicates.
