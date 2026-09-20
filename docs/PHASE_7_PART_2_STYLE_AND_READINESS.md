# ProGrapher V2 — Phase 7 Part 2 — Style + Profile Readiness

Implemented:
- Optional photographer style label.
- Optional manual Lightroom XMP preset selection.
- Best-effort preset discovery in OS-specific Lightroom/CameraRaw locations.
- Color-profile policy:
  - `from_source` (safe default),
  - `explicit` with a named profile.
- Explicit profile names are stored but are NOT assumed compatible with every camera.
- Readiness reasons are surfaced explicitly.
- A preset/style choice never changes `needs_more_data` to Ready.
- No base model/profile is invented when no validated personal data exists.

Still pending for Phase 7:
- camera list derived from real source data;
- verified count of RAW ↔ final-edit pairs (Phase 8 contract);
- real macOS validation;
- real Lightroom preset/profile path validation on both OS targets.
