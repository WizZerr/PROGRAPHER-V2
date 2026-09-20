# ProGrapher V2 — Phase 6 Part 2 — Missing + Relink

Added:
- Runtime availability check for each event.
- `מקור חסר` status if the original folder or tracked files are unavailable.
- `איתור מחדש` action using the native folder picker.
- Relink preserves the existing Event ID.
- Relink validates source identity using stored file fingerprints.
- An unrelated folder is rejected.

Not yet completed in Phase 6:
- true progressive scan/progress reporting for very large folders;
- macOS/Finder/external-drive validation.
