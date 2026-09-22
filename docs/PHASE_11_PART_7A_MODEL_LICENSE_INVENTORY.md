# Phase 11 Part 7A — Model license and provenance inventory

This document is an engineering compliance inventory, not legal advice.

## Current candidates

| Component | Role | License evidence | Engineering distribution status |
|---|---|---|---|
| OpenCV 5 | runtime | Apache-2.0 | Keep license/notice obligations with distribution |
| YuNet 2026may | face candidate | MIT for files in the OpenCV Zoo YuNet directory | Candidate may be packaged only with required license text |
| PP-HumanSeg 2023mar | rejected subject candidate | Apache-2.0 for files in its OpenCV Zoo directory | Retained only as comparison evidence; not promoted |
| PekingU/rtdetr_r50vd | person candidate | Apache-2.0 in model repository; official RT-DETR repo is Apache-2.0 | Candidate may be packaged only after final compliance review and attribution/notice handling |
| OpenAI CLIP | vision encoder candidate | OpenAI CLIP repository software is MIT | Do not assume the separately hosted pretrained weights have the same grant without direct confirmation |
| DINOv3 | vision encoder candidate | Custom DINOv3 License covers code and model weights | Custom terms must be reviewed before commercial bundling/redistribution |

## Product decisions recorded

- PP-HumanSeg is not promoted because it produced false-positive subject detections on the sculpture negative control.
- YuNet + RT-DETR passed the current basic negative/positive visual validation gate on Windows.
- Skin-region evidence remains explicitly unavailable; no color-threshold heuristic is permitted.
- CLIP and DINOv3 remain comparison candidates. No quality winner can be selected until a representative event-safe Dataset V2 exists.
- Model binaries remain outside Git. License/provenance files and validation evidence may be committed.

## Release gate

Before a shipping build includes any third-party model weight:

1. Re-read the exact license attached to the exact version/weight being shipped.
2. Preserve required copyright/license/NOTICE material.
3. Confirm whether redistribution of the weight itself is permitted.
4. Record exact version/hash in the release manifest.
5. Do not infer permission from a library/code license when the weight is distributed separately.

The runtime inventory tool writes:
`docs/runtime/phase11_model_license_inventory.json`
