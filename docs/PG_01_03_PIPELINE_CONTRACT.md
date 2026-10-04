# ProGrapher V2 — Unified Training & Inference Pipeline Contract

Version: **0.1 DRAFT**  
Prepared: 2026-10-04  
Workflow Part: **PG-01.03**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

> This contract defines one versioned pipeline spine shared by training, evaluation and product inference. It does not select a final model and does not claim AI quality.

## 1. Canonical pipeline

```text
Source
  ↓
Decode / Color / Preprocess
  ↓
Feature Extraction
  ↓
Model + Photographer Profile
  ↓
Recipe
  ↓
Renderer
  ↓
Preview / Export
```

Every production candidate must declare the version of each stage.

## 2. Non-negotiable rule

**Inference for a new photo must never require the edited target.**

Edited material may be used only for:

- target extraction,
- representation validation,
- training,
- validation,
- locked testing.

If any inference code path reads the paired edited target, the evaluation is invalid.

## 3. Shared version bundle

Every model/profile candidate must bind:

- `pipeline_contract_version`
- `source_contract_version`
- `color_preprocess_version`
- `feature_contract_version`
- `model_contract_version`
- `profile_schema_version`
- `recipe_contract_version`
- `renderer_contract_version`
- `dataset_manifest_id / hash`
- `software_commit`
- dependency/runtime version evidence

Changing a material stage creates a new Candidate/ProfileVersion identity.

An artifact is rejected when required versions are incompatible. It is never partially loaded and silently approximated.

## 4. Source stage

The Source stage receives a `PhotoAsset`, not a raw filesystem path as identity.

Required source facts:

- `photo_asset_id`
- `event_id`
- `media_kind: jpeg | raw`
- content fingerprint/hash
- mutable local locator
- available metadata
- explicit missing fields

A path may locate bytes but is not source identity.

## 5. JPEG path

JPEG is the primary independent Release 1 path.

### Product inference

```text
Original JPEG
→ ICC / EXIF orientation / normalized decode
→ working color space
→ feature extraction
→ photographer JPEG profile
→ JPEG edit recipe
→ versioned renderer
→ preview/final JPEG
```

The edited reference is absent during inference.

### Training/evaluation

```text
Original JPEG ───────────────┐
                            ├→ validated pair / geometry / color contract
Edited JPEG ────────────────┘
                            ↓
                    target representation
                            ↓
         train / validation / locked test
```

Target generation and source-side inference preprocessing must use compatible color/geometry contracts.

## 6. RAW-assisted path

RAW remains separate.

```text
RAW
→ supported RAW metadata / embedded preview / known decode path
→ RAW-specific features/profile
→ supported RAW recipe
→ assisted preview
→ XMP/Lightroom bridge
```

The RAW path must not reuse a JPEG recipe merely by renaming fields.

The assisted preview is not represented as exact Lightroom output unless a later renderer contract proves that claim.

## 7. Decode / color / preprocess contract

This stage owns:

- media decode,
- ICC interpretation,
- working color space,
- gamma/transfer handling,
- bit-depth policy,
- EXIF orientation,
- geometry normalization allowed by the data contract,
- deterministic resize/crop behavior,
- missing metadata handling.

It must output a versioned representation.

It must not:

- silently stretch mismatched original/edited geometry,
- silently assume missing ICC is equivalent to a known profile,
- replace missing metadata with zero,
- apply random augmentation during deterministic product inference.

## 8. Feature contract

Feature extraction receives only normalized source-side information.

A Feature artifact declares:

- version,
- ordered feature names,
- values,
- categorical context,
- missing-field semantics.

Existing `BrainInput.FeatureVector` is retained as useful foundation.

Future JPEG features may extend or replace RAW-centric fields, but version changes must be explicit.

No Feature extractor may read target/edited pixels at inference time.

## 9. Model contract

The Model consumes source-side features and an explicit ProfileVersion.

It produces a Recipe candidate plus provenance:

- candidate ID,
- candidate version,
- profile ID/version,
- parent candidate where applicable,
- confidence/availability fields when defined later.

Model complexity is not a success criterion.

A FixedBaseline / NoOp component is allowed for wiring tests but must be labeled as such and cannot be presented as implemented intelligence.

## 10. Profile contract

The Profile layer scopes prediction to the Photographer.

A ProfileVersion is immutable and binds:

- model artifact(s),
- normalizer,
- supported media kind,
- compatible feature/preprocess versions,
- compatible recipe/renderer versions,
- metrics and evaluation provenance.

JPEG and RAW ProfileVersions are never silently interchangeable.

## 11. Recipe contract

Recipe is the intermediate editing representation.

Rules:

- recipe is versioned,
- unsupported parameters fail explicitly,
- missing values stay missing where the contract permits,
- no silent clamp,
- RAW and JPEG recipes may have different schemas,
- the Renderer declares which Recipe contract it supports.

The existing RAW/Lightroom recipe contract remains valid only for its declared scope.

JPEG recipe scope is determined by J0/G2 evidence, not by Lightroom naming conventions.

## 12. Renderer contract

Renderer is a first-class versioned stage.

For JPEG Release 1 it must eventually support:

- deterministic rendering from source + recipe,
- same render semantics in evaluation and product inference,
- preview/final-output consistency within defined tolerances,
- explicit output color profile,
- safe output paths,
- source immutability.

For RAW-assisted flow, renderer/preview limitations remain explicit and separate.

## 13. Training pipeline

A TrainingRun receives an immutable Dataset snapshot/manifest.

Required flow:

```text
Dataset snapshot
→ validate rights/provenance
→ validate bytes/hash
→ validate pair/geometry/color
→ source preprocess
→ target extraction
→ split guard
→ source feature extraction
→ train candidate
→ validation
→ freeze candidate
→ locked test
→ candidate report
```

Test data must not be used to:

- fit weights,
- choose hyperparameters,
- choose target representation,
- select a candidate,
- tune thresholds.

## 14. Inference pipeline

Required product flow:

```text
PhotoAsset
→ verify source availability/fingerprint policy
→ source preprocess
→ features
→ compatible active ProfileVersion
→ prediction
→ recipe validation
→ renderer
→ persisted RecipeRevision
→ Review / Export
```

An unavailable required component returns an explicit unavailable/failure state.

It must not silently substitute a NoOp and label the result as AI-edited.

## 15. Review / correction feedback

Review and user correction sit **after** prediction.

A corrected RecipeRevision may become learning material only when:

- the revision is committed,
- source identity is known,
- provenance is valid,
- the learning-consent contract allows it,
- it is assigned to a new Dataset version.

The live product does not mutate the active ProfileVersion directly from one correction.

## 16. Current implementation mapping

| Existing component | Keep | Gap |
|---|---|---|
| `BrainInput` + preprocessing/features versions | yes | currently RAW-centric; must generalize source/media contract |
| `ArtifactContract` | yes | extend to recipe/renderer/profile compatibility and stronger artifact hashes |
| `FixedBaselineModel` | yes, wiring baseline only | never quality claim |
| Dataset manifest + hashes | yes | unify current manifest generations under the new dataset contract |
| RAW recipe validation | yes | only RAW/Lightroom scope |
| JPEG pair manifest | yes | needs color/geometry + renderer contract before product learning |
| Current Darkroom illustration | temporary UI aid | not the Release 1 JPEG renderer |

## 17. Failure semantics

Pipeline failures are typed and visible.

Minimum categories:

- source_missing
- source_changed
- unsupported_media
- decode_failed
- color_contract_failed
- geometry_contract_failed
- feature_contract_incompatible
- profile_incompatible
- model_unavailable
- recipe_invalid
- renderer_incompatible
- render_failed
- export_failed

A partial pipeline result is never marked as a completed Event edit.

## 18. Determinism and reproducibility

Given:

- the same source bytes,
- same Pipeline contract versions,
- same ProfileVersion,
- same model artifacts,
- same deterministic configuration,

product inference must be reproducible within the documented backend tolerance.

Any nondeterministic stage must declare why and how it is evaluated.

## 19. PG-01.03 completion checklist

- [x] One shared source→preprocess→features→model/profile→recipe→renderer spine is defined.
- [x] JPEG and RAW paths are separate at the semantic level.
- [x] Edited target is forbidden at inference time.
- [x] Pipeline stages are version-bound.
- [x] NoOp/baseline cannot masquerade as intelligence.
- [x] training/validation/test responsibilities are separated.
- [x] Review/corrections create later learning evidence rather than mutating the active profile inline.
- [x] failure semantics are explicit.
- [x] current code is mapped to the target contract.
- [ ] G0 is signed and the contract is ratified for implementation.

Until G0, PG-01.03 remains **◐ prepared**, not V.
