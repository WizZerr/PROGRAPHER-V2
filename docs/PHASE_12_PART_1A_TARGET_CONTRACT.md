# Phase 12 Part 1A — Exposure / Temperature / Tint Target Contract

## Scope

This starts only the data-independent portion of Phase 12.

Implemented groundwork:
- P12-01: explicit target contract for Exposure / Temperature / Tint.
- P12-02: explicit Lightroom rendering context.
- P12-03: safe representation of absolute Kelvin and delta-from-As-Shot candidates.

No model is trained or promoted.

## P12-01

V2.0 target fields:
- `exposure_stops`
- `temperature_k`
- `tint`

No other edit parameter is added.

Initial ProGrapher ordinary-camera-RAW product contract:
- Exposure: -5.0 to +5.0 stops.
- RAW Temperature: 2000 K to 50000 K.
- Tint: -150 to +150.

Missing targets remain `None`; no missing value is converted to zero.
A sample is ready for three-target training only when all three are present.

## P12-02

Every target sample carries known rendering context:
- source kind
- Process Version
- camera profile
- tone curve identity
- preset identity (`none` is explicit and valid)

Blank rendering-context values are rejected.

## P12-03

Two WB target representations can be expressed for later comparison:
- `absolute_kelvin`
- `delta_from_as_shot`

`delta_from_as_shot` is allowed only when As Shot Temperature/Tint mapping was
explicitly marked reliable and both values are available.

5000 K is never treated as an implicit universal zero.

The code does not decide which representation is better. That requires the real
Dataset V2.

## Still blocked

- P12-04: training/evaluation against baseline and candidate Brains.
- P12-05: Lightroom render + human visual evaluation.

## Guardrails

- No production inference path changed.
- No model trained.
- No Brain promoted.
- No missing value becomes zero.
- Phase 12 is not declared complete.
