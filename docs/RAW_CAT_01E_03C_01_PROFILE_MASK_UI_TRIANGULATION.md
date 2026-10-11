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

## 2026-10-11 — Independent Adobe UI observation, NO edit performed

- Isolated one-photo Lightroom Develop Basic panel displays a nonempty selected Profile labelled **Adobe Color**. Catalog and XMP both contain the identical low-level CameraProfile string **Adobe Standard**. This confirms a UI/serialized-context distinction, NOT resolution or proof of the responsible Look/Profile chain.
- Masking panel displays exactly **one named mask** with a human-silhouette miniature. The adjacent control area explicitly says **No Mask Selected**. **Show Overlay** checkbox is checked, but this only means overlay display is enabled; it is not an enabled/active mask guarantee.
- A nonempty opaque catalog MaskGroupBasedCorrections entry and a Lightroom-visible mask coexist for this sample. Exact correspondence, mask origin/type, mask feather/geometry, stored vs active state, mask-local sliders, Adobe .acr payload semantics, and render equivalence have NOT been verified.
- Screenshots of camera subject, camera image, image-level private files and underlying mask pixels are NOT committed.

NEXT manual action (still no settings changes): click the EXISTING listed mask once to select it, then send a cropped screenshot of the masking panel and adjustment controls ONLY, scrolling within those controls if needed; do not drag any slider, select another preset, or save new metadata. If clicking changes the visible overlay preview, this is selection UI and not a Develop recipe modification.

## 2026-10-11 — Selected-mask UI evidence (PRIVATE values omitted)

- Upon selecting the single listed Lightroom mask, the mask contained a **Select Subject** component; Lightroom displayed **Invert CHECKED**, and the tinted mask preview occupied the outside-of-subject area. This is evidence of the mask recipe as exposed by the Lightroom UI; it is NOT the original mask bitmap or independently reconstructed segmentation.
- Lightroom displayed **two nonzero local Tone controls**. All other visible Tone controls and the visible local Color controls were zero. The exact individual Develop values are intentionally NOT stored in repository docs or reports; they remain LOCAL PRIVATE.
- The checked inversion applies to the Subject-component mask selection and is crucial for meaning: background/outside rather than person/subject is targeted by the displayed mask overlay. Do not assume global Basic values equal mask-local values.
- The displayed mask Amount was standard/full. This alone does NOT establish pixel-parity of adjustments or mask geometry. Hidden controls lower down were NOT inspected yet; do not assert zero on hidden fields.
- Prior screenshots of Show Overlay relate only to Lightroom visibility toggles and cannot establish mask enabled/apply state. The sidecar companion .acr and embedded opaque structures are still not decoded, and an XMP mask field can have nested payloads that a global-property comparer deliberately excludes.
- All photo pixels and the precise masking numbers remain PRIVATE outside the repo.

NEXT: read-only scroll farther down the mask correction panel and share only the right-hand cropped controls, then assess what can be checked **locally and in aggregate** about the nested Adobe XMP mask structure without committing payloads or falsely claiming edit fidelity.
