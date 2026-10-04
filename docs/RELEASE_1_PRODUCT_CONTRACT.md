# ProGrapher V2 — Release 1 Product Contract

Version: **0.1 DRAFT**  
Prepared: 2026-10-04  
Workflow Part: **PG-01.01**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

> This document is the product-scope contract for Release 1. It is intentionally a **draft** until G0 is signed. Preparing the draft is allowed while PG-00.02 is still being closed. No item in this document becomes a market claim merely because it is written here.

## 1. Product promise

ProGrapher Release 1 is a professional desktop AI editing product for event photographers.

The primary commercial path is:

**Select original JPEG event → apply photographer profile locally → review/correct → export final JPEG locally**

The editing path must not modify source files.

The product is Hebrew-first / RTL and targets:

- Windows x64
- macOS Apple Silicon

Release 1 is designed for one photographer per account, with one or more personal profiles and use on authorized devices.

Multi-editor studio collaboration is outside Release 1.

## 2. Sellable Release 1 capabilities

A capability may be marketed only after the Gate named in the last column has passed with evidence.

| Capability | Release 1 commitment | Required evidence before market claim |
|---|---|---|
| Independent JPEG workflow | Original/edited learning material, local inference, review/correction and final local JPEG export | G1 data validity → G2 representation → G3 prediction → G4 local value |
| Photographer-specific profile | Versioned personal profile used by local inference | G3 candidate quality + later profile lifecycle evidence |
| Local event editing | Inference, render, review, export and jobs run on the photographer's computer | G4 |
| Source-file safety | Original RAW/JPEG files are not modified by normal editing/export flows | G0 regression baseline + continued regression coverage |
| RAW-assisted workflow | Existing safe RAW intake/preview/review/XMP bridge is preserved | Compatibility evidence for the supported RAW/XMP path |
| Profile backup/sync | Supported profile/settings backup or sync through commercial cloud control plane | G5 |
| Account + entitlement | User identity, authorized devices and subscription eligibility | G5 |
| Signed installation + updates | Installable commercial desktop package with controlled update path | G5 |
| Commercial Release 1 | Product can be sold only within the measured scope | G6 |

No percentage of quality, acceptance, automation or time saving may be advertised until the relevant evaluation has measured it on real unseen photographer events.

## 3. JPEG contract

JPEG is the **primary independent editing path** for Release 1.

Release 1 intends to support:

- original JPEG intake,
- edited-reference intake for profile learning,
- validated original↔edited pairing,
- local photographer-specific inference,
- deterministic/versioned preprocessing and rendering,
- review and manual correction,
- resumable event work,
- final local JPEG export,
- source-file preservation.

The initial edit representation is limited to the color/tone capability that passes J0/G2.

If the representation cannot reproduce enough of the photographer's real edits to meet the product-value gate, the representation must be expanded **before Release 1** or the commercial scope must be explicitly reduced and versioned.

JPEG inference for a new event must use only source-side information. An edited target is training/evaluation material, not an inference-time dependency.

## 4. RAW contract

RAW is a **supported assisted path**, not the primary independent AI editor in Release 1.

Release 1 preserves the safe capabilities already established around:

- RAW event intake,
- supported embedded/camera preview,
- review flow,
- Exposure / Temperature / Tint recipe handling where available,
- safe XMP export,
- refusal to overwrite photographer-owned XMP,
- source RAW preservation.

Release 1 does **not** promise:

- an independent Adobe-equivalent RAW development engine,
- exact Lightroom rendering inside ProGrapher,
- high-quality per-image RAW AI beyond what is explicitly measured,
- replacing Lightroom for the supported RAW-assisted path.

Any future independent RAW product claim requires a new scoped decision and its own evaluation evidence.

## 5. Profile contract

A photographer profile is a versioned product artifact, not a folder name and not the photographer identity itself.

Release 1 requires profiles to eventually contain enough information to reproduce the exact inference contract, including the applicable versions of:

- model/weights,
- feature/preprocess pipeline,
- normalization,
- recipe representation,
- renderer,
- compatibility metadata,
- evaluation metrics,
- hashes/checksums.

JPEG and RAW learning remain separate.

A JPEG profile must not pretend to contain Lightroom slider values inferred from RGB unless such values are part of an explicitly validated representation.

A RAW profile and a JPEG profile are not interchangeable merely because they belong to the same photographer.

## 6. Local / cloud boundary

### Local — mandatory

These operations run on the photographer's computer:

- access to event source files,
- event indexing,
- inference,
- rendering,
- review,
- correction state,
- export,
- local job execution,
- local cache.

### Cloud — commercial control plane

Cloud scope may include:

- account identity,
- entitlement/subscription state,
- authorized-device state,
- profile/settings registry and backup/sync,
- selected learning data,
- managed training,
- candidate/profile delivery.

### Explicit cloud exclusions

Release 1 does not automatically upload every event.

Profile sync is not marketed as full photo backup.

Moving to another computer does not magically restore source events that were never uploaded.

Live collaborative editing of the same event across devices is outside Release 1.

## 7. Learning and consent boundary

Photographer-approved results may become valid personal-learning examples according to the later data contract.

Release 1 must distinguish:

- local source photos,
- local derived/cache data,
- selected learning material,
- processed learning features/targets,
- profile artifacts,
- account metadata.

Use of a photographer's material for broader/global learning requires separate explicit consent and is not implied by use of the product.

## 8. Reliability contract

Release 1 must uphold the following product truths:

- source files are protected,
- a failed or partial run is not labeled complete,
- interrupted local work can be resumed according to the implemented recovery contract,
- incompatible profile/app/data versions fail clearly rather than partially loading,
- ambiguous learning pairs are excluded rather than guessed,
- unsupported capability is shown as unsupported, not silently approximated as a market claim.

Critical corruption, data-loss or unsafe-overwrite defects block the relevant Gate.

## 9. Explicitly outside Release 1 mandatory scope

The following are **Backlog unless a new versioned scope decision promotes them**:

- full independent RAW engine,
- cloud rendering for every photo,
- live same-event multi-device editing,
- photographer-client delivery galleries,
- studio/team management,
- video editing,
- generative content replacement,
- advanced retouching,
- full Lightroom plugin,
- multi-editor collaboration,
- unmeasured "100% automation" claims.

These items remain part of the wider product vision but are not required to ship Release 1.

## 10. OS support contract

Release 1 requires evidence for:

- Windows x64
- macOS Apple Silicon

Intel Mac support is a separate compatibility decision. It is not implied by Apple Silicon support.

A platform is not marked supported merely because the code compiles for another platform.

## 11. Scope-change rule

After this contract is ratified:

1. adding a major Release 1 capability,
2. removing a committed capability,
3. changing JPEG vs RAW responsibility,
4. changing local vs cloud responsibility,
5. changing supported OS targets,
6. expanding the meaning of a commercial quality claim,

requires a **versioned product-scope decision** in `docs/DECISIONS.md`.

No Part may silently widen the product.

## 12. Gate alignment

| Gate | What this contract allows after PASS |
|---|---|
| G0 | Begin the new implementation sequence from a trusted baseline |
| G1 | Treat selected data as valid training/evaluation material |
| G2 | Claim that the chosen edit representation is sufficient for the measured scope |
| G3 | Integrate a measured predictive candidate into internal alpha |
| G4 | Commit to building the commercial wrapper because local product value is evidenced |
| G5 | Deliver a self-service external beta with identity/entitlement/recovery/update controls |
| G6 | Market and sell only the Release 1 scope that the evidence supports |

## 13. Ratification checklist

PG-01.01 may move from DRAFT/◐ to V only when:

- [ ] G0 is signed.
- [ ] Product owner explicitly accepts the Release 1 scope.
- [ ] JPEG independent / RAW assisted split remains accepted.
- [ ] Windows x64 + Apple Silicon remain mandatory Release 1 targets.
- [ ] Local/cloud boundary remains accepted.
- [ ] Explicit exclusions remain understood.
- [ ] Sellable capabilities map to Gates without unsupported claims.
- [ ] Any change after acceptance is recorded as a versioned scope decision.

Until then, this file is the working draft and cannot be used to claim PG-01.01 complete.
