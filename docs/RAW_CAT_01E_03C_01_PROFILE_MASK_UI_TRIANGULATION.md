# RAW-CAT-01E.03C.01 — Profile/Look and Masks UI triangulation (manual, no source edits)

Date: 2026-10-11. D-015 RAW-first, pre-G0 RESEARCH ONLY.

## Why now
The Adobe-generated XMP and original catalog agreed on 48 exact field/curve representations for ONE copied RAW photo, but the Adobe Lightroom UI previously showed a user-facing profile label differing from the low-level CameraProfile field. The catalog also has an opaque Look and opaque MaskGroupBasedCorrections; an Adobe-created .acr companion exists. **Do not** conclude that a matching CameraProfile string establishes correct visible Profile/Look rendering, or that an opaque mask blob proves active masks.

## Independent Lightroom evidence requested
Use ONLY the **isolated one-photo exported catalog**, with copied camera RAW. Confirm with Show in Explorer that the active photo resides inside the isolated validation export. Do not open/source-edit the photographer's original catalog or RAW. No change to settings, sidecars, profiles, masks, sliders or Save Metadata during this visual inspection.

1. Develop > Basic > Profile: capture **cropped right-panel only** showing selected visible profile label. If safely possible, open Profile Browser without selecting another profile and capture its currently selected item, again RIGHT PANEL ONLY. Record whether the UI says Adobe Color, Adobe Standard, or something else; do not infer equality.
2. Develop > Masking: open panel and inspect whether there is a mask list, and whether any mask is visibly enabled. Capture cropped panel only, excluding the underlying photograph or any person's face. Do NOT toggle a mask, change it, or treat presence of list as proof that AI mask geometry is independently exportable.
3. Close Lightroom without modifying edits. No upload of XMP, ACR, RAW, original/catalog copies or individual private plans to GitHub. Text-only count/label can replace screenshots if cropping is inconvenient.

## Decision outcomes
- If Profile label/UI disagrees with CameraProfile metadata, open a separate semantics-gap issue/probe: investigate Adobe Look/profile identifier chaining on COPIES only and label unresolved until verified in Lightroom. Never auto-map Adobe Standard => Adobe Color.
- If Masks UI shows active masks, do NOT claim training/render parity: .acr and local correction payloads remain opaque, and mask geometry/pixel outcome need independent tests.
- If no masks are listed, do not infer the opaque catalog payload is active; distinguish stored opaque state from applied masks.

## Exit criteria
Manual evidence recorded privately for ONE reference photo (selected UI Profile label; Mask UI list/enable status; no source file changes); update findings only as aggregate categorical statuses, NO photo identifiers. This part does NOT unblock production Brain, G0, photographer data consent/finality, event-level split, or Adobe pixel-render parity.
