# PG-LI-04 — Before / after pairs (research)

**Branch:** `feature/pg-learning-onboarding-00-02`
**Goal:** for every photo, pair its "before" image with its "after" values.
- **Before:** the PG-LI-03 name-verified Smart Preview, rendered as Lightroom Reset.
- **After:** the photographer's Develop values from the catalog.

## How

`app/learning_intake/edit_pairs.py` works on the PG-LI-03 links. The Develop values come from `raw_catalog_intake.parse_develop_settings`, which parses the catalog's own Develop record without executing Lua.

**Targets.** These are the global sliders that a style model can predict from the "before" image: Exposure, Contrast, Highlights, Shadows, Whites, Blacks, Texture, Clarity, Dehaze, Vibrance, Saturation, Temperature and Tint. White balance mode is also kept, and temperature is also given in mired.

**Exclusions** (each one is counted):

| Reason | Meaning |
|---|---|
| `link_not_verified` | The link to the Smart Preview was not name-verified |
| `virtual_copy_shares_master_preview` | A virtual copy: it has the same "before" image as its master |
| *catalog parse exclusions* | Missing, ambiguous or unparsable Develop record |
| `rejected_in_lightroom` | Pick flag −1. `pick`/`rating` are now read when the catalog has them |
| `no_global_develop_values` | None of the target sliders is set |

**Kept as flags, not numbers.** Tone curves, HSL / colour grading, masks / local edits and black & white are flagged per pair. They are never turned into numbers.

**Rules carried over from the research pilot:**
- A field missing from the catalog is missing, never zero.
- Temperature is compared in mired.
- Folder groups (F01, F02…, largest first, no names) are summarised with their median exposure, mired and tint, because each shooter's folder starts from a different preset.

## Product surface

- **Endpoint:** `POST /api/learning-intake/profiles/{id}/edit-pairs`, body `{catalog_path, sample_size ≤ 4}`.
- **Returns:**
  - Counts and exclusions.
  - Per-target coverage with median and 10–90 % range.
  - The folder groups.
  - Up to 4 sample pairs: the rendered "before" image next to the photographer's values.
- **Panel:** the button "בנה זוגות לפני / אחרי (שלב 4)".
- **Privacy:** pairs are built in memory and not stored.

## Still not established

- **Edit finality:** whether the catalog's current Develop record is the photographer's delivered edit.
- **Which shooter edited each folder.**
- **Whole-event train/validation splits.**

`training_ready_samples` stays `0`.
