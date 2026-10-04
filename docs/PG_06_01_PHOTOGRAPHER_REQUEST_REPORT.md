# PG-06.01 — Photographer Data Request Package

Date: 2026-10-04  
Status: **V**

## Deliverables

- `docs/PHOTOGRAPHER_DATA_REQUEST_HE.md`
- `docs/PHOTOGRAPHER_SUBMISSION_CHECKLIST_HE.md`
- `docs/templates/photographer_submission_manifest.template.json`

## Package contract

The photographer is asked for event-separated JPEG material:

```text
EVENT/
├── ORIGINALS/
└── EDITS/
```

The package explicitly defines:

- what qualifies as Original,
- what qualifies as Photographer Final,
- filename/pairing expectations,
- event separation,
- editing software/workflow,
- export/color-space information,
- camera and lighting notes,
- crop/rotation/local-retouch/Photoshop exceptions,
- explicit approved No-Edit cases,
- optional RAW/XMP kept outside the JPEG path,
- confirmation that the photographer has permission to share the selected material for the agreed evaluation scope.

RAW is explicitly optional for starting the JPEG path.

## Validation

The JSON manifest template parses successfully as `prographer.photographer-submission.v1`.

The permission confirmation defaults to `false`; the template never pre-asserts permission on the photographer's behalf.

## Exit

The package is ready to send before files arrive.

PG-06.02 remains blocked on receipt of real photographer material.
