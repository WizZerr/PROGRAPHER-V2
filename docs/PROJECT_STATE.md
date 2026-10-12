# ProGrapher V2 — Project State v4.0

**Updated:** 2026-10-12  
**Single source of truth:** [MASTER_PLAN_SOURCE_OF_TRUTH.md](MASTER_PLAN_SOURCE_OF_TRUTH.md) v4.0.  
**Execution board:** [EXECUTION_BOARD.md](EXECUTION_BOARD.md).  
**Previous detailed snapshot:** [archive/PROJECT_STATE_v3.1_2026-10-12.md](archive/PROJECT_STATE_v3.1_2026-10-12.md).

## Repository and adoption
- Repository: `WizZerr/PROGRAPHER-V2`; active development mainline: `main`.
- Verified parent commit before v4 docs adoption: `021dcc16fe4f84ac9546349f224dee8331bc8877`.
- v4 adoption is documentation-only. It does **not** add local POC plugin source to the production codebase or pass an AI quality gate.
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

## Open gates and risks
- **G0 OPEN:** PG-00.02 and PG-00.05 remain unfinished.
- **B0 PASS only for one Windows research RAW. B1 NOT RUN.**
- **G1–G6 NOT PASSED; zero fully verified training-ready samples.**
- No unattended batch, end-to-end event JPEG workflow, Mac Bridge/installer test or measured quality/time savings.
- v0.3.x local mask SDK experiment is paused; keep evidence separate from product status.

## Next
**LB-01:** integrate and regress the proven one-RAW Lightroom Bridge source inside the repository with privacy-safe synthetic tests and verified local source hash. Then **LB-02:** authenticated local queue/heartbeat/readback/export on 10→100 RAW, with idempotency/recovery. In parallel prepare **DATA-01** as consent/identity/finality/event-safe research, without unauthorized training.

Do not promote any status merely because the master plan was updated.
