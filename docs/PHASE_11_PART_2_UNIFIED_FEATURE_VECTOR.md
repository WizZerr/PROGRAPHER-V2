# ProGrapher V2 — Phase 11 Part 2 — Unified Feature Vector

## Goal

Connect the real RAW decode path from Part 1 into the actual Brain V2 input
contract.

The feature input is now one versioned bundle:

- decoded RAW pixel statistics;
- numeric EXIF with explicit missing flags;
- normalized Camera/RAW WB ratios with explicit missing flags;
- camera make/model as categorical context.

## Why camera identity is categorical

Camera make/model are not converted to arbitrary scalar hashes.

A scalar camera ID would imply a fake numeric ordering and can create brittle
model behavior. They remain explicit categorical context so later model
families can encode them appropriately.

## RAW WB

For the visual path, WB priority is:

1. WB reported by the actual RAW decoder;
2. dataset/source metadata WB if decoder WB is unavailable;
3. explicit missing flags.

The feature vector uses normalized R/G and B/G ratios. Original WB values
remain preserved on the source/BrainInput contracts.

## Missing values

Numeric feature encodings may use `0` as a placeholder only when accompanied
by a dedicated `__missing=1` feature.

This does not change the source truth: missing EXIF/WB is still missing in
BrainInput and Dataset contracts.

## Pipeline connection

A new Phase 11 factory path now runs:

real RAW decode
→ unified features
→ BrainInput
→ wiring-only baseline
→ no-op photographer adapter
→ no-op event context
→ no-op critic

The final four components still do not represent editing intelligence.
Every result requires full review and has no invented confidence.

## Next

Part 3 should tackle P11-03: face/skin/subject evidence with an explicit
`not_detected` state and no fabricated subject signal.

After that, encoder candidates can be evaluated against the same unified
input/dataset rather than chosen by reputation.
