# Phase 6 — Existing event notification

Opening a folder that is already tracked must not look like a new import.

The API now returns one of:
- `created` — first time this folder becomes an event.
- `existing` — the same folder was selected again and no new files were found.
- `updated` — the folder was already an event but new photo files were found.

UI messages:
- Existing: `התיקייה כבר משויכת לאירוע „...”. לא נוצר אירוע נוסף.`
- Updated: `האירוע „...” עודכן. נוספו N קבצים חדשים.`
- Created: normal import summary.

This separates:
1. event identity,
2. new files,
3. byte-identical duplicate files inside the selected folder.
