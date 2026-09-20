# Phase 0 Evidence Log

## 2026-09-20 — archive audit

### Frozen hashes
- Frontend V18.0.5: `458f51720398c3818ca350619bae50492825f03191a03c082f7b21c3e607e496`
- Backend V2.1.3: `4cec4764e7677e38cb144de2720958b4499b560a490c35f08d1b41dfc505aba0`
- New Master Plan: `a71f68b177a51897c5e8a75152a8fc74949799b32145c960bf9f695cc9e8303e`

### Static findings
- Frontend `src/app/page.tsx`: 6,451 lines.
- Frontend `src/app/globals.css`: 6,686 lines.
- Backend `app/main.py`: 5,950 lines.
- `exifread` imports exist in `app/main.py` and `app/profile_ai.py` but dependency is absent from `requirements.txt`, `requirements-raw.txt`, `requirements-ai.txt`, and `requirements-train.txt`.
- Current user-facing/runtime guidance contains Windows-specific `.bat` assumptions.
- Frontend contains Windows catalog path placeholders.

### Checks run
- `python -m compileall` on backend app + training_lab: PASS.
- `python verify_fresh_install.py`: expected FAIL because the supplied source ZIP has no runtime database. This is NOT evidence of an application defect and NOT a runtime PASS.
- Frontend clean build: NOT TESTED in audit environment because dependency installation/lock evidence is not included in ZIP.

### Interpretation
These are baseline facts. No code fix has been applied yet.
