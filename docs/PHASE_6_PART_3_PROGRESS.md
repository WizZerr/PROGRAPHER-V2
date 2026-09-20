# ProGrapher V2 — Phase 6 Part 3 — Progressive Scan

## Added

- Event folder scanning runs in a background thread.
- UI polls a local job status endpoint.
- The interface remains responsive while fingerprinting a large event.
- Progress shows:
  - processed files,
  - total files,
  - percentage.
- Existing synchronous route is retained for compatibility/tests.

## Development sidecar automation

`npm run tauri dev` now runs `scripts/tauri-before-dev.mjs`.

Before Next.js starts, the script compares backend source mtimes with the current
packaged sidecar. If backend code changed, it rebuilds the sidecar automatically.
If nothing changed, it skips the rebuild.

This removes the manual `prepare_tauri_sidecar.py` step during normal desktop
development.

## Still NOT TESTED / remaining Phase 6 scope

- real external-drive disconnect/reconnect on Windows;
- macOS Finder, Unicode/case behavior and external-drive permissions;
- cloud-placeholder files that are not locally available.
