# RAW-CAT-01F — Visual Context Research (D-016)

State: pre-G0 RESEARCH/ENGINEERING PREPARATION. No production Brain. Date 2026-10-11.
Owner source of truth: docs/MASTER_PLAN_SOURCE_OF_TRUTH.md + D-015 + D-016.

## Hypothesis and falsifiable test

For a **specific** event photographer, image scene/lighting features extracted strictly from original RAW may help predict their approved final global Lightroom edits better than static style or camera/EXIF-only inputs, on new whole held-out events. If visually conditioned predictions do not improve over well-defined baselines, do NOT increase model complexity without a measured reason.

## Parts / execution order

| Part | Status | Deliverable | Definition of done |
|---|---|---|---|
| RAW-CAT-01F.01 | ACTIVE / spec-prep | Versioned raw-only context feature + provenance contract, privacy and leakage rules | Input/target boundary, null/unknown states, scene label vocabulary, and synthetic safety checks identified; architecture doc reviewed |
| RAW-CAT-01F.01A | ACTIVE / Windows run pending | Privacy-safe disk/catalog source readiness name join | Aggregate counts from actual user machine; no identities/filename lists exported; ambiguous duplicate keys reported not silently joined |
| RAW-CAT-01F.02 | READY / depends on 01F.01 | Safe reproducible RAW-neutral decode and technical/light features | Source RAW read-only, hash unchanged, versioned decode settings, controlled color handling, metadata + numerical features on LICENSED fixtures; no Lightroom cache/edited previews |
| RAW-CAT-01F.02A | ACTIVE / local proof pending | Small source-only fixed-decode linear RGB feature smoke test, no scene prediction | Synthetic tests + a strictly bounded consented Windows RAW run, path/identity-free aggregate metrics, failures counted, source safety preserved |
| RAW-CAT-01F.03 | READY / depends on approved RAW | Small, photographer-confirmed multi-scene pilot manifest | Authorized original RAW bytes matched to catalog records; photographer-confirmed final recipes/event membership; event-scoped privacy-preserving report, excluded/missing cases labelled |
| RAW-CAT-01F.04 | BLOCKED on 01F.02+03 and gate ratification | Context-feature validity study | Independent human labels for daylight, dim indoor, strongly colored/mixed lights, other/unknown; error/confidence + failure analysis; no unsupported labels |
| RAW-CAT-01F.05 | BLOCKED on G0/G1 and sufficient approved event data | Three-arm offline benchmark preregistration/execution | Whole-event train/validation/locked-test, same final global recipe targets and cases for style-only, EXIF-only, and EXIF+image-context comparisons; stable metrics, results reviewed, no leakage |
| RAW-CAT-01F.06 | BLOCKED on G2/G3 data/results | Personal style review and abstention rule | Blinded photographer acceptance and editing-time pilot, preserve no-op and local-mask-only review flags; candidate version retained if superseded |

Status READY means a plan exists, NOT permission to execute past required gates.

## Proposed contract (v0 — to be implemented and versioned)

Each input sample has:
- **Provenance stored privately**: photographer permission, original camera RAW hash, catalog-image match evidence, event/group identity from photographer, capture/source version; NO photo-level identifiers in shareable report.
- **Camera facts available at inference**: camera and lens metadata, ISO, shutter, aperture, focal length, camera as-shot WB if technically available and honest about availability.
- **Scene/light measurements from original RAW**: consistently decoded neutral RAW-derived RGB statistics or sensor-space proxies, luminance/contrast distribution, spatial brightness, clipping indicators with decoder limitations, color distribution, white-balance ambiguity, noise/blur proxies only where validated. Specify RAW decoder, demosaic, camera/working color transform and fixed settings.
- **Scene hypotheses, not facts**: daylight/outdoor, indoor ambient, dim reception, saturated/mixed artificial stage light, portrait/group/dancing/other — scores with UNKNOWN and annotation provenance. Avoid GPS, face identity, inferred sex/age/ethnicity or biometric classification.
- **Output separation**: final approved Lightroom recipe only as target; mask presence/type is an unsupported-local-edit indicator for initial global edit experiments (exclude/quarantine/route for human review per declared protocol), NEVER a guessed zero mask. Treat no-change as a first-class label.
- **Inference consistency**: cannot require final edits, masks, Lightroom cache or any data not available when predicting a NEW photo.

## Leakage, source safety and privacy

- Ban Lightroom Develop previews/Previews.lrdata/Smart Previews, exported edited JPEG, XMP, .lrcat Develop and Adobe .acr as model INPUT. Use them only to determine targets or evaluate after input extraction.
- Source RAW must not be altered; no metadata writes, image modification or photo uploads to GitHub. Feature caches only in explicit local private folders and tied to hash + decode version; purge policy needed. Client archives/capture times/path/camera serials are not shared.
- Avoid learning session-specific final exposure from photographic duplicates split between train/test. Split by confirmed whole event (including event-day bursts; photographer grouped scene families where applicable), preserve locked test, log exclusions without filenames.
- Mask-local edits can contaminate global-only targets; set a coverage policy before trying to reconstruct Lightroom result. Even accurate global parameters are NOT pixel/render parity.
- Consent and permission for private analysis/training must be confirmed for each photographer/event; never assume ownership is permission.

## Evaluation plan before model

Baselines (same events/targets/cases): (A) photographer median/no-change or nearest simple recipe, (B) EXIF/camera-only contextual predictor, (C) EXIF + neutral-original image features. Per-parameter error, calibrated scene classification, unsupported-case/abstention coverage, and scene-stratified differences are research metrics. Final product metrics are photographer accept-without-correction and actual active time, without universal aesthetics.

Pre-register split, train-only normalization, target support, coverage, thresholds, scene mix and stop rule **before** experiment. Do not copy historical JPEG G1–G4 numerical targets to RAW without formal workflow amendment. Evaluate stronger/complex vision modules only if B/C gains are convincingly measurable on held-out events.

## Immediate safe next action

1. Finish 01F.01 v0 contract with synthetic cases and precise input-leak rejection tests; it needs no private RAW files or Brain training.
2. Request a small **permissioned** multi-scene set of matching original RAWs (daylight/outdoors, indoor hall, strongly colored/mixed artificial lights) from more than one real event, together with existing Lightroom catalog and confirmation that edits are final. A handful supports feature sanity checks; it is NOT a training-quality dataset.
3. Later validate feature extraction locally on copies, fingerprint raw sources, and share only aggregate coverage/errors.

Current evidence: a single Adobe-validated example agrees on 48 field/curve expressions; thousands of catalog rows alone are NOT ground truth raw+recipe pairs. G0 unsigned, G1 unratified and training ready: 0.
