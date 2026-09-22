# ProGrapher V2 — Phase 11 Part 3

Implements the P11-03 evidence contract for face / skin / subject regions.

Three states are kept distinct:

- `unavailable`: no validated detector is active.
- `not_detected`: a validated detector ran and found no qualifying region.
- `available`: validated region detections exist.

For each region type the feature layer can record count, confidence, area,
position, luminance, clipping and RGB means.

Important: this Part intentionally does **not** add a color-threshold skin
heuristic or an arbitrary third-party detector. The production path therefore
remains `unavailable` until a detector candidate is validated for accuracy,
license and CPU/MPS/CUDA portability.

Unified feature version becomes `brain-v2-features-v1.2`.
