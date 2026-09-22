# ProGrapher V2 — Phase 11 Part 4A — Vision Encoder Candidates

## Goal

Start P11-04/P11-05/P11-06 without choosing a winner prematurely.

Comparison candidates:

1. `measured.unified-features.v1`
   - project-owned measured RAW/EXIF/WB/region features;
   - always available;
   - control candidate.

2. `clip.openai-vit-b32.v1`
   - `openai/clip-vit-base-patch32`;
   - optional experiment only.

3. `dinov3.vits16-lvd1689m.v1`
   - `facebook/dinov3-vits16-pretrain-lvd1689m`;
   - optional experiment only.

No pretrained model is promoted or downloaded by this package.

## Vision image contract

The RAW path produces linear sRGB. Before a pretrained encoder sees the
image, the adapter applies the standard sRGB transfer function:

`linear sRGB -> encoded sRGB -> uint8 RGB`

This conversion is versioned as:

`linear-srgb-to-encoded-srgb-v1`

## Candidate adapter

An optional Hugging Face adapter is included. It uses each model's own
AutoImageProcessor and records encoder ID/version, vector dimension, device
and input contract.

Tests do not auto-install dependencies or download model weights.

## Hardware inventory

`tools/phase11_encoder_inventory.py` records torch/transformers/torchvision
versions, CUDA/MPS availability and the candidate registry.

Inventory is not a quality benchmark.

## Next

Part 4B will validate the experiment environment and run the same RAW-derived
image through CLIP and DINOv3. Later, the same downstream predictor family
will be trained per candidate on the same Dataset split and compared on edit
quality, runtime, RAM/VRAM and portability.
