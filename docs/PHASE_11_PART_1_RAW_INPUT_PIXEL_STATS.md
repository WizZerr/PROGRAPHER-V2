# ProGrapher V2 — Phase 11 Part 1 — RAW input + measurable pixel features

## Scope

This Part starts P11-01 and P11-02.

It does not choose DINOv3/CLIP yet and does not add face/skin detection yet.

## RAW preparation contract

The real RAW path is explicit and versioned:

- engine: rawpy / LibRaw;
- Camera WB: enabled;
- Auto WB: disabled;
- Auto Bright: disabled;
- gamma: `(1, 1)`;
- demosaic: AHD;
- output: 16-bit;
- color output: sRGB primaries with linear transfer;
- normalized to float32 `[0, 1]`;
- original RAW SHA-256 verified before/after decode;
- embedded JPEG preview is not used.

Any change to those choices requires a new preprocessing version.

## Pixel statistics

The first measurable visual features include:

- linear luminance mean / std;
- luminance p01 / p05 / p50 / p95 / p99;
- shadow/highlight clipping fractions;
- per-channel mean / p01 / p50 / p99;
- RGB chroma ratio;
- red-minus-blue mean.

Large images are sampled deterministically for statistics to cap memory/time.
The exact sample count is recorded as diagnostics but is not itself a model
feature.

## Dependency

`rawpy==0.27.1` is pinned for this Phase 11 Windows probe.

PyPI currently provides CPython 3.12 Windows x86-64 and macOS Apple Silicon
wheels for this release. macOS execution still remains NOT TESTED in this
project until we run it on a real Mac.

## Next

After the real Windows RAW probe passes, Part 2 will connect decoded pixel
features into the Brain V2 input path and add EXIF + RAW WB feature groups in
one versioned vector.

Face/skin/subject evidence, encoder comparison (DINOv3 vs alternatives),
ablation, performance and Mac/MPS/CPU/CUDA comparison remain later Phase 11
work.
