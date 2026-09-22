# Phase 12 Part 1D — Dataset Import Manifest

## Purpose

Freeze the structural result of Dataset V2 ingestion into a deterministic,
versioned manifest that later training/evaluation code can consume directly.

The manifest is built from the Part 1C readiness scan.

## Per-sample data

Each sample records:

- stable `sample_id`
- `event_id`
- absolute RAW path
- RAW path relative to the dataset root
- RAW SHA-256
- XMP path / relative path
- XMP SHA-256
- RAW/XMP pairing state
- Phase 12 target state
- Exposure / Temperature / Tint when available
- missing target fields
- rendering context
- ingestion error, if any

## Dataset identity

`dataset_id` is deterministic and content-derived.

It includes the stable sample identities, target values, rendering context,
event grouping, and content hashes.

Running the builder again over unchanged material produces the same dataset ID.

If a RAW, XMP, target value, or relevant rendering context changes, the dataset
identity changes.

## Event-safe behavior

The manifest preserves event IDs and records the usable event list.

It does not itself choose train/validation membership. That later split must be
performed at event level.

## Why this matters

Training should never silently depend on "whatever happens to be in a folder
today."

A saved manifest gives later experiments a reproducible input definition and
lets Brain/model versions record exactly which dataset identity they used.

## Still not done

- no model training
- no event split assignment
- no measured/CLIP/DINO quality winner
- no Base Editor promotion
- no human Lightroom evaluation
