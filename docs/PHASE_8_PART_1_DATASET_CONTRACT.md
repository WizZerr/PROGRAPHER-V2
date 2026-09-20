# ProGrapher V2 — Phase 8 Part 1 — Dataset Contract + Conservative Pairing

## Implemented

- Versionable Dataset V2 contract foundation.
- RAW source identity includes:
  - path,
  - relative path,
  - filename / extension,
  - size / mtime,
  - source fingerprint.
- XMP reader captures:
  - Exposure,
  - Temperature,
  - Tint,
  - Blacks,
  - Process Version,
  - Camera Profile.
- Missing metadata remains `None`.
- A real numeric zero remains zero.
- Pairing is conservative:
  1. same relative path + stem,
  2. explicit source filename declared by XMP,
  3. unique filename stem.
- Ambiguous candidates are NOT silently paired.
- XMP sidecar presence is NOT treated as proof of a final photographer edit.
- `verified_training_pairs` remains zero until final-edit provenance is proven.
- Deterministic Train / Validation / Test assignment is by Event ID, never
  by individual photo.

## Important limitation

This Part does not yet read a real Lightroom catalog or Virtual Copies.

An XMP sidecar alone cannot prove:
- that it is the photographer's final edit,
- Lightroom Virtual Copy identity,
- that masks / local edits are within the supported learning scope.

Those remain explicit future Phase 8 work.

## Current user-data dependency

None is required for these engineering tests.

A useful personal dataset still requires the photographer's real RAW + final
Lightroom edits. The implementation must not fabricate that evidence.
