# Phase 11 Part 6B — OpenCV face/subject detector candidates

This is an evaluation candidate, not yet the promoted production detector.

Candidates:
- Face: YuNet `face_detection_yunet_2026may.onnx`
- Human subject: PP-HumanSeg `human_segmentation_pphumanseg_2023mar.onnx`
- Skin: deliberately `unavailable`

The candidate does not use filename inference or a color-threshold skin
heuristic.

Model integrity:
- YuNet SHA256:
  ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0
- PP-HumanSeg SHA256:
  552d8a984054e59b5d773d24b9b12022b22046ceb2bbc4c9aaeaceb36a9ddf24

Third-party license files are stored next to the downloaded model files.

The detector candidate is not wired into the default Phase 11 pipeline yet.
That prevents unvalidated region evidence from silently changing the training
feature contract. Promotion, if any, must happen in a later explicit step.
