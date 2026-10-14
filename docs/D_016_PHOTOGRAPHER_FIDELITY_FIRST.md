# D-016 — Photographer Style Fidelity First

> **D-022 historical-source amendment (2026-10-14):** historical learning uses Catalog + Smart Previews, with strictly validated source-neutral input features; historical original RAW is not required. RAW-source statements below describe earlier research and remain valid for new-event inference and original-RAW experiments. No historical Smart Preview input is trainable merely because it renders after Reset.

Date: 2026-10-11
Status: Product-owner direction confirmed in conversation. Research plan only; no training or quality gates approved.
Authority: docs/MASTER_PLAN_SOURCE_OF_TRUTH.md
Works with: D-015 RAW-first scope. Does not unfreeze JPEG or override G0–G6.

## Product promise

**הצלם נשאר האמן. ProGrapher לומדת להיות העוזרת שלו.**

ProGrapher learns to edit **as the individual photographer would**, for the actual source photo, its scene and event context, so the photographer can deliver more events with less manual editing time. The software must not deliberately replace the photographer's style with a generalized idea of prettier photographs.

## Model decision policy

- Photographer-approved final decisions/recipes are the supervised target, not a model-defined beauty score.
- Unedited source RAW + camera/sensor metadata + scene/event context actually available at inference are model inputs. Lightroom edited previews, Develop adjustments, XMP or post-edit outputs are targets/validation evidence **only**, and may NEVER leak into input visual features.
- Understand the original scene to predict what *this photographer* would do: daylight/outdoors, dim hall, mixed-color LED/stage lights, portrait/candid/dancing, subject/backdrop relationship, exposure/contrast/color issues and relevant camera conditions. Scene labels are hypotheses with confidence and an explicit UNKNOWN state, not objective truth.
- Global and local edits are distinct. Masking automation is **not** a Release 1 prerequisite. Preserve/categorize images with local edits to avoid training an impossible global-only target; consider human review or abstention for unsupported local requirements.
- Respect deliberate unconventional grading, moody shadows, colored dancefloor lighting, texture and no-change decisions. Do not automatically neutralize stylistic lighting or make all images match one generic aesthetic.
- When confidence or support is inadequate, flag review / no-op. Never make confident destructive style changes on uncertain images.
- Use corrections explicitly approved by the photographer as feedback for later versioned learning. Never automatically learn from unreviewed AI output.
- Preserve source RAW bytes and photographer privacy; no upload of whole events by default; training is gated on data permissions/finality and event-separated evaluation.

## What counts as success

Primary product outcome: **photographer accepts the proposed edit without changing it**, across previously unseen events. Secondary measures: perceived style fidelity assessed by the photographer, active editing time saved (including review/fixes), serious failures, and consistency across scene types. Offline per-parameter error is diagnostic rather than a substitute for photographer acceptance. No universal beauty metric is a release criterion.

## Scope and gate impact

This refines D-015's RAW recipe prediction goal: prioritize scene-aware **global** edits and measured fidelity, with honest masking limitations. Adds pre-G0 **RAW-CAT-01F — Visual Context Research**, to define/test input-only image features before a Brain. Previous mask-structure line RAW-CAT-01E.03C.02 is preserved but **PAUSED** and may return if a coverage experiment demonstrates it is a blocker. None of the current 48 one-photo Adobe XMP matches proves visual-context accuracy or model quality.

G0 remains UNSIGNED; PG-00.05 open, photographer approved final RAW/catalog pairs insufficient for G1; G1–G4 RAW-specific contracts/evaluation require explicit update/ratification before model training. Do not start production Brain, Auth/Cloud or claim G2/G3/G4 passed. All historic code/evidence remain intact.

## Anti-goals

No autonomous artistic re-styling, no personalized photographer identity recognition, no biometric/demographic labels, no post-edited preview-as-original, no model trained on catalog targets without matching original RAW and event-level holdout, no silent defaults for missing/opaque fields, no new service promises or weights trained from one RAW example.
