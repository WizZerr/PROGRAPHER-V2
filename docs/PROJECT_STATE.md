# ProGrapher V2 — Project State v4.0

**Updated:** 2026-10-12  
**Single source of truth:** [MASTER_PLAN_SOURCE_OF_TRUTH.md](MASTER_PLAN_SOURCE_OF_TRUTH.md) v4.0.  
**Execution board:** [EXECUTION_BOARD.md](EXECUTION_BOARD.md).  
**Previous detailed snapshot:** [archive/PROJECT_STATE_v3.1_2026-10-12.md](archive/PROJECT_STATE_v3.1_2026-10-12.md).

## Repository and adoption
- Repository: `WizZerr/PROGRAPHER-V2`; active development mainline: `main`.
- Verified parent commit before v4 docs adoption: `021dcc16fe4f84ac9546349f224dee8331bc8877`.
- v4 adoption at commit `0ca3d9c` was documentation-only. The LB-01 research adapter was merged via PR #2 at `2df653526456345bf2f08a77b35e756f967af2f8`; no AI quality gate is passed by that integration.
- Prior source/history and existing engineering Parts are preserved; v3.1 master and previous state are archived.
- v4 decisions D-018–D-021 added without replacing existing D-017 Profile Learning UX.
- Files `D_015_RAW_FIRST_SCOPE.md` and `D_016_PHOTOGRAPHER_FIDELITY_FIRST.md` are authoritative by pathname; their numeric prefixes collide with other DECISIONS.md historical headings.

## Adopted direction
ProGrapher uses original RAW + verified photographer Lightroom Classic Develop targets to learn each photographer's choices. Source-only visual/technical inputs generate a versioned per-image editing recipe, reviewed and developed/exported by Lightroom Bridge. The Lightroom plugin is a minimal local executor and not the proprietary Brain. Windows x64 and Apple Silicon support, Hebrew RTL UX, customer-owned Lightroom license, safe event-level delivery, and local private data by default remain goals.

Keep neutral EditIntent and exact AdobeDevelopRecipe separately; moving to another renderer will require calibration. Independent JPEG learning/Adobe-equivalent renderer work stays frozen/deferred rather than deleted.

## Evidence collected to date
- User-run Windows v0.1.1 Bridge POC: Exposure +0.55, Highlights −30, Shadows +20 and a valid 8,857,195-byte JPEG.
- User-run Windows v0.2.0 Bridge POC: Adobe Standard profile and 10 develop adjustments read back, 9,152,353-byte JPEG.
- Mask inspector returned one existing, visually reasonable Subject mask; local Exposure remained 0.00. Cannot claim local adjustment or masked export.
- Local RAW/catalog audit: 5,210 RAW files, 7,023 catalog RAW entries, 5,208 unique name-based candidates. They are not proven photographer-approved pairs.
- Local CLIP research: 12 proposals on source RAW, one abstention; uncalibrated, not a learned editor.
- Existing Desktop/Brain contracts and data integrity features exist in GitHub. No full photographer-trained production Brain.

## LB-01 integration review snapshot — 2026-10-12

- Merged PR #2 contains a minimal repository-owned Lightroom Classic Lua research adapter, Python allowlisted `prepare/verify`, synthetic tests, Hebrew Windows instructions and provenance documentation.
- Integrated Windows single-RAW proof: Adobe Standard, ten Develop readbacks, unchanged source RAW SHA-256, JPEG with 9,154,074 bytes.
- Source under local regression: `88c49a6` (test worktree); **16 pytest cases PASSED in 0.50s, exit 0**.
- Scoped error diagnostics were revised after the real Lightroom proof. Positive-path SDK actions were not changed, but the final code revision has not itself been re-tested in Lightroom.
- GitHub-hosted Actions quota: 2,000/2,000 minutes; workflow `38289239558` failed to *start* due to billing/spending limits. **No hosted CI test execution occurred**. The team chose recorded local testing and manual-only workflow dispatch for this research Part. G0's larger CI requirement remains open.
- PR #2 merged successfully and its integration files were verified on `main`. Safe workstation synchronization remains (local modified/untracked files must be preserved). No private RAW/catalog or Lightroom result manifests committed.

## Open gates and risks
- **G0 OPEN:** PG-00.02 and PG-00.05 remain unfinished.
- **B0 PASS only for one Windows research RAW. B1 NOT RUN.**
- **G1–G6 NOT PASSED; zero fully verified training-ready samples.**
- No unattended batch, end-to-end event JPEG workflow, Mac Bridge/installer test or measured quality/time savings.
- v0.3.x local mask SDK experiment is paused; keep evidence separate from product status.

## Next
**LB-01:** repository research integration is merged and mainline-verified. Preserve the Windows single-RAW evidence and perform safe developer-machine sync. Then **LB-02:** authenticated local queue/heartbeat/readback/export on 10→100 RAW, with idempotency/recovery. In parallel prepare **DATA-01** as consent/identity/finality/event-safe research, without unauthorized training.

Do not promote any status merely because the master plan was updated.
