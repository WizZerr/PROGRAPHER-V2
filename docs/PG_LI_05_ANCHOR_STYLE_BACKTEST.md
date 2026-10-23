# PG-LI-05 — Style model backtest: the anchor method on the product's own pairs (research)

**Branch:** `feature/pg-learning-onboarding-00-02`
**Goal:** measure, inside the product and on a real catalog, how many photos the research **anchor method** would deliver without the photographer touching them. It is compared against two simple baselines.

## Method

The code is in `app/learning_intake/anchor_backtest.py` and works on the PG-LI-04 pairs.

**White balance in Lightroom units.** `white_balance.py` converts each Smart Preview's `AsShotNeutral` to Kelvin and Tint the way the DNG SDK does:
- Iterative ColorMatrix/CameraCalibration interpolation for neutral → xy.
- Robertson isotemperature lines for xy → Kelvin and Tint (tint × −3000).

For every "As Shot" photo the result is checked against the value Lightroom stored, and the check is reported as `as_shot_conversion_check`. The photographer's white-balance change is measured in **mired** relative to that As Shot value.

**The anchor rule (from the research pilot).**
- Photos are sorted by capture time and cut into K equal runs. The middle photo of each run is its anchor, and its real edit is used.
- Exposure is copied from the anchor.
- White balance applies the anchor's change from its own As Shot (in mired and tint) on top of each photo's As Shot.

**Baselines:**
- `as_shot`: no correction.
- `global_median`: the median of the anchors' exposure and white-balance changes, applied everywhere.

**"Untouched"** means |exposure| ≤ 0.15 EV, |temperature| ≤ 5 mired and |tint| ≤ 2, the research definition. Anchors themselves are not scored. Black & white photos are excluded.

**Learning curve.** The report also gives the untouched rate at 15, 50 and 100 anchors, plus the requested number.

## Product surface

- **Endpoint:** `POST /api/learning-intake/profiles/{id}/anchor-backtest` with body `{catalog_path, anchors 5..500 (default 100), sample_size ≤ 4}`.
- **Panel:** the button "בדוק את מודל הסגנון (שלב 5)". It shows:
  - The method/baseline table and the anchor curve.
  - Up to 4 photos, each with its "before" image, the photographer's values and the proposed values.
- **Nothing is stored:** `model_stored` and `applied_to_lightroom` are always `false`.

## Scope and gates

- This is an **in-event** measurement of the anchor workflow: the anchors come from the same event. It is **not** the G3 unseen-event generalisation test.
- Edit finality and consent are still unverified. G1 is unchanged and `training_ready_samples` stays 0.
- Anchor choice is by equal time runs. A real product would let the photographer choose the anchors, or pick them by scene similarity.

## Photographer-facing flow (simplified screen)

The learning screen now has three simple views. The research and diagnostic buttons are gone from the UI, but their API routes remain.

1. **Profile:** name, photography type, colour mode and consent.
2. **Add catalog:** the photographer picks a folder; the catalog and its Smart Previews are found automatically.
   - **"הוסף ונתח"** first attaches the catalog.
   - It then calls `POST /api/learning-intake/profiles/{id}/analyze`, which does PG-LI-03 to 05 in one pass.
   - A checklist shows progress while it runs.
3. **Profile summary:**
   - Photos found, linked and with edits read.
   - Expected savings ("with K edited photos, about X% of the rest need no change", plus the 15/50/100 curve).
   - The photographer's style:
     - fixed preset values;
     - sliders adjusted per photo, with their range;
     - sliders left untouched;
     - rarely used sliders.
   - Four sample before images with the photographer's and the proposed values.

The numeric summary is stored per catalog in `learning_intake_analysis`. It holds counts, medians and percentages only: no file names, photo paths or images. It is shown again when the profile is reopened. The sample images are returned once and never stored. Deleting the profile deletes its summaries.
