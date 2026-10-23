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
