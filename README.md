# ProGrapher V2

Professional desktop AI assistant for event photographers. Hebrew-first (RTL), Windows x64 and macOS Apple Silicon target platforms.

## One active execution source of truth

**[ProGrapher Master v4.0 — `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`](docs/MASTER_PLAN_SOURCE_OF_TRUTH.md)** (2026-10-12).

**Product direction:** RAW-first photographer-specific learning, with Adobe Lightroom Classic as the first RAW development/JPEG export engine. ProGrapher owns source analysis, per-photo decisions, event orchestration, quality review and delivery. A licensed compatible Lightroom Classic installation is required for the Lightroom-First workflow. A native renderer is not promised for Release 1.

## Working documents
- [Execution Board](docs/EXECUTION_BOARD.md) — next executable task: **LB-01**.
- [Project State](docs/PROJECT_STATE.md) — evidence, current limitations and Gates.
- [Decisions](docs/DECISIONS.md) — v4 Lightroom-First decisions D-018–D-021 (existing D-017 preserved).
- [RAW-first scope decision](docs/D_015_RAW_FIRST_SCOPE.md) and [photographer fidelity decision](docs/D_016_PHOTOGRAPHER_FIDELITY_FIRST.md) — cite by file paths to avoid historic decision-ID collisions.
- [Archived v3.1 Master](docs/archive/MASTER_PLAN_SOURCE_OF_TRUTH_v3.1_2026-10-12.md) — reference only, not execution authority.

## Current evidence
- Lightroom Bridge POC v0.1.1 and v0.2.0 passed on **one Windows research RAW**: Adobe Standard plus 10 settings read back and actual JPEG generated.
- The experimental Lightroom Subject mask exists but applying local +0.25 has **not** passed.
- RAW ↔ Lightroom filename matching produced 5,208 candidates, **zero** fully verified, licensed, training-ready samples.
- No photographer-trained production Brain, unattended event processing, Mac Bridge smoke or single commercial installer yet. G0 remains open; G1–G6 have not passed.

Never commit photographer RAWs, catalogs, per-photo records or private previews. Preserve source originals and historic model candidates.

**NEXT:** LB-01 freeze/integrate local working POC, then LB-02 autonomous batch. DATA-01 consent/finality/source-identity engineering can proceed separately.
