# Phase 11 Part 2 — RAW metadata fallback fix

The first real unified probe exposed an important issue:

- pixel decode succeeded;
- the older metadata reader printed `File format not recognized.`;
- the probe still printed PASS;
- `RAW WB` and camera metadata stayed missing.

That was not acceptable as the final Part 2 evidence.

## Fix

The real RAW path now gets technical metadata directly from the same
rawpy/LibRaw decode used for pixels:

- Camera/as-shot WB;
- ISO;
- shutter;
- aperture;
- focal length;
- capture time when available;
- camera RGB→XYZ matrix.

Recovered values update the effective `RawInputRecord` before `BrainInput` is
constructed, so the feature vector and BrainInput can no longer disagree.

The probe no longer calls the older metadata reader, so a CR3 that LibRaw
successfully decodes is not followed by a misleading
`File format not recognized.` message from another parser.

## Camera identity

Human-readable make/model are still preserved when a trusted metadata
provider supplies them, but are not guessed from filenames.

For the Phase 11 visual feature path, the LibRaw camera RGB→XYZ matrix is now
included as a versioned numeric camera feature with an explicit missing flag.

This avoids introducing another native/licensed metadata dependency merely to
make the probe look complete. Exact camera make/model can be added through a
separately evaluated metadata provider later.

## Version

Unified features changed from:

`brain-v2-features-v1`

to:

`brain-v2-features-v1.1`

because the actual model input changed.
