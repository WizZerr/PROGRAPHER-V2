# Decisions

## D-001 — New master plan is the only development source of truth
The 20 Sep 2026 ProGrapher V2 Master Implementation Plan replaces the prior execution plan.

## D-002 — Execution order follows the plan, not simple numeric order
After Phase 0: Phase 4A → Phases 1–3 → Phase 4B → Phases 5–8 → early 15A/22A/23A → Phases 9–15 → etc.

## D-003 — macOS Apple Silicon + Windows x64 are first-release requirements
A phase that requires both cannot close based on one platform only.

## D-004 — Quality and engineering gates are separate
Phase 0 can finish on engineering evidence without pretending model quality has been proven. Model quality uses the Phase 15 evaluation path.

## D-005 — Existing faults are frozen before fixing
Known dependency, metadata, range and OS assumptions are recorded first; fixes occur in the phase assigned by the master plan.


## D-006 — JPEG learning uses an interpretable recipe-first research path before deeper models
For JPEG Original/Edited pairs, do not invent Lightroom slider labels from pixels and do not jump directly to an unconstrained image-to-image generator. First validate an explicit JPEG edit representation (J0), then predict that representation from image features (J1), preserving candidate versions and measuring them on whole held-out events.

Synthetic data may validate engineering plumbing but cannot establish photographer style or product quality. Real promotion decisions require representative photographer material with Train/Validation/Test separated by event/source group.
