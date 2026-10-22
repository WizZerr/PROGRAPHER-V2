# PG-BS-01 — A/B Brain Studio workflow (research-only)

**Source:** main at 712b552 (2026-10-12). **Branch:** feature/pg-brain-studio-ab-workflow.  
**Status:** Draft, requires Windows/Tauri smoke + TypeScript build. No AI training or batch Lightroom capability is claimed.

## Why this first slice exists

The user wants: **RAW + verified edited Lightroom targets from folder A → photographer-specific saved Brain → RAW folder B → per-image recipe → Lightroom application → review and iteration**, all from the Hebrew desktop UI. No ZIP/CLI as the user's routine workflow.

Existing main already has profile/training screens, local event scanning, a RAW+XMP testing profile with a train median of Exposure/Temperature/Tint, a per-event review API and an LB-01 one-RAW Lightroom research adapter.

**Important:** choosing LRCAT in the existing UI currently stores a path, *not* training samples. Choosing RAW+XMP builds a *median baseline*, not an AI profile. The research AUTO-D code is not integrated into the product and is not a persistable, generic folder-to-folder model.

## What this PR changes

- Adds **מעבדת Brain** as a navigable workspace screen.
- Lets the user choose local training RAW folder A and matching final XMP folder, then computes a clearly labeled baseline via the existing /api/testing/profile route.
- Lets the user choose local test RAW folder B; rejects identical or nested folder paths; ingests via existing non-destructive event scanner.
- Displays per-photo baseline suggestions from the existing review API. If B includes matching true edits, shows MAE for Exposure in stops, Temperature in K and Tint. Never calls this AUTO-D quality.
- Uses existing secret-bearing desktop API client; sends no user photos or private manifests to GitHub.
- Makes no renderer changes and offers no misleading Lightroom batch apply button.

**Constraints:** folder-path separation does not prove image separation. There is not yet a source hash overlap check; copied photos may invalidate evaluation. The existing raw testing profile is replaced by the new baseline; this workflow does not yet implement versioned experiment retention. Not to be deployed as commercial functionality.

## Windows developer smoke (required before merge)

1. Keep original RAW and Lightroom catalog backed up, and only use local authorized research copies.
2. Run backend and frontend using repository README instructions; verify existing events/profile screens still work.
3. Navigate to **מעבדת Brain**; choose RAW-A + matching final XMP folder. Click **בדוק זוגות וצור Baseline**.
4. Verify profile count is plausible; inspect warnings for missing targets/local adjustments and absence of quality claims.
5. Choose separate RAW-B and click **הפק תחזיות Baseline**. Check event scan progress, RAW count, 30-row preview and no source mutation.
6. With matching B-side XMP, verify MAEs match independently calculated values; without XMP verify *no accuracy claim*.
7. Reject same/parent/child paths. Verify no RAW, XMP, LRCAT, filename inventory or per-photo manifest reaches GitHub.
8. Run `cd frontend && npm ci && npm run lint && npm run build` and backend regression tests. Hosted CI may remain quota-blocked; record a verifiable local result.

## Immediate next Parts (do not call them already implemented)

**PG-BS-02 — Durable profiles + verified train/test provenance:** versioned model/experiment artifacts, consent/finality, per-file source fingerprints, event-level disjointness, no overwriting prior Brain candidates. Store artifacts only in user data directory.

**PG-BS-03 — Real AUTO-D adapter:** generalize the historic D experiment to arbitrary RAW+verified targets, implement identical source-only features on A and B, keep trained preprocessing/feature schema and weights with hashes, and demonstrate same- and cross-event evaluation versus median baseline. Do not directly depend on original private inventory CSV, research-only feature CSV or a fixed photo event/shooter name. Resolve target units and Lightroom rendering-context semantics. No train/test leakage.

**PG-BS-04 — Lightroom apply:** adapt LB-02 authenticated queue to take versioned per-image Adobe recipe jobs; prove 10→100 idempotent apply/readback/export on test copies, with isolation and recovery. No direct write into a live .lrcat.

**PG-BS-05 — Photographer study:** capture review edits, whole-event holdout, side-by-side reference renders, MAE and amount of active photographer time saved. Keep old candidates and their frozen benchmarks; no promotion without passing gate.

## Status and accuracy

- **PG-BS-01 UI + existing services: authored on feature branch, NOT build/run verified.**
- **A→B baseline suggestions:** implementation is assembled, not user-tested.
- **A→B learned model and Lightroom batch editing:** NOT implemented.
- **AUTO-D from October research:** external research candidate, not the active product model.
- **Repository main:** unchanged until reviewed merge.
