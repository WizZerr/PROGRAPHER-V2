# PG-03.08 — Immutable Target & Candidate Provenance

Date: 2026-10-04  
Evidence HEAD: `5caf2ea343182e369619c9fda4a5a5062f566a9d`  
GitHub Actions run: `37174158871`

## Result

**PG-03.08 — V**

On the evidence HEAD:

- Windows backend regression passed.
- `python -m compileall -q app training_lab` passed.

## Shared provenance contract

Added:

`backend/app/evaluation/artifact_provenance.py`

The contract is shared by J0 target generation, J1 candidate training and locked-Test audit.

## Immutable J0 Target Bundles

J0 no longer treats one mutable `recipe_targets.json` as the target identity.

It creates:

```text
target_bundles/
  targets-<identity>/
    recipe_targets.json
```

Target identity binds:

- dataset snapshot,
- dataset manifest evidence,
- semantic target content,
- exact Git commit,
- dependency-lock SHA-256,
- JPEG color contract version,
- J0 feature/representation contract version,
- recipe contract version,
- renderer contract version,
- split mode,
- J0 configuration.

Timestamps and output locators are not target semantics.

Changing recipe target content or any material contract/config input creates a new target artifact ID.

An existing immutable target artifact is not overwritten.

## Immutable J1 Candidate Identity

J1 verifies the target provenance before fitting.

Candidate identity binds:

- candidate family/model version,
- frozen dataset snapshot,
- dataset manifest evidence,
- target artifact ID + target semantic fingerprint,
- exact Git commit,
- dependency-lock SHA-256,
- color contract version,
- measured-feature contract version,
- exact ordered feature-name fingerprint,
- recipe contract version,
- renderer contract version,
- estimator/normalization configuration.

The candidate path is:

```text
candidates/
  candidate-<identity>/
```

If the same candidate identity already exists, training refuses to overwrite it.

A material config/version/commit/target change creates a different candidate ID.

## Candidate artifact integrity

Completed candidate files are sealed by:

`artifact_manifest.json`

It records SHA-256 + size for:

- `candidate_provenance.json`
- `model/model.npz`
- `model/model_contract.json`
- `summary.json`
- `validation_results.csv`
- validation contact sheet when present

The Locked Test audit verifies this manifest **before loading the model**.

A candidate whose bytes changed after creation is rejected.

## Rejected / non-promoted candidates

Candidate creation and candidate promotion are separate.

A J1 candidate starts as:

- `evaluated_validation`
- `promotion_status: not_promoted`
- immutable

Not promoting or later rejecting a candidate does not delete or overwrite its artifact. Future candidates receive their own IDs and remain comparable.

## Locked Test compatibility checks

Before opening locked Test, the audit verifies:

- candidate provenance self-consistency,
- candidate artifact file hashes,
- dataset snapshot identity,
- dataset manifest binding,
- color contract compatibility,
- feature contract compatibility,
- recipe contract compatibility,
- renderer contract compatibility,
- model-contract / summary / provenance agreement.

## Regression evidence

`backend/tests/test_artifact_provenance.py` proves:

- target identity ignores timestamp/output-locator noise,
- target recipe/content changes create new IDs,
- code revision changes create new IDs,
- dependency-lock changes create new IDs,
- color/feature/renderer version changes create new IDs,
- model configuration changes create new IDs,
- target semantic changes create new Candidate IDs,
- existing artifact directories refuse overwrite,
- provenance IDs self-verify,
- target tampering is detected,
- candidate file-byte tampering is detected,
- canonical config hashing is independent of JSON key order.

## Important scope

This Part makes experiments reproducible and immutable.

It does **not** claim that any candidate is good, production-ready or promotable. Quality still requires the later Gates on real photographer material.
