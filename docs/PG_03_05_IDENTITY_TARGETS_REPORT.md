# PG-03.05 — Approved Identity Targets

Date: 2026-10-04  
Evidence HEAD: `5423c820d1398415fd0c332248fde499a35304ce`  
GitHub Actions run: `37172073037`

## Result

**PG-03.05 — V**

Relevant Windows backend regression completed successfully.

## Contract

A byte-identical Original/Edited JPEG is **not** automatically a learning label.

Three states are separated:

1. **unchanged_unverified** — files are byte-identical but there is no explicit human approval. Preserved for audit, excluded from learning.
2. **identity_approved** — files are distinct physical files, byte-identical, and the photographer/intake evidence explicitly confirms the final was intentionally unchanged. This is a valid identity/no-edit target.
3. **identity approval conflict** — the approval says unchanged, but current bytes are no longer identical or the approved pair cannot be matched. Intake fails instead of guessing.

Selecting the same physical file as both Original and Edited remains invalid.

## Evidence format

The real JPEG Intake accepts an optional `--identity-approvals` JSON file using schema:

`prographer.identity-approvals.v1`

Each approval binds:

- photographer ID,
- event ID,
- original relative path,
- decision `approved_unchanged_final`,
- approver identity,
- approval timestamp,
- optional note.

The approval file SHA-256 is recorded in the dataset manifest.

## Learning behavior

Approved identity targets are written into the event J0 manifest with:

- `identity_target_approved: true`
- `target_kind: identity`

J0 accepts these byte-identical pairs and fits/evaluates the identity/no-edit target.

Unapproved byte-identical pairs are still rejected by J0.

Therefore "no edit" can participate in later training/evaluation only when it has explicit provenance.

## Regression evidence

`backend/tests/test_jpeg_integrity.py::test_identity_target_requires_explicit_approval_and_reaches_j0` proves:

- identical pair without approval is excluded,
- the same pair with explicit approval becomes usable,
- approval provenance is recorded,
- the approved identity target completes J0,
- stale approval against changed Edited bytes blocks Intake.

This is engineering/provenance evidence, not photographer-quality evidence.
