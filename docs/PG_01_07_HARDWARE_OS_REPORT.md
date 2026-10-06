# PG-01.07 — Hardware / OS Support Matrix Report

Date: **2026-10-06**  
Status: **◐ PREPARED / G0 + PLATFORM MEASUREMENT PENDING**

## Deliverables

- `docs/TARGET_SYSTEM_MATRIX.md` rebuilt as the Release 1 candidate support matrix.
- D-014 added to `docs/DECISIONS.md` for the separate Intel Mac boundary.
- Master/Project State/Execution Board aligned to PG-01.07 as the active
  pre-G0 preparation lane.

## Decisions prepared

- Windows x64 and macOS Apple Silicon remain mandatory Release 1 targets.
- Intel Mac is evaluation-only and does not block Release 1.
- Candidate commercial floor starts at 16 GB RAM + SSD-class storage.
- 32 GB is the recommended professional planning tier.
- No discrete GPU, CUDA or MPS requirement is frozen before a production Brain
  candidate is measured.
- OS support is tied to vendor-supported releases rather than a permanently
  hard-coded patch version.
- External SSD is a planned supported workflow but still requires the deferred
  disconnect/reconnect + Relink evidence.
- NAS/network/cloud-synced live Event roots remain unverified.

## New Windows evidence recorded

The current Windows local-verification session provides stronger evidence than
the old Phase-0 matrix:

- 118 backend tests passed,
- 27 focused JPEG renderer/product/control tests passed after optimization,
- ESLint, TypeScript and Next production build passed,
- Rust/Tauri check and actual desktop launch passed,
- local engine autostart passed,
- real JPEG + MPO-backed JPG + RAW manual paths were exercised.

This remains one-machine engineering evidence. Hardware specs, 2,000-photo
performance, external-drive recovery and clean second-machine installer testing
are still missing.

## Why PG-01.07 is not V

Phase 01 formally enters after G0, which remains unsigned.

In addition, the Master explicitly states that numeric minimum requirements stay
candidate values until measured. Apple Silicon has no real execution evidence
yet.

Therefore the correct status is **◐**, not V.

## Next dependency

Once this prepared contract is accepted after G0, Phase 02 has an exact platform
test matrix instead of an undefined "test on Mac" task.
