# LB-02 — Direct catalog write: delivering edits into Lightroom Classic (engineering building block)

**Branch:** `feature/pg-learning-onboarding-00-02`

**Decision:** D-022.

**Goal:** deliver per-photo slider values into the photographer's Lightroom Classic catalog the way Imagen does:
- The photographer closes Lightroom.
- ProGrapher writes the edits.
- When Lightroom is reopened, every photo shows its values and has a "ProGrapher" History step.

This replaces the plugin route for event delivery. The plugin applied edits one photo at a time and could take close to an hour for an event, with Lightroom busy throughout. Writing directly takes about a second.

## What Lightroom writes when you edit (catalog research, CameraTest catalog)

The research compared before/after snapshots of the catalog around manual edits. Each edit touches the following:

**`Adobe_imageDevelopSettings` row (one per photo):**
- `text` holds the full settings as a Lua-style table, with byte-sorted keys.
- `digest` is a 32-hex fingerprint of the rendering-relevant settings. It ignores the camera/lens profile digests and As Shot Temperature/Tint, so two untouched photos from different cameras share one digest. The exact formula is not known and is not needed (see below).
- `historySettingsID` equals the `id_global` of the latest History step.
- Cache and status columns, including `whiteBalance` and `hasDevelopAdjustmentsEx`.

**`Adobe_libraryImageDevelopHistoryStep`:**
- One row per step: `name`, `valueString`, `relValueString` and `dateCreated` (seconds since 2001-01-01).
- Each row also holds a full settings copy, stored Qt-qCompress style (4-byte big-endian length + zlib).
- `id_local` comes from `Adobe_variablesTable.Adobe_entityIDCounter`.

**Other tables:**
- `Adobe_images`: `touchCount` and `touchTime`.
- `AgLibraryImageChangeCounter` and `LrMobileSyncChangeCounter`: mobile-sync change counters.

**Custom white balance:**
- Text: `WhiteBalance = "Custom"`, plus `CustomTemperature`/`CustomTint` next to `Temperature`/`Tint`.
- Column: `whiteBalance = 'Custom'`.

## Experiments (test copy of the CameraTest catalog; Lightroom Classic, schema 1504001, settings Version 18.7, Windows)

| Experiment | Written | Result in Lightroom |
|---|---|---|
| 1A | settings text only | Slider shows the value, but the digest stays old and the thumbnail stays stale (old look on hover until opened) |
| 1B | text + new random digest + new historySettingsID | Value shown; Lightroom replaced our digest with the real one and re-rendered the thumbnail |
| 1C | 1B + "ProGrapher" History step + touch/counters | As 1B, and "ProGrapher" is the top History step |
| 2 | 1C with WB Custom 6500/+15 and 10 tone/presence sliders on all 25 photos (Canon, Nikon, Sony, Fujifilm, 5 makers) | Values intact 25/25, digest recomputed 25/25, ProGrapher step 25/25, crops kept 25/25; written in 0.02 s |

On the three manual edits from the research, the text editor produced the same text as Lightroom, byte for byte:
- Exposure.
- Custom white balance.
- Exposure + Highlights + Shadows + Texture, including the alphabetical insertion of a new key.

## Module

The module is `app/lightroom_bridge/catalog_writer.py`. Its entry point is `write_edits(catalog, {image_id: {slider: value}})`.

**Writable sliders:** Exposure2012, Contrast2012, Highlights2012, Shadows2012, Whites2012, Blacks2012, Texture, Clarity2012, Dehaze, Vibrance, Saturation, and Temperature + Tint.
- Every value is range-checked and rounded.
- White balance becomes Lightroom's Custom white balance.
- Other keys are never changed: crop, profile, lens, masks, curves.

**Safety:**
1. **Lightroom closed:** it refuses while `<catalog>.lock` exists or `-wal` is non-empty.
2. **Validation before writing:** every value is validated first. One bad value means nothing is written and no backup is made.
3. **Backup:** a SQLite-API backup is written to `ProGrapher Backups/<name>-<time>.lrcat-backup`. The suffix keeps Lightroom from opening it. `restore_backup()` is the undo.
4. **Atomic write:** one transaction, then `PRAGMA quick_check`. On any failure the backup is restored automatically.
5. **Photographer edits are protected:**
   - A photo with any History step other than Import/Export/ProGrapher is skipped (`edited_by_photographer`) unless `overwrite_photographer_edits=True`.
   - Re-running ProGrapher on its own output is allowed.
   - Localised step names count as edits, so a non-English Lightroom is protected rather than overwritten.
6. **Skipped without changes:** photos with Process Version older than 2012 (6.7) or unreadable settings.
7. **JPEG/TIFF:** receive tone values but no white balance, because they use a different scale that is not yet learned.
8. **Layout check:** the catalog layout is verified first. Missing tables or columns, or an unknown History format, means the write is refused.

**Write session (safety round):**
- Every write (`write_edits`, `revert_edits`, `mark_photos`, `unmark_photos`) goes through `_write_session`. It holds:
  - A ProGrapher lock per catalog (OS file lock + in-process).
  - The Lightroom-closed check.
  - An optional `check(db)`, run read-only before the backup and again inside the transaction.
  - The backup.
  - `BEGIN EXCLUSIVE` with busy timeout 0.
  - A Lightroom check before COMMIT.
  - The integrity check after COMMIT.
- An exception before COMMIT rolls back, so the catalog is untouched; it is not restored from the backup.
- `write_edits(allowed_images=...)` refuses photos outside the event.
- `write_edits(history_ids=...)` lets a job prove afterwards what was written. It returns each photo's before-state for undo.
- `revert_edits` puts back only photos still exactly as ProGrapher left them.

**Tests:** `tests/test_lb02_catalog_writer.py`, on a synthetic catalog. They cover:
- Settings round trip and the Lightroom-identical edit.
- Range checks and the lock refusal.
- No partial writes.
- Protection, re-run, JPEG and old Process Version.
- Backup restore and an unsupported layout.

## Scope and gates

- **No UI yet.** The writer is the delivery building block for the event flow: choose a catalog → read Smart Previews → model predicts → `write_edits`. The values will come from the style model, which is not built yet. G1 is unchanged and `training_ready_samples` stays 0.
- **Evidence is narrow.** It covers one Windows machine and one Lightroom Classic version (schema 1504001) on a 25-photo test catalog. Not yet verified:
  - macOS.
  - Other Lightroom versions.
  - Catalogs with virtual copies or stacks.
  - Large catalogs.
  - Mobile-synced collections.
- **Before delivering to customers:** run experiment 2 on every supported Lightroom version. Keep the backup until the photographer confirms the result.
