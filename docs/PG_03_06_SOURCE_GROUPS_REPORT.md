# PG-03.06 — Source Groups & Split Leakage Guard

Date: 2026-10-04  
Evidence HEAD: `c53fd608bd2f1102e9daa294f2ff7509c6d707f3`  
GitHub Actions run: `37172785201`

## Result

**PG-03.06 — V**

The Windows backend regression completed successfully on the evidence HEAD.

## What was implemented

### 1. Source-side perceptual identity

Every decoded JPEG now receives a versioned 64-bit DCT perceptual hash after:

- EXIF orientation normalization,
- ICC/color normalization,
- conversion into the declared working space.

SHA-256 remains the exact bytes identity. The perceptual hash is used only to shortlist possible visual derivatives.

### 2. Source Groups

`backend/app/datasets/source_groups.py` builds dataset-scoped Source Groups.

Detection pipeline:

```text
Exact SHA-256
      ↓
Perceptual pHash candidate search
      ↓
Geometry verification
      ↓
Source Group
```

Verified derivatives may include:

- recompressed JPEG,
- resized JPEG,
- crop,
- rotation,
- mirror/flip,

when geometry evidence proves the same underlying source.

### 3. Conservative suspect handling

A perceptually similar pair that cannot be verified geometrically is **not** silently grouped.

It is written to:

`near_duplicate_suspects.json`

with a stable `review_id`.

Human review may explicitly resolve it as:

- `same_source`
- `distinct_source`

using schema:

`prographer.near-duplicate-reviews.v1`

Stale or unknown review IDs are rejected.

### 4. Split lock is Source-Group aware

Split policy is now:

`event-source-group-v2`

Events linked through one Source Group become one split component.

Therefore:

- whole Events still remain intact,
- exact/near-duplicate derivatives stay together,
- an explicit split cannot put connected events into Validation and Test separately,
- an existing locked Test is never silently moved,
- a newly discovered Event remains unassigned until an intentional lock rebuild.

### 5. Leakage readiness

Evaluation is blocked when:

- a Source Group crosses locked splits,
- an unresolved near-duplicate suspect exists,
- a newly discovered Event is still unassigned.

The dataset manifest records source groups, relations, suspects, policy version and leakage status.

## Regression evidence

`backend/tests/test_jpeg_integrity.py` proves:

- resized/recompressed same-source JPEGs are grouped,
- unrelated visual input is not silently grouped,
- unresolved suspects require explicit review,
- `distinct_source` human review resolves a suspect without merging it,
- connected Events receive the same split,
- a new Event does not move the existing Test split,
- an explicit Validation/Test plan that attempts to split one Source Group is rejected.

## Important limitation

Perceptual matching is a leakage guard, not a semantic photo-search product.

Real photographer data may reveal additional derivative patterns. Those cases become new regression fixtures rather than weakening the split guard.

This Part is engineering/data-integrity evidence; it is not G1 quality evidence by itself.
