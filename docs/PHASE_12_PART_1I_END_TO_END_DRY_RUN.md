# Phase 12 Part 1I — End-to-End Synthetic Dry Run

## Purpose

Verify that the Phase 12 preparation pieces actually connect end to end before
representative Dataset V2 material arrives.

This Part uses a tiny, deterministic synthetic fixture only.

It does **not** validate photographic quality.

## Pipeline exercised

```text
Synthetic Dataset Manifest
        ↓
Event-Safe Split contract
        ↓
Train-only Simple Baseline fit
        ↓
Validation-only Predictions
        ↓
Candidate Experiment Contract
        ↓
Evaluation Harness
        ↓
Deterministic Dry-Run Report
```

## What the dry run proves

It proves that:

- Dataset identity reaches the downstream evaluation;
- split identity reaches the downstream evaluation;
- train and validation events remain separate;
- the simple baseline fits on train samples only;
- prediction generation covers validation samples only;
- experiment identity can be created for the same Dataset/split;
- evaluation can consume the generated predictions;
- repeated runs produce stable baseline, experiment, and evaluation IDs.

## What it does not prove

The synthetic metrics must not be used to claim:

- useful Exposure prediction;
- useful white-balance prediction;
- measured features beat CLIP or DINO;
- any Brain is ready for production;
- any event-photography quality level.

The generated report explicitly records:

`quality_claim_allowed = false`

## Why this is useful before Dataset V2

When representative photographer material arrives, failures caused by basic
contract wiring should already have been caught.

The real-data path can then focus on:

- Dataset readiness;
- WB target representation;
- measured / CLIP / DINO experiments;
- numeric evaluation;
- camera / lighting failure analysis;
- Lightroom visual review.
