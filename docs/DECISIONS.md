# Decisions

## D-001 — [SUPERSEDED] 20 Sep master plan was the development source of truth
Historical decision. Superseded by D-007 on 2026-10-04. The 20 Sep plan is archived under `docs/archive/`.

## D-002 — [SUPERSEDED] Execution order from the 20 Sep plan
Historical decision. Superseded by the Phase/Part/Gate sequence in Master Workflow v3.0.

## D-003 — macOS Apple Silicon + Windows x64 are first-release requirements
A phase that requires both cannot close based on one platform only.

## D-004 — Quality and engineering gates are separate
Phase 0 can finish on engineering evidence without pretending model quality has been proven. Model quality uses the Phase 15 evaluation path.

## D-005 — Existing faults are frozen before fixing
Known dependency, metadata, range and OS assumptions are recorded first; fixes occur in the phase assigned by the master plan.


## D-006 — JPEG learning uses an interpretable recipe-first research path before deeper models
For JPEG Original/Edited pairs, do not invent Lightroom slider labels from pixels and do not jump directly to an unconstrained image-to-image generator. First validate an explicit JPEG edit representation (J0), then predict that representation from image features (J1), preserving candidate versions and measuring them on whole held-out events.

Synthetic data may validate engineering plumbing but cannot establish photographer style or product quality. Real promotion decisions require representative photographer material with Train/Validation/Test separated by event/source group.


## D-007 — Master Workflow v3.0 is the sole active execution source of truth
Adopted 2026-10-04 under PG-00.03. `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` is the only active master execution plan. The 20 Sep plan, legacy Phase 0 checklist and prior cloud-revision status are historical material under `docs/archive/`.

## D-008 — Release 1 uses local execution with a narrow cloud control plane
Event editing, AI inference, rendering, review, export and local jobs run on the photographer's computer. Cloud scope is identity, entitlement, profile/settings backup or sync, selected learning data and managed training. ProGrapher does not automatically upload every event.

## D-009 — PG-00.02 remains open; paused QA is not a passed gate
On 2026-10-04 the product owner stopped additional manual PR1 QA for now and chose to batch remaining bugs later. Existing PASS evidence remains valid, but External Drive/Relink and final-head CI are still missing. PG-00.04 merge/tag stays blocked until PG-00.02 is explicitly closed.

## D-010 — Legacy V1 brain stays retired; candidate history must be preserved
Do not reconstruct the retired CLIP + ExtraTrees V1 brain. Each new Brain/model version that replaces or changes the active candidate is preserved for comparison against prior candidates and a simple baseline.


## D-011 — [DRAFT] Release 1 product scope contract
Prepared 2026-10-04 under PG-01.01. The working scope is defined in `docs/RELEASE_1_PRODUCT_CONTRACT.md`: independent JPEG editing is the primary Release 1 path; RAW remains an assisted safe RAW/XMP path; Windows x64 and macOS Apple Silicon are mandatory targets; event editing/inference/render/review/export stay local; cloud remains a narrow commercial control plane.

This decision is **not ratified** until G0 is signed and the product owner explicitly accepts the contract. After ratification, scope changes require a new versioned decision.
