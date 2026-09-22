# Phase 11 Part 7B — Detector extraction/resource benchmark

Benchmarks the validated YuNet + RT-DETR candidate stack on both the negative
and positive RAW controls, in isolated CPU and CUDA workers.

Evidence captured:
- RAW preprocessing time
- cold detector time
- steady-state detector median/min/max
- process-tree peak RSS
- NVIDIA system-total used-memory baseline/peak/delta where available
- control correctness on both devices

Limits:
- two RAWs are not representative production throughput
- GPU memory is system-total delta, not isolated process VRAM
- macOS/MPS remains untested
- quality contribution/ablation is blocked until a representative Dataset V2 exists

No production detector promotion occurs in this part.
