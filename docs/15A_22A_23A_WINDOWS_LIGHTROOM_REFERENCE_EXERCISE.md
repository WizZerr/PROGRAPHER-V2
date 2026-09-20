# ProGrapher — 15A + 22A + 23A — Windows Lightroom Reference Exercise

## Purpose

This is the first real Lightroom Classic exercise after Dataset V2.

The flow is:

RAW source
→ untouched test copy
→ known ProGrapher recipe
→ standard XMP sidecar beside the test copy
→ Lightroom Classic
→ verify displayed Develop values
→ Lightroom JPEG/TIFF sRGB reference render
→ result manifest
→ verify original RAW hash did not change.

## Known recipe

- Exposure: +0.35
- Temperature: 5650 K
- Tint: -7
- Blacks: -40
- Process Version: 11.0
- Camera Profile: Adobe Color

## Safety

The original RAW is never given a sidecar by this tool.

The fixture is copied to:
`~/Desktop/ProGrapher Lightroom Reference/<exercise-id>/fixture`

Only that copy is imported into Lightroom.

## Lightroom Classic 15 note

Adobe documents that Lightroom Classic 15 may maintain an additional ACR
sidecar when saving metadata for raw files. The exercise records whether an
`.acr` file appears but does not treat that as a failure.

## Pass criteria for this Windows exercise

- the source RAW SHA-256 remains unchanged;
- the fixture RAW remains byte-identical;
- Lightroom displays the six expected recipe fields exactly;
- a Lightroom reference JPEG/TIFF exists;
- the result manifest is written.

A PASS here is evidence for the Windows portion of the early 15A/22A/23A
workflow. It does not close the full phases and it does not substitute for
macOS testing.
