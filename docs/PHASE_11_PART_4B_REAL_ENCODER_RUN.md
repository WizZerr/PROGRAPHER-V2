# ProGrapher V2 — Phase 11 Part 4B — Real encoder runtime

## Purpose

Run the exact same RAW-derived image through the controlled Phase 11
candidates on real hardware.

This is still **not a quality winner decision**.

It establishes that each candidate:

- installs in the clean V2 environment;
- runs on the declared device;
- produces a reproducible embedding contract;
- has measurable inference time and memory cost;
- can later enter the same downstream prediction experiment.

## Windows reference environment

For the current Windows / Python 3.12 reference machine:

- PyTorch: 2.11.0 + CUDA 12.8 wheel
- torchvision: 0.26.0 + CUDA 12.8 wheel
- Transformers: 4.57.6

The PyTorch packages are installed from the official cu128 wheel index.

## CLIP path

CLIP uses:

`CLIPImageProcessor`
+
`CLIPVisionModelWithProjection`

This avoids invoking the text tower when the experiment needs image
embeddings only.

## DINOv3 path

DINOv3 uses:

`AutoImageProcessor`
+
`AutoModel`

The selected Meta checkpoint is gated on Hugging Face. If the user has not
accepted the model access terms and authenticated locally, the benchmark
records DINOv3 as `blocked / gated_or_unauthorized`.

That state is not converted into a fake failure or a substitute checkpoint.

## Measurement

For each pretrained candidate:

- model load time;
- warm-up excluded from inference timing;
- median / min / max inference time;
- peak CUDA allocated/reserved memory where applicable;
- process RSS before/after when psutil is available;
- embedding dimension;
- L2 norm;
- SHA-256 of float32 embedding.

Full vectors are stored in a compressed NPZ for later same-dataset
experiments.

## Important limitation

A one-image embedding benchmark cannot answer whether CLIP, DINOv3, or
measured features produce better photographic edits.

That decision requires the later same-Dataset/same-predictor evaluation
required by P11-04/P11-05 and Phase 15.
