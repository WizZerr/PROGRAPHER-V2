# Changelog

## Phase 0 — new-scope initialization — 2026-09-20
- Adopted new Master Plan as sole source of truth.
- Froze SHA-256 hashes for frontend/backend/master-plan inputs.
- Recorded static source findings without modifying production code.
- Created target OS matrix.
- Created Phase 15A evaluation protocol draft.
- Phase 0 remains IN PROGRESS.


## PR #1 testing loop + JPEG research preparation — 2026-10-02
- Added Windows PR1 automated validation for backend tests, TypeScript, Next build, and Tauri/Rust check.
- Added safe RAW/XMP review/export behavior and separate JPEG Original/Edited dataset flow.
- Added manual PR1 QA checklist and recorded confirmed source-safety/review evidence.
- Added isolated JPEG J0 representation feasibility tooling.
- Added synthetic J1 recipe-prediction benchmark with whole-event Train/Validation/Test separation.
- Added real-folder JPEG intake with SHA-256 provenance, geometry exclusions, split locking, leakage detection, and versioned reports.
- Added immutable J1 Candidate artifacts and explicit locked-Test audit tooling.
- Exercised the synthetic real-folder smoke chain end-to-end; results remain engineering evidence only and do not establish real photographer quality.
- PR #1 remains in QA / merge-gate status.

## LB-02 direct catalog write — 2026-10-26
- Added `catalog_writer`: writes per-photo global sliders (incl. Custom white balance) into a closed Lightroom Classic catalog with a new digest, historySettingsID and a "ProGrapher" History step; backup/restore, validation, single transaction, photographer-edit protection.
- Verified on a 25-photo test catalog (5 camera makers): values, digest recompute, thumbnails, History step and crops all as Lightroom's own edits; 0.02 s write.
- Decision D-022 supersedes the earlier no-direct-write rule for event delivery under these safety conditions.
