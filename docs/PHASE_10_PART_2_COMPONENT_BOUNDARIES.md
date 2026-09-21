# ProGrapher V2 — Phase 10 Part 2 — Component Boundaries

## Goal

Finish the structural split required by P10-01 without pretending that the
actual editing intelligence already exists.

The first executable Brain V2 path is now:

`RawInputRecord`
→ `Preprocessor`
→ `FeatureExtractor`
→ `BaseModel`
→ `PhotographerAdapter`
→ `EventContext`
→ `QualityControl`
→ `BrainPipelineResult`

## Important behavior

### Preprocessing

The first implementation is metadata-only. It does not decode pixels yet.

That is intentional: the purpose of Phase 10 is to establish a stable
replaceable boundary before Phase 11+ adds real preprocessing.

### Features

The first feature implementation is deterministic EXIF metadata only.

When a numeric field is missing, the feature vector contains a numeric
placeholder plus a separate `__missing` flag. The original source contract
still keeps the field missing; zero is not silently claimed as real metadata.

### Base model

The current `FixedBaselineModel` is wiring-only.

It predicts Exposure 0 and leaves Temperature/Tint/Blacks unknown. It is not
an AI model and is not a quality candidate.

### Photographer adapter

No-op until real personal style data exists. It must not alter a recipe or
pretend personalization happened.

### Event context

No-op and explicitly unavailable.

### Quality / Critic

No-op and explicitly unavailable.

- no confidence score is emitted;
- every result requires full human review;
- `critic_checked` remains false.

## Phase 10 result

With Part 1 + Part 2:

- input contract is versioned;
- recipe units are explicit;
- model artifacts carry compatibility versions;
- training and inference share the same contracts;
- components are separated behind replaceable interfaces;
- unavailable Scene Context/Critic states are explicit;
- incompatibilities are rejected instead of silently accepted.

The next development step can move to Phase 11 without choosing a final model.
