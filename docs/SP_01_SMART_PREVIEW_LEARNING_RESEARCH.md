# SP-01 — Catalog + Smart Preview Learning Research

**2026-10-13 | Status: SP-01.01 research implementation committed; synthetic tests and real Lightroom SDK run PENDING | ProGrapher Master v4.0 (Lightroom-First).**

## Goal and scope

Enable a photographer to select an authorized Lightroom Classic catalog plus Smart Previews, without requiring retention/transfer of historical original RAWs for the initial visual learning pathway. Use a neutral, source-equivalent image representation as model **input** and photographer-approved original Develop instructions as **target**. Keep this research separate from PG-04.LB01 (strictly one authorized CR3/copy) and PG-04.LB02 (autonomous bridge IPC).

No customer-facing automation, AI accuracy, model training or catalog-only production support is claimed here.

## Local user-observed proof (PRIVATE, not reproduced in repo)

- Research catalog `SP_01_SMART_ONLY` was exported with Smart Previews, without exporting original negative files.
- A separate one-photo catalog `SP_01_OFFLINE_PROOF` was created. Only the exported *copy* of the RAW folder was temporarily renamed to make that source unavailable.
- Lightroom Classic histogram displayed `Smart Preview` without `Original`.
- User created a Virtual Copy, used Develop Reset and successfully exported a neutral-baseline JPEG from the unavailable-original workflow.
- The export is **not** verified pixel-equivalent to the original RAW, not verified independent of original photographer Develop settings across repeated resets, and no catalog-target extraction or pairing was proven by this JPEG alone.
- Original shooter RAWs and working catalog must never be modified to repeat the test. Original photographer Develop state remains distinct from neutral copy state. User evidence stays local; photo assets, paths, catalog/database, manifests and personal metadata must not be uploaded to GitHub.

## SP-01.01: first engineering Part — input/target contract, single-image safety proof

**Input (research only):**
- User-authorized *copy* of a Lightroom catalog and its matching Smart Preview store; one selected photo at a time.
- Catalog/photo/virtual-copy identity must be unambiguous; never infer identity from filenames alone.
- Private on-device original Develop snapshot BEFORE any neutralizing operation, including profile/process version, supported global recipe, WB, crop/rotation and explicit unsupported local edits/masks.
- Source visual artifact: Lightroom's own **Smart Preview**, with original RAW demonstrably unavailable in isolated test. Do not parse or mutate the .lrcat SQLite file directly while Lightroom is using it.

**Safe neutral processing:**
- Do NOT reuse or loosen the allowlists in `backend/app/lightroom_bridge/lb01_poc.py` and the existing LB01 plugin.
- Discover and prove supported Lightroom SDK operations in a *separate research adapter*; do not assume an SDK-supported Virtual Copy/Reset API or automate mouse/UI clicks in a customer catalog.
- Any neutral operation acts only on a disposable test catalog/copy and disposable working copy. If no supported SDK solution is proven, preserve the existing manual POC and mark automation BLOCKED.
- Define and version neutral baseline policy explicitly: process version, camera profile, WB handling, tone/curve, orientation, crop state, output dimensions, color space and JPEG encode version. **Develop Reset is not equivalent to original RAW bytes or zero processing.**
- Save neutral JPEG in private, pre-approved, isolated output directory; never overwrite or alter original source, existing XMP, original Develop or user's exports.

**Pair contract (future schema):**
- `asset_ref`: opaque, unique validated catalog image/virtual-copy identity, never just a stem.
- `neutral_input`: path/hash/dimensions, representation version and neutral renderer policy, proof of Smart Preview-only source.
- `photographer_target`: independently captured, approved final AdobeDevelopRecipe, crop policy and unsupported flags.
- `qa`: identity, original target snapshot/restore check, source separation, neutral repeatability, privacy and reason for exclusion.
- Training eligibility remains **false** until photographer consent/finality, whole-event membership, exact identity, leakage audit and G1 are independently verified.

**Source-only anti-leak test:** change photographer Develop in a disposable catalog copy without changing the Smart Preview, regenerate neutral input with identical neutral policy; normalized pixel output must be consistent within predeclared encode tolerance. Compare neutral images and include a negative test that accidentally exported **edited** preview is detected, or fail closed when not detectable. Do not use Lightroom's standard edited Preview as source input.

## Implemented in SP-01 feature branch (NOT YET VERIFIED ON USER PC)

- `backend/app/photographer/smart_preview_analysis.py`: fail-closed, source-only reader for a **previously exported neutral JPEG**; correct sRGB-to-linearized-display metrics; optional reuse of the existing local CLIP scene predictor; research outputs remain private, with an identity-free aggregate and no photographer target in model inputs. Does **not** claim the neutral JPEG was proven independent of Develop.
- `backend/tests/test_sp01_smart_preview_analysis.py`: synthetic test suite for pixels, deterministic analysis, file immutability, no overwrite, privacy, research-root restrictions, scene unknown/abstention and static Lua research safety; Windows test proof pending.
- `integrations/lightroom_classic/sp01/ProGrapherSmartPreviewResearch.lrdevplugin/`: research-only, one-photo exporter guarded to exact `SP_01_OFFLINE_PROOF.lrcat`. Reads master Develop separately and exports an already reset selected Virtual Copy only when physical RAW is offline. Does not perform Reset/create VC and is **not yet Lightroom-run**.
- `integrations/lightroom_classic/sp01/README_HE.md`: Windows detached worktree tests and safe single-JPEG smoke instructions.
- Note: published Lightroom SDK references `LrCatalog:createVirtualCopies()` and `LrDevelopController.resetAllDevelopAdjustments()`, but version-specific runtime behavior, reset defaults and safe headless operation are not proven; do not assume they solve product-scale automation. Adobe Reset uses configured defaults, not RAW byte reconstruction.

**No code has been merged into main; the Windows test and SDK runtime evidence must precede any status promotion.**

## Next execution order

1. **SP-01.01** (THIS PART): scope/contract and synthetic security/regression tests; verify one-image neutral input + original recipe provenance is possible using *documented* supported SDK operations on the research copy.
2. **SP-01.02**: implement safe catalog/Smart Preview adapter when SDK feasibility is established; signed-off, bounded 1-photo proof and 3-photo smoke, no customer catalog mutation.
3. **SP-01.03**: add neutral-JPEG analysis adapter (correct sRGB decoding; NEVER silently treat 8-bit JPEG as original linear RAW features) and run local CLIP scene suggestions with explicit UNKNOWN/human review.
4. **SP-01.04**: test repeatability, source-only leakage, crop and camera/process coverage across multiple authorized photos/events; collect approved examples and human evaluations before model training.
5. Larger autonomous orchestration belongs to PG-04.LB02 + PG-05; G0 still OPEN; G1–G6 NOT PASSED.

## Definition of Done for SP-01.01

- Contract reviewed, boundaries to Lightroom SDK and private files explicit.
- Synthetic tests exercise no-overwrite, source-type separation, unique identity, recipe provenance, neutral policy versioning, leakage/repeatability rules and failure/abstention paths.
- One isolated copied-catalog Smart Preview-only record can be transformed into a **private** paired neutral-input + original-target manifest without modifying source or target.
- Real SDK automation can remain BLOCKED if unsupported; must not claim PASS based solely on the previous manual export.

Current claim: **manual Smart Preview-only neutral export PASS on one research image; automatic source-only learning pipeline NOT PROVEN**.

## SP-01.03 — Provenance and precision contract (2026-10-13)

**What we can measure** from a Lightroom-exported neutral Smart Preview JPEG: decoded pixel dimensions, source digest, display-referred sRGB luminance/chromatic statistics after explicitly recorded sRGB transfer, sampled clipping proxies, and an uncalibrated, human-reviewable complete rank across the fixed eight CLIP scene prompts. These are **measurements of the rendered neutral JPEG**; JPEG compression and Lightroom defaults still influence them. Camera EXIF or catalog capture metadata such as ISO, shutter, aperture and focal length, if available, belongs to a separately provenance-verified *capture-metadata* channel, not derived from JPEG tone and never confused with Develop values.

**What we cannot honestly recover from Smart Preview alone:** the sensor's original linear pixel values, uncompressed color, physical sensor clipping and noise, accurate sensor dynamic range, or guaranteed neutral independent of the photographer's prior Develop/Camera Default. Reset does not prove source-equivalence. Master Develop, crop/rotation, masks, profile, process version and photographer approval remain target metadata, **never** a source model input.

**Human-confirmed scene for the first private image:** photographer identified `PORTRAIT` (staged couple portrait before the ceremony), while CLIP raw top-1 was `CEREMONY` (relative 0.256, margin 0.0716), with final `UNKNOWN`. One semantic top-1 error; safe abstention worked. Do not tune on this single photo.

**Additive implementation:** `backend/app/photographer/smart_preview_ranked_scene.py` records all eight fixed-prompt scores, top-3, prompt-set SHA-256, version, library versions, explicitly slow CLIP preprocessing, and optional ground-truth evaluation AFTER inference. Existing RAW analysis and model weights remain unchanged. `--scene-diagnostics --human-scene PORTRAIT` is strictly opt-in; no data is training-ready. Runbook in `integrations/lightroom_classic/sp01/README_HE.md`.

**Validation gate:** locally execute synthetic ranking/privacy tests, then private JPEG top-3 test; collect a small representative labeled sample across distinct sessions and lighting before prompt experimentation. Independent no-leak, target identity and reset consistency gates remain OPEN.

## SP-01.04 — second-neutral-export repeatability (candidate gate, not anti-leakage proof)

After one-image zero-shot diagnostics, before expanding input features or training, test **repeatability of the same Reset Virtual Copy** while the copied RAW remains offline. Lightroom must still show `Smart Preview` alone; export the same copy again to a NEW private directory using identical full-size sRGB JPEG settings (quality, profile, no sharpening/watermark, geometry, metadata policy). Do not modify the photographer's master. Never run this experiment in a live customer catalog.

`backend/app/photographer/smart_preview_repeatability.py` checks two distinct local JPEGs with strict full decoded RGB pixel equality, byte hashes (not published), geometry, MAE, p95 delta, and equality fraction. It refuses to overwrite outputs and writes only a source-identity-free aggregate into private research. **Two matching JPEGs do NOT prove independent exports, uncropped source geometry, or independence from photographer Develop.** A separate leakage intervention on a disposable catalog copy and exact master↔copy provenance check remain required. Model training eligibility remains false.

Synthetic tests: `backend/tests/test_sp01_smart_preview_repeatability.py`. Real Windows/Lightroom proof pending. Existing 22 passed/1 symlink-permission skip applies to earlier diagnostics, not this new module.
