# PG-00.05 — Fixture & Restore Matrix

Updated: 2026-10-04  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

**Status: ◐ PARTIAL**

PG-00.05 is not complete yet. This document separates what is already reproducible from what still requires real backup/licensing evidence.

## Required outcome

PG-00.05 requires:

1. DB/profile backup fixture.
2. RAW/XMP fixture.
3. paired JPEG fixture.
4. license/provenance for non-synthetic media.
5. restore on a copy.
6. profile/events/reviews open after restore.
7. source files remain unchanged.

## Current matrix

| Fixture / evidence | Status | What is proven | Remaining gap |
|---|---|---|---|
| Synthetic RAW/XMP test data | AVAILABLE | Dataset/profile/review/XMP safety logic can be exercised without external media | Synthetic bytes are plumbing fixtures, not real-camera decode evidence |
| Synthetic paired JPEG test data | AVAILABLE | Pairing, ambiguity, manifest creation, source/edit separation and JPEG-only filtering | Synthetic bytes are not visual-quality evidence |
| Local FiveK PR1 fixture | LOCAL / RESEARCH ONLY | Manual PR1 RAW/XMP behavior and real DNG previews were exercised | Commercial/product licensing is not established here; do not ship it as a product fixture |
| Event catalog SQLite state | AVAILABLE | Events persist in `prographer.sqlite3` under `PROGRAPHER_DATA_DIR` | Real historical user backup still not supplied/verified |
| RAW profile + review state | AUTOMATED RESTORE TEST ADDED | Copy of local data dir can restore event catalog, RAW profile and saved review while source RAW bytes stay unchanged | CI still needs to run the new test |
| JPEG profile manifest | BUG / BLOCKER | Manifest is created under user data dir and profile stores `dataset_manifest_path` | Path is absolute; moving a backup to a new data-dir location can leave the stored manifest path pointing at the old location |
| Real camera fixture with explicit redistribution/use provenance | MISSING | — | Need a small licensed fixture set before PG-00.05 can be V |
| Real historical DB/profile backup restore | MISSING | — | Need a safe copy of actual user development state; never test restore destructively on the only copy |

## New automated restore scenario

`backend/tests/test_testing_loop.py::test_pg00_backup_copy_restores_event_raw_profile_and_review`

Scenario:

1. create source RAW event and separate RAW/XMP reference,
2. open the event,
3. build RAW profile,
4. save a corrected Review,
5. close the app,
6. copy `PROGRAPHER_DATA_DIR` to a different directory,
7. delete the original app-data copy,
8. reopen the app against the restored copy,
9. verify Event, RAW profile and saved Review are readable,
10. verify source RAW bytes are unchanged.

This is a state-restore plumbing test. It does not claim migration compatibility with every historical ProGrapher version.

## Batched bug discovered during PG-00.05 audit

### BUG-PG00-001 — JPEG manifest backup path is not portable

**Class:** BUG  
**Severity:** High for backup/restore; not source-corruption.  
**Observed in code:** JPEG `TestingProfileSummary.dataset_manifest_path` is stored as an absolute path to a file under the current user data directory.

**Risk:** copying/restoring the app data directory to a different location can preserve the old absolute manifest path.

**Policy:** do not silently fix inside PG-00.05. Add to the future bug batch requested by the product owner. PG-00.05 cannot be marked V until backup/restore semantics for this path are defined and verified.

## Provenance policy for fixtures

- Test-generated synthetic bytes are project-owned test fixtures and require no third-party redistribution permission.
- Real photographs/RAW files require explicit provenance/license before being committed or distributed as fixtures.
- Research datasets may be used only within their allowed terms and must not automatically become commercial product fixtures.
- Photographer material is never committed to the repository unless the relevant permission explicitly allows it.

## Exit blockers for PG-00.05

- **B-004:** real historical DB/profile backup restore evidence missing.
- **B-007:** JPEG manifest absolute-path restore semantics unresolved.
- **B-008:** small real-camera fixture set with explicit usable provenance/license missing.
- New restore test must pass CI.

Until these are resolved, PG-00.05 remains **◐**, not V.
