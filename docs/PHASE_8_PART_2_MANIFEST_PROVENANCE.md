# ProGrapher V2 — Phase 8 Part 2 — Manifest + Final Edit Provenance

## What this adds

- Explicit final-edit review state:
  - `unreviewed`
  - `verified_final`
  - `rejected`
- A technical RAW ↔ XMP match is still not enough.
- Only an explicitly verified final edit can become training data.
- Explicit initial exclusion policy:
  - missing Exposure / Temperature / Tint;
  - ambiguous pair;
  - missing pair;
  - local masks / brush / gradient / retouch signals.
- Local adjustments are preserved as provenance, but excluded from the
  initial global Exposure/WB dataset.
- Atomic, versioned Dataset Manifest JSON.
- Manifest records:
  - source identity,
  - target recipe,
  - pairing method,
  - final-edit state,
  - exclusion reasons,
  - event-level split,
  - training usability.
- Train/Validation/Test scope remains `event`, never photo.

## Why local adjustments are excluded now

Phase 8 requires an explicit policy when masks or edits outside the initial
target scope exist. The initial ProGrapher target is global Exposure,
Temperature and Tint. A photo with local edits can still be useful later, but
it is not allowed into the first training set until that policy is validated.

## Virtual Copies

The contract reserves `virtual_copy_name`, but this Part does not invent
Virtual Copy identity from an XMP sidecar.

Real Lightroom catalog / plugin evidence is required for that later step.

## No personal training data required

All engineering behavior is testable with synthetic fixtures.
A photographer's real profile still waits for real RAW + final edits.
