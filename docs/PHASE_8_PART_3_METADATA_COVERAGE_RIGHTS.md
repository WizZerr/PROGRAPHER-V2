# ProGrapher V2 — Phase 8 Part 3 — Metadata + Coverage + Data Rights

## Added

- Per-RAW metadata contract:
  - camera make/model,
  - capture time,
  - ISO,
  - shutter,
  - aperture,
  - focal length,
  - RAW WB when a real vendor tag is available.
- Missing metadata remains missing; no synthetic zero values.
- Photographer ID, event ID, source-group/sequence field, Lightroom version
  and style label have explicit provenance fields.
- Folder-derived `sequence_id` is only a source grouping aid. It is not
  claimed to be semantic scene detection.
- Manifest schema version moved to 2.
- Dataset rights:
  - permission basis,
  - personal-training permission,
  - general-training permission,
  - license name / notes.
- General training is opt-in and false by default.
- Coverage report includes:
  - event count,
  - camera distribution,
  - missing camera / time / RAW WB,
  - verified pairs,
  - local-adjustment exclusions,
  - incomplete targets.
- Lighting coverage remains `not_measured` until event/scene analysis exists.
- Readiness cannot be inferred from image count alone.

## Important limitations

This is metadata/provenance infrastructure, not proof of profile quality.

Phase 8 still needs:
- real Lightroom final-edit / Virtual Copy evidence;
- manual spot-check on real RAW ↔ final-edit pairs;
- Lightroom reference renders and the 15A / 22A / 23A round-trip work;
- real coverage evaluation once professional event material exists.
