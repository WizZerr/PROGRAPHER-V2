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


## D-012 — [DRAFT] Supabase is the initial Release 1 cloud provider
Prepared 2026-10-04 under PG-01.02.

Initial cloud implementation target:

- Supabase Auth for authentication,
- Supabase PostgreSQL for the commercial control-plane database,
- Supabase Storage for private profile/model artifacts and explicitly selected learning material,
- local SQLite remains the operational source of truth for Event/PhotoAsset/Run/RecipeRevision/Review/Export.

Supabase is an implementation provider, not the ProGrapher domain model. Canonical IDs and contracts must remain portable so the provider can be changed later without redefining Account, Photographer, Profile or Event identity.

No Supabase cloud resources are considered production-ready merely because this decision exists. Cloud implementation remains gated by the Master Workflow.


## D-013 — [DRAFT] One versioned pipeline spine serves training and inference
Prepared 2026-10-04 under PG-01.03.

Canonical spine:

`source → color/preprocess → features → model/profile → recipe → renderer`

JPEG and RAW remain semantically separate. Product inference may use source-side information only and must never depend on the edited target. NoOp/fixed baselines are wiring/comparison components and cannot be presented as implemented AI capability.

Ratification waits for G0.


## D-014 — [DRAFT] Intel Mac is evaluation-only for Release 1
Prepared 2026-10-06 under PG-01.07.

Release 1 remains mandatory on **Windows x64** and **macOS Apple Silicon arm64**.

Intel Mac (`x86_64`) is a separate feasibility track:

- it is not a Release 1 launch blocker,
- Phase 02 may run a low-cost build/start smoke if suitable hardware is
  available,
- no Intel Mac support/marketing promise exists without a later versioned
  promotion decision,
- Intel support must not reduce testing depth, performance or packaging quality
  on the two mandatory platforms.

This decision is still a draft while G0 is unsigned.


## D-015 — [DRAFT] Evaluation Protocol 1.0 freezes the initial promotion metrics
Prepared 2026-10-06 under PG-01.06.

Before real candidate selection:

- G2 uses close-enough representation fidelity + representation coverage,
- G3 primary metric is **acceptance without manual correction**, not time saved,
- G4/G6 use active workflow time at equal approved delivery quality,
- JPEG and RAW evidence remain separate.

Initial thresholds are the Section-7 values from Master Workflow v3.0:

- G2: >=90% close-enough in-scope Validation pairs and >=80% representation
  coverage,
- G3: >=10 percentage-point acceptance improvement over a frozen strong simple
  baseline, no serious-failure-rate increase and no new systematic serious
  failure,
- G4: >=30% median active-time saving on at least two new Events of the target
  Photographer,
- G6: >=70% median beta-Event saving, >=50% median per Photographer; 80%+ is
  aspirational, with an initial evidence target of at least 3 Photographers x
  3 new Events.

Changing a threshold after observing a candidate cannot retroactively make that
candidate pass. A new protocol version and future evaluation are required.

This decision remains draft until G0 and Phase-01 ratification.
