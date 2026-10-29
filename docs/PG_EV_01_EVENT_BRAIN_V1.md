# PG-EV-01 — Event brain v1: moments, anchors and completing an event (engineering building block)

**Branch:** `feature/pg-learning-onboarding-00-02`. **Depends on:** LB-02 (`catalog_writer`, D-022).

## Flow (Lightroom closed for every step)

1. **Choose anchors.** Endpoint: `POST /api/event-edit/anchors`.
   - The event is cut into moments.
   - The middle photo of each of the biggest moments goes into the collection "ProGrapher - Edit these" and gets a purple label.
   - The number of anchors is 4% of the photos, clamped to 20–150.
   - The photographer edits those photos in Lightroom as usual.
2. **Complete the event.** Endpoint: `POST /api/event-edit/complete`. For every photo the photographer did not edit:
   - **In a moment with an edited anchor:**
     - Exposure and base sliders: the anchor's values (Contrast, Highlights, Shadows, Whites, Blacks, Texture, Clarity, Dehaze, Vibrance, Saturation).
     - White balance: the anchor's change from its As Shot (mired, tint), applied on top of the photo's own As Shot.
   - **Other moments:**
     - Base sliders: the anchors' median.
     - Exposure: the automatic exposure when available, else the anchors' median.
     - White balance: As Shot is kept.
   - Written through `catalog_writer.write_edits`: backup, a "ProGrapher" History step, and photographer edits protected.
3. **Undo.** Endpoint: `POST /api/event-edit/undo`. Restores the backup made by step 1 or step 2. Only this catalog's own `ProGrapher Backups` files are accepted.

**As Shot white balance** comes from the catalog itself: the current settings while As Shot, else the earliest As Shot History step (the Import step). No Smart Preview is needed for it.

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
- **Not done yet:** UI, background jobs and progress reporting. `complete` is synchronous and may take minutes with automatic exposure.
- G1 is unchanged. `training_ready_samples` stays 0. This is not a trained model; it is rules tuned on one event.
