# Phase 6 — scan stuck at 100% fix

## Root cause

The event used in the reproduction had previously been Relinked.

Relink deliberately preserves the Event ID but changes `root_key` to the new
folder path. A later normal scan found the existing row by the new root key,
but `open_folder()` incorrectly derived a fresh Event ID from that path rather
than reusing the stored Event ID.

The subsequent `event_files` write therefore referenced a non-existing Event ID
and SQLite raised a foreign-key error in the background thread.

The job handler did not catch that SQLite exception, so the thread exited while
the in-memory job remained `scanning` at 100%. The frontend therefore polled
forever and never received the final notification.

## Fix

- Existing event root keys always reuse the Event ID stored in SQLite.
- Background scan jobs can no longer die silently: unexpected exceptions become
  `failed`.
- Added explicit `finalizing` state after fingerprinting and before database
  synchronization.
- Added regression test: create -> relink -> rescan moved folder -> same Event ID.
