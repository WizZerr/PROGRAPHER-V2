# D-022 — Historical Catalog + Smart Previews; new-event RAW (2026-10-14)

**Status:** Product-owner approved INPUT CONTRACT. Implementation, source-neutrality and validation gates remain OPEN.  
**Authority:** `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`; Stage 1 tracking: GitHub Issue #9.  
**Supersedes:** `docs/D_015_RAW_FIRST_SCOPE.md` §Decision 1 and the requirement for historical original RAW bytes in §Decision 4, **historical training only**. Also narrows source-RAW statements in `docs/D_016_PHOTOGRAPHER_FIDELITY_FIRST.md` and corresponding old plan sections. Preserves all other safety, scientific validity and scope constraints.

## Contract
- **Historical learning intake (Stage 1):** photographer selects a licensed Lightroom Classic **`.lrcat` and matching `Smart Previews.lrdata`**. Historical original camera RAW files MUST NOT be required in the active learning UI, API or data contract. `Previews.lrdata` (ordinary JPEG cache) is NOT a replacement for Smart Previews.
- **Historical learning analysis (Stage 2):** Lightroom final Develop state is an *output target*; source visual features must NOT contain those targets or edited pixels. Smart Previews may already contain historic edits. Simply resetting Develop or matching two reset renders does NOT establish source independence. **No model training or valid input/target pair claims before source-neutrality, identity/finality, consent and whole-event separation pass their gates.** If this cannot be proven, investigate an alternative that preserves the product requirement, and report the blocker instead of silently requesting historical RAW.
- **New event editing (Stage 5):** original RAW files ARE the required event input, analyzed with the approved personal Brain and rendered/exported through licensed Lightroom Classic. Source RAW safety and Bridge requirements stay unchanged.
- **Photographer fidelity:** model must learn the photographer's decisions, not generic enhancement; No-Edit/abstain and unsupported edit families remain explicit.
- **Windows first:** Stage Parts are approved only after all supported Windows acceptance tests and real E2E evidence; macOS Apple Silicon certification is a distinct final gate after Windows core acceptance. A Windows VERIFIED label does not imply macOS certification.

## Boundary and fail-closed behavior
- Stage 1 validates selection, storage, accessibility, versioned inventory, provenance and catalog/Smart Preview associations **where actually proven**. Ambiguous/unlinked records are quarantined. Presence of a directory never by itself establishes correct photo identity or training readiness.
- Stage 2 validates Develop interpretation, source-safe visual inputs, target provenance, event finality and train/validation/test grouping. Historical Smart Preview neutrality is Stage 2, NOT a Stage 1 completion check.
- No guessed UUID, basename, Lightroom internal schema or file-extension equivalence may be promoted to identity proof without a controlled genuine Lightroom fixture and versioned test.
- Never mutate photographer originals or live Lightroom Catalog. Prefer closed/exported immutable snapshots; WAL/SHM and active Lightroom states must be fail-closed until safe snapshot policy is proven.
- No photographer-specific RAW, catalogs, previews, .lrcat-data, image filenames, per-photo manifests, Develop values or customer identifiers in GitHub. Commit only synthetic fixtures and anonymized aggregate proofs.
- **No Stage 1 DONE claim** on this document alone, no change to G0/G1/B0/B1/G2–G6, and preserve all past research and candidate history.

## Required follow-through
1. Align active Master/Board/State/UX code with this input contract; preserve historical decisions as archived evidence.
2. Replace historical `RAW+Catalog` form with `Catalog+Smart Previews`, persisted in backend SQLite and explicitly labeled “selected / inventory-only / unverified”, not “training-ready”.
3. Validate real version-specific Smart Preview storage/linkage using a consented, disposable Lightroom fixture. Do not substitute regular `Previews.lrdata`.
4. Add privacy, corruption, restart, relink, unsupported-version and negative-path tests; run full UI E2E on Windows with genuine materials before accepting Stage 1.
5. Defer macOS certification until Windows core completes, then prove separate cross-platform gate.
