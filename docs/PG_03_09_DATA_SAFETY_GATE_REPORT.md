# PG-03.09 — Consolidated Data Safety Regression Gate

Date: 2026-10-04  
Evidence HEAD: `6e4ab6f961d7e5ca591092b4a217954bc99ce1b6`  
GitHub Actions run: `37174673037`

## Result

**PG-03.09 — V**

On the evidence HEAD:

- `Run PR1 backend tests` — PASS
- `Compile backend training tools` — PASS

The consolidated safety suite is now part of the normal PR1 Windows CI path.

## Explicit J1 preflight boundary

`jpeg_real_j1_candidate.py` now has an explicit preflight boundary:

```text
load manifests
    ↓
snapshot integrity
    ↓
dataset/photographer contract
    ↓
exact/source-group leakage guards
    ↓
near-duplicate review guard
    ↓
dataset readiness
    ↓
target provenance verification
    ↓
ONLY THEN image decode / feature extraction
    ↓
ONLY THEN model fitting
```

This makes the fail-closed ordering directly testable.

## Test contamination guard

J1 target handling is now scan-first / decode-second.

Before any JPEG is decoded, the complete target list is checked.

If any target is:

- `test`, or
- an unsupported split,

candidate preparation stops immediately.

Therefore a target bundle cannot hide a Test target after several Train rows and cause partial feature work before the guard fires.

## Consolidated regression suite

Added:

`backend/tests/test_pg_03_09_data_safety_gate.py`

The suite covers the risks introduced/closed across PG-03.02–PG-03.08:

### PG-03.02 — Geometry

- crop / geometry mismatch is fail-closed,
- wrong-copy is rejected.

### PG-03.03 — Color / ICC

- unsafe CMYK JPEG without ICC is rejected.

### PG-03.04 — Frozen snapshot

- source mutation after Intake is rejected,
- feature decode is proven not to run after snapshot failure.

### PG-03.05 — Identity / no-edit provenance

- byte-identical Original/Edited without explicit approval remains excluded from learning.

### PG-03.06 — Source-group leakage

- cross-split Source Group blocks candidate preparation,
- unresolved near-duplicate suspect blocks candidate preparation,
- both are proven to fire before feature decode.

### PG-03.07 — Coverage truthfulness

- matched pairs, usable pairs and excluded pairs remain separate,
- exclusion reasons stay visible,
- hard groups remain visible.

### PG-03.08 — Artifact provenance

- tampered target semantics are rejected before feature decode.

### Locked Test guard

Two explicit proofs were added:

1. a contaminated target bundle containing a Test target is rejected before **any** image decode;
2. a valid candidate-preparation run may have Test pairs in the frozen Dataset, but reads only Train/Validation originals and never decodes Test pixels.

## CI integration

PR1 Windows CI now always runs:

- existing PR1 backend tests,
- JPEG integrity regressions,
- artifact provenance regressions,
- consolidated PG-03.09 safety gate,
- `python -m compileall -q app training_lab`.

A future refactor that breaks one of these fail-closed guarantees blocks CI.

## Scope

This closes the pre-photographer **engineering/data-integrity** package PG-03.02–PG-03.09.

It does not mean G1 has passed.

G1 still requires representative real photographer material, real provenance/consent and real coverage/quality evidence. The important change is that when that material arrives, it can enter an already-guarded Intake → Snapshot → Split → Coverage → J0 path instead of requiring foundational safety work first.
