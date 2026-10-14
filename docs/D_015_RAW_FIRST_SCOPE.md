# D-015 — RAW-first learning scope / JPEG freeze

> **Historical learning input superseded by [D-022](D_022_HISTORICAL_SMART_PREVIEWS_CONTRACT.md), 2026-10-14.** Historical learning now requires Lightroom Catalog + Smart Previews, NOT original historical RAW. The original text below is preserved for research provenance only; its §§Decision 1 and 4 RAW-byte requirements no longer govern historical intake. New-event RAW, no data leakage, consent/finality/event holdouts, source safety and JPEG freeze remain in force.

**Date:** 2026-10-11
**Status:** Product-owner approved direction; implementation and quality gates NOT approved/passed.
**Authority:** docs/MASTER_PLAN_SOURCE_OF_TRUTH.md
**Supersedes:** JPEG-first Release 1 scope in Workflow v3.0 and PG-01.01 draft (scope only; preserves historical engineering evidence).

## Decision
1. **Active learning pathway:** original camera RAW (including CR3) + exported Lightroom Classic .lrcat Develop metadata. XMP is a supported interoperability/validation fallback. Do not require before/after or final JPEG files as training input.
2. **Initial inference/output boundary:** source RAW features -> per-photographer predicted Lightroom editing recipe -> separate, source-safe XMP -> Lightroom renders/exports final JPEG. Do not promise independent Adobe-equivalent RAW rendering.
3. **JPEG learning/rendering development is PAUSED.** Preserve all previous JPEG code, tests, artifacts, findings and historical Part statuses; only regressions, maintenance and safety fixes can proceed while paused.
4. **Do not train on catalog rows alone.** .lrcat settings need source RAW identity/bytes, finality/consent validation and event-level Train/Validation/locked Test segregation before G1/G2/G3. Catalog may include unrelated personal/food photos; do not infer event membership from nonzero sliders, filenames, folders or dates alone. Maintain explicit human-confirmed event labels and quarantine ambiguous rows. Approved No-Edit records are valid, subject to evidence.
5. **Develop coverage is not Basic-only.** Track profile, ProcessVersion, WB, B&W, tone curves, HSL/Color Mixer, color grading, geometry, masks, AI/local retouch and unavailable .lrcat-data adjuncts. Expose partial/unsupported flags rather than pretending full equivalence. Preset/Auto/Sync history are optional evidence, not required targets or trustworthy current edit origins.
6. **Dataset recommendation, not a hard eligibility gate:** target multiple diverse, photographer-approved events; ~2,000 RAW samples is a planning hypothesis, not a statistical guarantee. Prefer separate whole events for training, validation and locked testing; one wedding supports only an engineering pilot.
7. **No personal photographer assets in GitHub.** Keep private catalogs, previews, .lrcat-data, image names/paths and per-photo manifests locally. Use synthetic/public licensed fixtures in repo; reports shared only as authorized aggregate data.

## Execution lane / boundaries
- **RAW-CAT-01D — backend foundation (RESEARCH / ENGINEERING PREP).** Build a read-only, versioned catalog extractor that rejects ambiguous/missing records, produces an aggregate privacy-safe report and local private RAW edit manifest with training_eligible=false; add synthetic regression tests. Does not connect the production app/Brain or claim semantic parity with Adobe.
- **RAW-CAT-01E — Lightroom/XMP equivalence & coverage.** Verify samples with source and verified current Develop settings, parse actual curve/control structures and capture meaningful unsupported settings; test safe cross-version schema changes.
- **PG-06.02–PG-06.07 — real photographer intake/G1.** After authorized RAW arrives, match originals to catalog, confirm event/finality/provenance, split whole events and only then evaluate targets. Do not claim G1 or model quality from aggregate reports.
- **Existing PG-00.05 / PG-00.02 / G0 remain open.** Isolated pre-G0 research/fixtures are allowed; production integration and formal Part validation remain gated. Keep Cloud/Auth and production Brain blocked until their gates.

## Acceptance for RAW-CAT-01D research
- Read-only SQLite exported-copy access; never mutate Lightroom DB, accompanying files or camera originals.
- Fail closed for unsupported schema, missing/duplicated develop relation, non-finite values and ambiguous linkage.
- Process real .lrcat with no CSV/JSON file paths in shareable report. Private mapping is separate and opt-in.
- Preserve source identity, Develop field provenance and unsupported-field visibility; explicitly record zero training-ready samples.
- Synthetic/public fixtures and isolated tests pass, with results bounded to engineering (NOT Lightroom parity or quality).
