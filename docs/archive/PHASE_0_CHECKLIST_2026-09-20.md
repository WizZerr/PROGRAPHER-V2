> **ARCHIVED — HISTORICAL PHASE 0 CHECKLIST**
>
> Preserved by PG-00.03 on 2026-10-04. Do not use P00-* items as active execution instructions. Use PG-00.* in `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`.

# Phase 0 — Freeze + Safety Checklist (New Scope)

Legend: DONE / PARTIAL / NOT TESTED / BLOCKED

| ID | Task | Status | Evidence / next action |
|---|---|---|---|
| P00-01 | Freeze archives, SHA-256, create `prographer-v2`, document deps/OS/data locations | PARTIAL | SHA-256 frozen. Git branch and real-machine environment capture still required. |
| P00-02 | Backup current DB/profiles and prove restore on a copy | NOT TESTED | Supplied ZIPs contain no runtime DB/profile state. Must run against user's real working data copy. |
| P00-03 | Clean install/build/runtime/import/event/export | PARTIAL | Python compile PASS. Runtime DB absent; frontend deps not bundled. Must run clean builds on target machines. |
| P00-04 | Create 30–50 technical fixture files with license/reference | NOT STARTED | Needs test RAW set and reference outputs when available. |
| P00-05 | Project state / changelog / decisions / regression records | DONE (initial) | New-scope Phase 0 pack created. Must keep updated during evidence collection. |
| P00-06 | Define Phase 15A measurement protocol | DONE (draft) | See `EVALUATION_15A_PROTOCOL.md`. Numeric promotion thresholds remain to be locked before model selection. |
| P00-07 | Lock target matrix and check Python/rawpy/PyTorch/model components per target | PARTIAL | Matrix locked by master plan. Compatibility evidence still required on Windows + Apple Silicon; Intel Mac feasibility open. |
| P00-08 | Define real Mac + Windows test/build environments and versions | PARTIAL | Required evidence sheet created. Actual machines/versions must be filled and tested. |

## Phase 0 completion gate
Phase 0 may be marked DONE only when all mandatory engineering evidence in the master plan has been run and recorded. A known failure may be documented, but it may not be represented as a passed test.
