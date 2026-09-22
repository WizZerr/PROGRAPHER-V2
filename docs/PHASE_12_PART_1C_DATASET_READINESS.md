# Phase 12 Part 1C — Dataset Readiness Validator

## Purpose

Prepare for the photographer Dataset V2 before the real material arrives.

This tool does not train anything. It answers a narrower question:

> Is the incoming material structurally ready to begin Phase 12 three-target
> training/evaluation?

## Initial folder convention

The validator treats each immediate child directory as one event.

Example:

```text
DatasetV2/
  wedding-001/
    IMG_0001.CR3
    IMG_0001.CR3.xmp
    ...
  wedding-002/
    IMG_1001.CR3
    IMG_1001.CR3.xmp
    ...
```

If the root has no child directories, the root is treated as a single event.

This is an importer convention, not a permanent product restriction.

## Pairing

For each RAW, the validator tries:

1. `RAW.ext.xmp`
2. `RAW-stem.xmp`

The first existing sidecar is used.

Catalog-only Lightroom edits are explicitly out of scope for this first
readiness validator.

## Checks

Per RAW:
- paired XMP exists
- Phase 12 Exposure/Temperature/Tint can be extracted
- missing targets stay missing
- Process Version / Camera Profile / Tone Curve are known
- preset identity is explicit
- optional RAW SHA-256 for duplicate detection

Dataset-level:
- event count
- usable event count
- duplicate RAW groups
- at least two usable event groups for event-safe train/validation splitting

## Readiness gate

`can_start_three_target_training` is true only when:
- at least one sample has all three targets
- at least two usable event groups exist
- there are no invalid paired XMP/rendering-context rows

This gate is intentionally structural. It does not claim the data are
representative enough, stylistically consistent enough, or high quality enough
for a production Brain.

## Important limitations

- no Lightroom catalog database parsing yet
- no training
- no quality metrics
- no measured/CLIP/DINO comparison
- no Base Editor promotion
- no proof of photographic representativeness
