# PG-LI-03 — Smart Preview ↔ catalog photo link (research)

**Branch:** `feature/pg-learning-onboarding-00-02`
**Goal:** know with certainty which Smart Preview DNG belongs to which Lightroom catalog photo. Without that link, a "before" image (the Smart Preview rendered as Lightroom Reset) cannot be paired with that photo's Develop record (the "after").

## How a link is made

- `app/learning_intake/smart_preview_link.py` reads the catalog through the existing consistent snapshot (`_inspect_consistent_snapshot`, private RAW records). It also reads the Smart Previews folder with the probe's bounded DNG inventory.
- **UUID match:** a Smart Preview's file name is a catalog UUID. Each record is matched first on `Adobe_images.id_global` (`image_uuid`), then on `AgLibraryFile.id_global` (`file_uuid`).
- **Name check:** every Smart Preview stores the source RAW's file name (`OriginalRawFileName`, DNG tag 50827). It is read with a bounded IFD0 reader (`dng_diagnostics.read_original_raw_file_name`) and compared with the catalog's `baseName.extension`.
- **Statuses:**

  | Status | Meaning |
  |---|---|
  | `linked_name_verified` | The UUID and the stored name both agree with the catalog |
  | `linked_name_mismatch` | The UUID matches but the stored name differs (e.g. renamed after the preview was built). Needs review |
  | `linked_name_unreadable` | The UUID matches but the DNG stores no name |
  | `no_smart_preview` | No DNG for this photo |
  | `ambiguous_smart_preview` | Several DNGs share the UUID |

- **Also reported:**
  - `orphan_smart_previews`: DNGs that no catalog RAW photo claims.
  - Virtual copies: they share their master's Smart Preview. One "before" image, several Develop records, never several independent examples.

The research pipeline used the same UUID rule. It matched 100/100 pilot photos and 25/25 camera-test photos.

## Product surface

- **Endpoint:** `POST /api/learning-intake/profiles/{id}/smart-preview-links` with body `{catalog_path, sample_size ≤ 4}`. It is authenticated like the other learning-intake routes.
- **Returns:** aggregate counts, plus up to 4 name-verified photos. Each comes with its catalog file name and its rendered "before" image (in memory), so a person can compare it with Lightroom by name.
- **Panel:** the button "קשר Smart Previews לתמונות בקטלוג".
- **Privacy:** no links, names or images are stored.

## Still not established

- **Byte-level RAW identity.** The name check is strong evidence, not proof.
- **Develop targets (the "after") and edit finality.** That is PG-LI-04.
- **Whole-event validation splits.** `photo_to_dng_link_verified` and `training_ready_samples` stay `false` / `0`.
