# ProGrapher V2 — Execution Board v4.0

**Updated:** 2026-10-12  
**Authority:** [MASTER_PLAN_SOURCE_OF_TRUTH.md](MASTER_PLAN_SOURCE_OF_TRUTH.md) — v4.0 Lightroom-First / Photographer-Fidelity / Event-First.  
**Previous full board:** [archive/EXECUTION_BOARD_v3.1_2026-10-12.md](archive/EXECUTION_BOARD_v3.1_2026-10-12.md).

This board is an execution view, never a second master plan. One active Part per lane; no research result is promoted to production quality without the proper Gate.

## What has and has not passed

| Component | State | Evidence / limitation |
|---|---|---|
| Desktop/event/RAW/Brain contracts | EXISTS | Repository contains Tauri, Next.js, FastAPI, SQLite and research modules; no full-event AI editing proof |
| **B0 Lightroom single-RAW Bridge** | **PASS, limited** | Original v0.2 (9,152,353-byte JPEG), plus newly integrated LB-01 user-verified on one Windows RAW (9,154,074-byte JPEG); no batch/mask proof |
| Masking | RESEARCH INCOMPLETE | One Subject mask visible, local Exposure still 0.00; creation origin, local edit and masked export not proven |
| Source RAW scene research | RESEARCH | Local CLIP on 12 original RAW inputs, one abstention; no calibrated or photographer-approved scene accuracy |
| Photographer training dataset | BLOCKED | 5,208 RAW/catalog filename-only candidates, **0 validated training-ready examples** |
| B1 unattended batch | NOT RUN | No unattended 10/100-photo pipeline, idempotence, source readback or resume evidence |
| AI personalized edits | NOT TRAINED/VALIDATED | No authorized event-held-out photographer model and no G1–G3 |
| Installer / Apple Silicon | NOT VERIFIED | Windows and Mac Lightroom version matrix, installation/update/recovery pending |

## Current work lanes

| Lane | Next execution Part | Status | Exit criterion |
|---|---|---|---|
| Master docs adoption | **PG-00.LB01** | **DONE (docs only)** | v3.1 archived, v4 master/decisions/board/state/README aligned. No Gate advanced. |
| Lightroom POC integration | **LB-01 / PG-04.LB01** | **RESEARCH INTEGRATION MERGED (PR #2); 16 LOCAL TESTS PASS** | 16 local synthetic pytest cases PASS (Windows, 0.50s, exit 0) on PR head 88c49a6; real Lightroom single RAW readbacks and 9,154,074-byte JPEG, unchanged RAW hash |
| Autonomous Bridge queue | **LB-02** | PLANNED | Authenticated loopback, capability check, job ID, heartbeat and 10→100 RAW idempotent apply/readback/export/restart |
| Photographer data | **DATA-01 / PG-03/06** | RESEARCH READY; G1 BLOCKED | Consent, true source identity, final edit state, source grouping and whole-event split |
| Personalized model | **BRAIN-01 / PG-07/08** | BLOCKED G1/G2 | Strong baseline, valid source-only features, held-out whole-event audit and confidence/abstain |
| Event run | **EVT-01 / PG-09/11** | BLOCKED B1/G3 | Verified 100–300 photo pilot, then larger event, review, JPEG delivery and photographer time study |
| Mac + installer | PG-02/15 | PLANNED | Mac smoke, SDK compat, single installer, signed updates and rollback |
| Local mask add-on | v0.3.x | PAUSED RESEARCH | Prove local +0.25 edit and mask correctness; not mandatory for global-first evaluation |
| Historical baseline | PG-00.02/PG-00.05 | OPEN/PAUSED | Finish drive/restore/CI and licensed fixture QA, then G0 |

## Gates

| Gate | Current status | Passing evidence |
|---|---|---|
| G0 — engineering baseline | **OPEN** | PR1/recovery/backup, source-safety and final CI |
| B0 — single RAW Lightroom Bridge | **PASS, Windows single research RAW** | Profile, 10 settings, readback and JPEG |
| B1 — autonomous batch | **NOT RUN** | 10→100 RAW correct idempotent unattended jobs and exports |
| G1 — validated learning data | **BLOCKED, zero verified pairs** | Consent, identity, finality, event grouping/splits |
| G2 — learnable targets | NOT PASSED | Scoped RAW recipe representation, supported-coverage audit, baseline |
| G3 — Brain candidate | NOT PASSED | Unseen-event style fidelity vs frozen baseline, no systematic critical failure |
| G4 — local value | NOT PASSED | Event workflow, accepted JPEG, active-time savings and two-OS evidence |
| G5 — independent beta | NOT PASSED | Tested installer/plugin, entitlement, privacy, recovery and updates |
| G6 — commercial launch | NOT PASSED | Real multi-photographer evaluation, cost/support, release blockers |

## LB-01 integration review disposition (2026-10-12)

- PR #2 merged to `main` after remote merge check, merge commit `2df653526456345bf2f08a77b35e756f967af2f8`. The repository contains the research adapter, not a trained Brain or unattended bridge.
- Local Windows review checkout of `88c49a6`: **16/16 synthetic pytest PASS**, exit 0. This is not Lightroom SDK batch coverage.
- Hosted CI run `38289239558`: job never started. GitHub Billing showed 2,000/2,000 included Actions minutes used; failure is infrastructure/quota, **not failing test assertions**. Scoped decision: local testing for LB-01, hosted workflow kept manual-only. Do not mark CI green.
- One-RAW Adobe SDK positive proof is from the integrated plugin prior to the narrow error-reporting refinement; no new Lightroom positive-path validation of that revision is claimed.
- G0 remains OPEN. G1-G6 are NOT PASSED. A reviewed POC integration may merge without promoting product readiness.

## Persistent blockers
- Existing PG-00.02/PG-00.05 blockers: external-drive/relink, final-head CI, historical restore and licensed-camera fixture.
- Missing Mac Apple Silicon Lightroom end-to-end proof.
- No approved photographer event split/finality/usage permission for training.
- Local plugin IPC, unattended jobs and cross-catalog behavior unverified.
- Mask edit v0.3.3 remains unsupported pending a successful readback and JPEG.
- No photographer-authorized independent event acceptance/time measurements.

## Non-negotiable rules
1. No private photographer RAW, catalogs, XMP, filenames, manifests or private previews in GitHub.
2. No original RAW mutation. Direct `.lrcat` writes only through `catalog_writer` under D-022 (Lightroom closed, backup first, photographer edits protected).
3. Keep all model candidates/baselines; retired V1 stays retired.
4. Maintain source-only inference: no Lightroom targets or post-edited pixels in inputs.
5. Record SHA, test results, platform, assumptions and failure reason for each Part.
6. Claims must match the narrowest evidence. A successful POC is not a production-ready feature.

**NEXT:** Safely synchronize the Windows development worktree with merged `main` (preserve existing modified/untracked local files). Then begin LB-02 as a new reviewed Part while DATA-01 remains separate.
