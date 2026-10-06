# PG-01.06 — Evaluation Protocol Report

Date: **2026-10-06**  
Status: **◐ PROTOCOL FROZEN AS DRAFT / G0 RATIFICATION PENDING**

## What changed

`docs/EVALUATION_15A_PROTOCOL.md` was upgraded from the old generic
measurement note into the Release 1 evaluation contract.

The protocol now explicitly separates:

- JPEG representation evaluation (G2/J0),
- JPEG source-only prediction evaluation (G3/J1),
- RAW-assisted compatibility/safety evaluation,
- local workflow value (G4),
- beta/Release 1 value (G6),
- engineering performance budgets.

## Frozen primary decisions

### G2

- >=90% close-enough reconstruction rate on valid in-scope Validation pairs.
- >=80% representation coverage.

### G3

Primary metric is **acceptance without manual correction**.

Promotion requires:

- >=10 percentage-point improvement over the frozen strong simple baseline on
  the Validation promotion set,
- no increase in serious-failure rate,
- no new systematic serious-failure mechanism.

Locked Test is a single confirmatory audit after candidate freeze. It is not a
repeated model-selection surface.

### G4

- >=30% median active-time saving,
- at least two new Events of the target Photographer,
- approved delivery quality,
- required Windows + Apple Silicon operational/performance evidence.

### G6

- initial beta target >=3 Photographers x 3 new Events each,
- >=70% median active-time saving across beta Events,
- >=50% median active-time saving for every beta Photographer,
- 80%+ remains aspirational,
- delivery quality approved for every delivered Event.

## Denominator/failure hardening

The old note did not define enough denominator semantics.

Protocol 1.0 now freezes:

- exact acceptance denominator,
- representation-coverage denominator,
- G2 close-enough denominator,
- serious-failure denominator,
- unsupported/excluded reporting,
- Event/Photographer-level aggregation rules,
- systematic serious-failure definition.

## RAW separation

RAW does not inherit JPEG G2/G3 thresholds.

The local RAW preview remains approximate; product-quality judgment for the
assisted path uses the supported Lightroom/Camera Raw result. Source/XMP safety
remains zero-tolerance.

RAW workflow-time studies, if performed, are reported separately and cannot be
mixed into JPEG G4/G6 claims without a new scope decision.

## Time-study hardening

Active time and elapsed time are separate.

The normal baseline keeps the photographer's real presets/tools. Both workflows
must reach the same delivery quality. Profile/onboarding cost is reported
separately.

Event-level time savings are calculated before medians so thousands of photos
from one Event cannot masquerade as independent evidence.

## Why PG-01.06 is not V

The protocol is technically ready and thresholds are frozen as a draft, but
Phase 01 formally requires G0. G0 is still unsigned.

Therefore PG-01.06 remains **◐**, not V.

No photographer/model-quality claim is created by this documentation work.
