# PG-EV-01 — Event brain v1: moments, anchors and completing an event (engineering building block)

**Branch:** `feature/pg-learning-onboarding-00-02`. **Depends on:** LB-02 (`catalog_writer`, D-022).

## Automatic editing (default, as Imagen does)

**Owner decision (after the safety round):** adding an event edits **the whole event automatically** from the learning profile. No anchors are needed.

**Endpoint:** `POST /api/event-edit/plan/auto {catalog_path, folder_keys, profile_id}`. It is a dry run like every other plan, with the same confirm / undo / scope / lock / job safety described below.

**The style (`style.py`)** is learnt once per profile from its catalogs' before/after pairs and stored with the profile, numbers only (`learning_intake_style`). It holds:
- **Base sliders:** the median of each base slider over the editor's photos.
- **Exposure:** the face target method (`target_face_lightness`, `slope`) from up to 400 photos with faces. The profile's median exposure is kept as the fallback.
- **White balance:** As Shot, kept.

**For each event photo the photographer has not edited:**
- Base sliders come from the profile.
- Exposure: the face target method on the event's own Smart Previews (level solved for the event, plus the per-photo rule), or the profile's typical level when there are no Smart Previews, no face model, or too few faces.
- White balance is left As Shot.

The dry run says which exposure mode was used and why.

**Matching each photo to its Smart Preview:**
- First by the photo's or file's catalog UUID (the DNG's name).
- Every photo still unmatched is then looked up by the RAW file name stored in the Smart Preview (DNG tag 50827). This is the "Export as Catalog" case.
- A name is used only when it is unambiguous:
  - exactly one file in the **whole catalog** has it (two cameras both write `IMG_0001.CR3`);
  - exactly one Smart Preview carries it;
  - that Smart Preview is not already owned by another photo's UUID.
- Anything else stays unmatched; ProGrapher never guesses.
- The plan reports `exposure.matching` = `{by_id, by_name, ambiguous, unmatched}`.

**Uniform exposure needs its own confirmation:**
- The plan lists `requires_acknowledgement: ["uniform_exposure"]` and a warning when photos would get one exposure instead of one measured on the photo. That happens when:
  - there are no Smart Previews, no face model, or too few faces (the whole event); or
  - more than 10% of the photos had no Smart Preview measured (`MAX_UNANALYSED_SHARE`).
- `confirm` refuses (nothing written, the plan stays `planned`) unless `{"confirm": true, "acknowledge": ["uniform_exposure"]}` is sent.
- The screen shows the warning with its own checkbox, and the write button stays disabled until it is ticked.
- 10% or fewer unanalysed photos give a warning (`photos_without_analysis`) only.

**Expected quality (wedding A, a shooter the model had not seen):** about 15% of photos exactly as the editor would leave them (strict limits), and about 25% more within a small fix. The exposure level is close; per-photo exposure is about 0.25 stop off. It improves with more edited events, which is the plan.

**Anchors** (the flow below) remain in the backend as an optional "refine" path and are no longer in the screen.

## Flow and safety (P0/P1 safety round)

Every catalog change is a **job**: a dry run first, then an explicit confirmation. Lightroom must be closed for every step.

| Step | Endpoint | Writes? |
|---|---|---|
| Choose the event | `POST /api/event-edit/folders` | No. Read-only, immutable mode |
| Dry run: anchors | `POST /api/event-edit/plan/anchors {catalog_path, folder_keys}` | No |
| Dry run: completion | `POST /api/event-edit/plan/complete {catalog_path, folder_keys}` | No |
| Dry run: undo | `POST /api/event-edit/plan/undo {job_id}` | No |
| Confirm | `POST /api/event-edit/jobs/{id}/confirm {"confirm": true}` | Yes, after re-checking the catalog |
| Progress, status, recovery | `GET /api/event-edit/jobs/{id}` | No |
| Cancel | `POST /api/event-edit/jobs/{id}/cancel` | No (refused while writing) |

**1. Event isolation (`scope.py`)**
- The event is a set of Lightroom folders (and their subfolders). A folder key is the root folder's `id_global` plus its path inside the root, so it survives moving or copying the catalog.
- `event_id` is derived from the catalog path and the sorted folder keys.
- Every read, plan and write is limited to the event's photos. No folders means no work.
- The writer receives an allow-list: if any photo outside the event reaches a write, nothing is written at all.
- Dry runs open the catalog with SQLite `immutable=1`: the file and its folder stay byte-identical (tested).

**2. Evidence gates (`brain.py`)**
- `MIN_EDITED_ANCHORS = 20` edited anchors, or every planned anchor for a small event. 20 is the smallest anchor count evaluated in the tuning; below it there is no evidence for the event as a whole.
- The gate counts the anchors **ProGrapher recorded**. Removing photos from the collection does not lower it.
- **Only photos in a moment with an edited anchor are written** (the measured "anchor copy" case). All other photos are skipped with the reason `no_edited_anchor_in_moment`. Filling them (automatic exposure, anchors' median) is opt-in (`fill_unanchored`), because the evidence there is weak: about 24–27% of photos had exposure within 0.15 stop.
- A photo whose camera As Shot is more than 15 mired from the anchor's is skipped (`light_differs_from_anchor`). It is the same threshold that splits moments.
- If the anchor changed white balance but the photo's As Shot is unknown, the photo is skipped (`white_balance_unknown`).
- Values already in place are not rewritten (`already_up_to_date`). Only sliders that change are written.
- The dry run reports:
  - What will be written and which sliders.
  - Skip counts by reason.
  - Edited and required anchors.
  - Moments covered and the share of photos covered.
  - Light bins (camera As Shot) with no edited example.
  - Warnings, blocking reasons and the backup folder.

**3. Confirmation and re-validation (`service.confirm`)**
- Only a `planned` job with no blocking reason can be confirmed, and only once (atomic `planned → queued`).
- The dry run stores a fingerprint of the event's state: settings text, historySettingsID, last History step, colour label of every event photo, and ProGrapher's collection members.
- The fingerprint is checked twice:
  - Read-only before the backup, so an outdated plan costs no backup.
  - Again inside the write transaction.
- If anything changed, the job becomes `outdated` and nothing is written.

**4. Safe undo**
- Undo of a completion is **selective**. A photo is put back only if:
  - its latest History step and historySettingsID are still ProGrapher's, and
  - every value ProGrapher wrote is still there.
- Anything edited since is kept and reported (`changed_after_prographer`).
- Only the latest completion of an event can be undone. An undone completion cannot be undone again.
- Undo of choosing anchors:
  - The collection is removed only while it still holds exactly ProGrapher's photos.
  - Labels are cleared only where ProGrapher set them and they are still purple.
- Backups are never deleted. A full restore from a backup is not offered by the engine; it is a manual step (see below).

**5. Collections**
- Each event gets its own collection, `ProGrapher - Edit these [<event id>]`. Its id is recorded as owned by ProGrapher.
- It is reused only while it is still owned, has that name and holds exactly ProGrapher's photos. Otherwise a new one is created (a name that is taken gets a ` (2)` suffix).
- A collection ProGrapher did not create is never changed (tested).

**6. Locking**
- One ProGrapher writer per catalog: an OS-level exclusive lock on `<data>/locks/<catalog-hash>.lock` (released by the OS if the process dies) plus an in-process lock.
- An engine-level check refuses a second write job while one is queued or writing.
- The write is a single `BEGIN EXCLUSIVE` transaction with busy timeout 0.
- Lightroom's `.lock`/WAL is checked before the write and again right before COMMIT. If Lightroom appears, the write rolls back.
- After COMMIT, an integrity check runs; on failure the backup is restored.
- **Not proven:** that Lightroom itself cannot interfere while ProGrapher writes. ProGrapher stops on the signals it can see.

**7. Jobs (`jobs.py`)**
- Statuses:
  - Normal path: `pending → planning → planned → queued → writing → completed`.
  - Ends without a write: `cancelled` (before writing only), `outdated`, `interrupted`.
  - Other ends: `failed`, and for a completion `undone` / `partially_undone`.
- Stored in `<data>/event_edit/jobs.sqlite`. Plans hold per-photo values and are private local data.
- Recovery on the next read of a job left active by a crash:
  - Planning or queued jobs become `interrupted` (nothing was written).
  - Writing jobs are checked against the catalog: History step ids for a completion, the collection for anchors, before-state for undo. They become `completed`, or `failed` with `nothing_written: true/false`.
- The screen offers "check again" only when nothing was written. Otherwise it tells the photographer to check the catalog against the backup.

## Automatic exposure (`exposure_target.py`)

**Target method:** the editor brings faces to about the same final lightness (L\*) for every shooter.
- The target lightness and the "darker faces get more" slope are learnt from the **edited anchors of this event**.
- The level for the rest of the event is then solved from their faces.
- The "before" colours come from the Smart Preview (vendored decoder, Lightroom-Reset render before the tone curve).
- Faces are found with OpenCV YuNet. The model file goes in `<data dir>/models/face_detection_yunet_2023mar.onnx`, or the `PROGRAPHER_FACE_MODEL` env var.

**When it is off:** without the model file, without Smart Previews next to the catalog, or with fewer than 20 edited anchors showing a face. Those photos then get the anchors' median exposure. The response reports this as `automatic_exposure`.

## Evidence (wedding A, one editor, two shooters; each shooter predicted from the other)

Research tools are in the private kit: `exposure_target_test.py`, `wb_target_test.py`, `wb_pattern_test.py`, `v1_simulation.py`, `v1_tuning.py`, `v1_tuning2.py`.

| Finding | Result |
|---|---|
| Final face lightness, F04 / F05 / event B (previews) | 54.9 / 53.5 / 51.9, while the Exposure slider medians were −0.4 / +0.2 / 0 |
| Automatic exposure level without any edit of that shooter | +0.32 vs real +0.28; −0.25 vs real −0.40 |
| Per-photo exposure error | 0.27 / 0.25 stop (preset: 0.74 / 0.61) |
| White balance, target colour | fails: worse than As Shot |
| White balance, rules from metadata | do not beat As Shot (66.5% / 52.9% within limits) |
| What drives white-balance edits | the moment, not camera metadata: 74–81% of same-minute pairs share it |
| Best moment definition | 20 s gap + split on a > 15 mired As Shot jump |
| Best anchor choice | biggest moments |
| Best exposure from an anchor | copying the anchor's exposure ≈ automatic + anchor correction |
| READY share (exposure ≤ 0.15 stop, temperature ≤ 5 mired, tint ≤ 2) | 0 anchors 15%, 40 anchors 37%, 80 anchors 46%, 120 anchors 50.5% |
| Small fix (≤ 0.3 / 10 / 4) | about 15% more |

Two parts of the product are **not yet evidenced**:
- Calibrating the automatic exposure on this event's own anchors. The research learnt it from the other shooter.
- The 4% default anchor count on events other than wedding A.

## Scope and gates

- **Global sliders only.** Curves, HSL, colour grading, profile, crop and masks are expected to come from the photographer's import preset and are never changed.
- **One wedding, one editor, Windows, one Lightroom version.** Event B had previews only (no RAW/Smart Previews), so it is not a full cross-event test.
- **Lightroom checks:**
  - The collection and label writes were verified in Lightroom Classic (experiment 3).
  - The Develop writes were verified in experiments 1–2 (LB-02).
- **Background jobs and progress:** done (see above). Progress during the single write transaction is start/end only.
- G1 is unchanged. `training_ready_samples` stays 0. This is not a trained model; it is rules tuned on one event.

## Tests (synthetic catalogs only)

- `tests/test_event_edit_service.py`:
  - Three events in one catalog; a plan holding another event's photo.
  - No scope; too few edited anchors; the photographer's collection; undo after a later edit; only the latest undo.
  - Concurrent writes; byte-identical dry runs; a plan outdated by an edit.
  - Lightroom open (before, and appearing during the write); failure in the middle; crash recovery.
  - A second confirm, and re-planning after a completed write.
  - Undo of choosing anchors; cancel.
  - Regressions from the independent review: cancel during planning; collection shrinkage does not lower the gate; no backup when outdated; unmark that keeps the collection; recovery of crashed unmark and "(2)" collections; an unreadable catalog during recovery.
- `tests/test_lb02_catalog_writer.py`: allow-list, lock, Lightroom opening, failure rollback, selective revert, collection ownership.
- `tests/test_event_edit_api.py`: HTTP. The dry run writes nothing, confirmation must be `{"confirm": true}`, and a second confirm is refused.
- `frontend/src/features/events/eventFlow.test.ts` (`npm run test:ui`): confirm/retry rules, status texts, saved-state validation.
- A browser run of the panel against a real engine, on a synthetic catalog with two events, went: choose → plan → confirm → blocked with 0 edited → edit → plan → write → undo plan → undo. The other event stayed identical to a fresh build. This was a manual Playwright script, not in CI.
