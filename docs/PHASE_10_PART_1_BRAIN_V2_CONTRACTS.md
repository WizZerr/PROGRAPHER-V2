# ProGrapher V2 — Phase 10 Part 1 — Brain contracts

## Purpose

Create stable contracts so preprocessing, feature extraction, models,
photographer adaptation, event context, evaluation and quality control can
evolve independently without silently changing units or inputs.

## Contracts added

### BrainInput

Contains:

- source fingerprint;
- event identity;
- camera identity;
- capture time;
- RAW WB;
- EXIF;
- explicit missing fields;
- preprocessing version and implementation;
- feature vector and feature version;
- Scene Context availability;
- Critic availability;
- Brain contract version.

Missing information stays missing. It is never silently converted to zero.

### EditRecipe

Uses explicit units:

- `exposure_stops`
- `temperature_kelvin`
- `tint_units`
- `blacks_units`

It also records:

- Process Family;
- Process Version;
- Camera Profile;
- prediction origin;
- candidate ID/version;
- parent candidate;
- photographer profile identity/version when applicable;
- whether Scene Context was applied;
- whether Critic checked the output.

### ArtifactContract

Every future model artifact must record:

- model candidate ID/version;
- parent candidate;
- Brain contract version;
- preprocessing version;
- feature version;
- Dataset Manifest ID;
- software version;
- optional photographer-profile schema version.

Inference rejects an artifact when the input contract is incompatible.

### Training / Inference parity

Training and inference use the same `BrainInput` and recipe contracts.
Feature/preprocessing mismatches are rejected explicitly.

### Scene Context / Critic

Both exist in the contract now but are explicitly `not_available` in the
first experimental path. No confidence or quality score is invented.

## Next

Part 2 will create the actual component boundaries:

preprocessing -> features -> base prediction -> photographer adapter ->
event context -> evaluation / quality control

The components can initially be no-op or baseline implementations, but their
interfaces will already be fixed and testable.
