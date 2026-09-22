# Phase 11 Part 6A — per-kind visual-region availability

The original RegionEvidence contract had one global state shared by face, skin
and subject evidence. That cannot represent a production case where one
detector is validated while another is deliberately unavailable.

This change adds optional per-kind state:
- face: available / not_detected / unavailable
- skin: available / not_detected / unavailable
- subject: available / not_detected / unavailable

Existing RegionEvidence values remain backward-compatible when kind_statuses
is empty.

The numeric region.<kind>.available flag now follows the per-kind state.

No OpenCV dependency or detector model is introduced in Part 6A.
The active detector remains unchanged, so the unified feature version stays at
its current value.

Next Part 6B:
- face detector candidate
- subject detector candidate
- skin remains explicitly unavailable until a reliable method is validated
