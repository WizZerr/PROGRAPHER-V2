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

## Event automatic editing: Smart Preview matching and uniform-exposure confirmation — 2026-10-30
- Fixed: Smart Preview matching stopped once half the photos matched by UUID; every unmatched photo is now looked up by RAW name, and the plan reports matched/ambiguous/unmatched counts.
- RAW names shared by more than one file in the catalog (several cameras), carried by two Smart Previews, or belonging to a Smart Preview another photo owns are never used to match.
- A plan in which photos get one uniform exposure (no Smart Previews / face model / faces, or >10% unanalysed) needs a dedicated `uniform_exposure` acknowledgement before writing; the screen shows a warning with its own checkbox.
- Tests: two cameras with the same names, a 6,000-photo catalog, duplicate previews, the 50% case, and the confirmation gate in the service and the API (synthetic catalogs only).- Fixed: photos the editor turned black & white were included when learning the profile's colour style (base sliders, exposure level, face target). They are now left out (style version 2), older styles are relearnt automatically, and the plan shows how many were left out.
