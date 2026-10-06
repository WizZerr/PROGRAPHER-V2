# ProGrapher V2 — Evaluation Protocol

Protocol version: **1.0**  
Prepared: **2026-10-06**  
Workflow Part: **PG-01.06**  
Status: **◐ FROZEN DRAFT / G0 RATIFICATION PENDING**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

This file replaces the earlier generic Phase-15A measurement note while keeping
the same filename for historical links.

It freezes how ProGrapher evaluates representation quality, predictive model
quality, real workflow value and Release 1 claims **before** candidate results
are available.

It does not claim that photographer quality, automation or time saving has
already been measured.

---

## 1. Evaluation principles

1. **JPEG and RAW are different product paths.** JPEG is the primary independent
   Release 1 editing path. RAW is an assisted RAW/XMP path. Their quality claims,
   denominators and visual truth are never merged.
2. **Whole Event / source-group separation is mandatory.** Random image-level
   splitting from one Event cannot establish generalization.
3. **Validation chooses; locked Test audits.** Repeated Test inspection turns it
   into development data and requires a new locked Test set.
4. **Image counts are not independent experiments.** Primary conclusions are
   reported by Event and Photographer; photo-level rates remain supporting
   measurements.
5. **Human delivery judgment is primary for artistic usefulness.** Pixel metrics
   diagnose differences but do not replace photographer judgment.
6. **The normal workflow is a real baseline.** Presets, sync, AI tools or other
   aids the photographer normally uses remain part of the baseline rather than
   being removed to make ProGrapher look better.
7. **Unsupported/excluded material stays visible.** It can be removed from a
   capability-specific denominator only under a predeclared rule and must still
   appear in coverage reporting.
8. **No threshold is lowered after seeing a candidate result.** A threshold
   change requires a new protocol version, rationale and future evaluation.
9. **A failed run remains evidence.** Retry or a later model does not delete or
   overwrite the failed artifact/result.
10. **Source safety and data integrity outrank average quality.** Corruption,
    wrong-source output, unsafe overwrite or leakage blocks the relevant Gate.

---

## 2. Evaluation units and outcome vocabulary

### 2.1 Units

- **Photo** — atomic editing outcome.
- **Source group** — exact/near-duplicate or otherwise linked source derivatives
  that must stay in one split.
- **Event** — primary unit for generalization and workflow-time reporting.
- **Photographer** — primary unit for Release 1 value claims.
- **Evaluation run** — immutable combination of protocol version, dataset
  snapshot/splits, candidate, baseline, renderer/recipe versions, code commit
  and environment.

### 2.2 JPEG human outcome categories

Every supported photo reviewed for JPEG quality receives exactly one primary
outcome:

| Outcome | Definition |
|---|---|
| **ACCEPT_NO_CORRECTION** | Photographer would deliver the result without changing the edit. |
| **MINOR_CORRECTION** | Deliverable after a small routine correction that does not change the editing strategy. |
| **MAJOR_CORRECTION** | Requires substantial re-editing or a different edit decision before delivery. |
| **SERIOUS_FAILURE** | Not safely deliverable: severe color/skin/tone failure, wrong source/content, corrupt output, destructive artifact or another predeclared critical failure. |
| **UNSUPPORTED / EXCLUDED** | Outside the declared capability or invalid by data/integrity rules. Reason is mandatory. |

`ACCEPT_NO_CORRECTION` is the only category counted as "accepted without manual
correction".

### 2.3 Delivery-quality rubric

Photographer review records at minimum:

- exposure / overall tone,
- color cast and white-balance impression,
- skin color where people are present,
- highlight/shadow handling,
- distracting artifacts / clipping,
- consistency with neighboring delivered images,
- source/output correctness,
- overall **would deliver / would not deliver** decision.

Optional sub-scores may be added later, but the delivery decision and primary
outcome category remain mandatory.

### 2.4 Serious failure

A serious failure is separate from "needs correction". Examples include:

- clearly wrong source or mismatched image,
- corrupt or unreadable result,
- severe skin/color failure that a photographer would immediately reject,
- destructive clipping/artifact introduced by the system,
- source mutation or unsafe overwrite,
- another failure class frozen before the run.

For G3, the candidate serious-failure rate may not exceed the frozen baseline
rate on the promotion set.

A **new systematic serious failure** also blocks promotion. For this protocol it
means the same serious-failure mechanism appears on at least two independent
source groups, or the mechanism is a source-integrity/corruption failure even
once.

---

## 3. Denominators and required reporting

### 3.1 Acceptance without correction

```text
accepted_without_correction_rate =
    ACCEPT_NO_CORRECTION
    / all supported photos selected for editing in the evaluation set
```

The report must show the raw numerator and denominator.

Unsupported/excluded photos are reported separately with reason. They cannot be
silently removed from overall coverage.

### 3.2 Representation coverage

```text
representation_coverage =
    valid intended-to-edit inputs that fall inside the declared representation scope
    / all valid intended-to-edit inputs before representation-scope exclusion
```

Data-integrity exclusions from G1 are reported separately and do not become
representation failures. Representation exclusions are part of the G2 coverage
denominator.

### 3.3 G2 "close enough" rate

```text
g2_close_enough_rate =
    in-scope Validation pairs rated close enough to serve as a learning target
    / all valid in-scope Validation pairs presented for G2 review
```

### 3.4 Serious-failure rate

```text
serious_failure_rate =
    SERIOUS_FAILURE
    / all supported photos selected for editing in the evaluation set
```

### 3.5 Event and photographer reporting

Photo-level rates are reported, but Gate summaries use:

- per-Event results,
- median across Events where a median is requested,
- per-Photographer results,
- distribution/range and weak groups.

Thousands of photos from one Event do not count as thousands of independent
proofs.

---

## 4. Data separation and locked-Test discipline

### 4.1 Split rule

Train / Validation / locked Test are separated by whole Event and source group.

A source group may never cross splits.

Exact/near duplicates discovered after a split are treated as contamination and
must be resolved before a promotion result is valid.

### 4.2 Validation

Validation may be used for:

- representation design,
- model/hyperparameter choice,
- baseline selection,
- threshold-independent engineering debugging,
- candidate rejection.

Every decision that consults Validation is logged.

### 4.3 Locked Test

Locked Test is opened only after:

- candidate identity is frozen,
- baseline identity is frozen,
- protocol version is frozen,
- code/dependency/recipe/renderer versions are recorded,
- Validation-based decisions are finished.

The first valid Test audit is preserved.

If Test results drive another model/feature/representation choice, that Test set
is retired to development evidence and a new locked Test set is required before
a later final promotion claim.

### 4.4 Unseen Event requirement

G3, G4 and G6 evidence must use Events not used to fit the evaluated candidate.

G4/G6 time studies use new Events for the Photographer, not replay of the Event
used to construct the profile.

---

## 5. Baselines

Every evaluation declares baselines before results.

### 5.1 Normal workflow baseline

For G4/G6 time studies this is the photographer's real workflow, including
their normal:

- presets,
- synchronization,
- culling/editing tools,
- AI products,
- Lightroom features,
- keyboard shortcuts,
- export workflow.

Removing a tool they normally use invalidates the comparison.

### 5.2 Simple strong model baseline

G3 uses a reproducible simple baseline selected on Train/Validation before the
candidate promotion comparison.

A NoOp or fixed baseline may be used as an engineering reference, but a weak
reference does not satisfy the requirement for a **strong simple baseline** if a
better simple approach is already known.

### 5.3 Previous ProGrapher candidate

When a prior candidate exists, preserve and report it as an additional
comparison. It does not replace the required normal-workflow or simple-baseline
comparison.

---

## 6. JPEG evaluation path

JPEG is the primary independent editing path.

### 6.1 G2 / J0 — representation suitability

Input:

- valid Original/Edited JPEG pairs,
- G1 data-integrity evidence,
- Train/Validation split by Event/source group,
- frozen recipe/renderer/color contract.

J0 may use both Original and Edited because its purpose is to test whether the
representation can reconstruct known edits. This is **not inference**.

Primary G2 measures:

1. **Close-enough reconstruction rate on Validation**
2. **Representation coverage**

Frozen G2 thresholds from Master Workflow section 7:

- **>= 90%** of valid, in-scope Validation pairs are rated "close enough to
  serve as a learning target".
- **>= 80%** representation coverage of valid intended-to-edit input.

The report must also show the remaining <=10% reconstruction failures and all
representation exclusions by reason/group.

Pixel measures such as MAE/PSNR/SSIM, recipe residuals or color error may be
reported for diagnosis, but they do not independently pass G2.

If G2 fails, improve the representation or explicitly reduce/version the product
scope. Do not compensate by simply using a larger predictive model.

### 6.2 G3 / J1 — source-only prediction

Inference input may contain source-side information only.

Edited targets, target-derived metadata or any proxy unavailable on a new Event
are forbidden at inference time.

**Frozen G3 primary metric:** acceptance without manual correction.

This protocol chooses that metric rather than correction-time as the primary G3
metric. Correction/time remains secondary until G4, where the full workflow is
measured.

Frozen G3 promotion threshold:

- candidate improves acceptance without correction by **at least 10 percentage
  points** over the frozen strong simple baseline on the predeclared Validation
  promotion set,
- candidate serious-failure rate does **not increase** relative to baseline,
- no new systematic serious-failure mechanism appears in any declared weak
  group.

Example: baseline 41% acceptance and candidate 52% = +11 percentage points.

Relative-percent improvement is not substituted for percentage points.

### 6.3 Locked-Test audit for G3

After candidate freeze, run one locked-Test audit.

The Test report must:

- use the same frozen candidate/baseline,
- report acceptance, serious failures, coverage and weak groups,
- show candidate acceptance is not worse than the frozen baseline,
- show no increase in serious failures and no new systematic serious-failure
  mechanism.

The +10 percentage-point Validation rule remains the candidate-selection
threshold. Test is confirmatory and cannot be repeatedly mined to tune the
candidate.

A contradictory Test result blocks G3 and returns the work to research.

### 6.4 Weak-group reporting

Where sample size permits, JPEG results are sliced by declared groups such as:

- Event,
- camera/body,
- lens where relevant,
- indoor/outdoor,
- daylight/tungsten/mixed/LED lighting,
- flash/no-flash,
- people/skin-visible vs non-people,
- exposure difficulty,
- representation exclusion reason.

Small groups are labeled as such rather than hidden in the global average.

---

## 7. RAW evaluation path — separate contract

RAW remains an assisted RAW/XMP workflow in Release 1.

JPEG G2/G3 quality thresholds do **not** apply to RAW and RAW results cannot be
included in JPEG automation/time claims.

### 7.1 RAW visual truth

The ProGrapher local RAW preview is an approximation.

Any RAW quality judgment used for a product claim must be made on the supported
Lightroom/Camera Raw result produced from the exported XMP/reference workflow,
not solely on the local preview.

### 7.2 RAW mandatory safety measures

For the supported RAW/XMP path:

- source RAW bytes must remain unchanged,
- photographer-owned XMP must not be silently overwritten,
- ProGrapher XMP ownership/rollback rules must pass,
- round-trip values must remain within the declared contract,
- failed export must not be presented as successful.

Any observed source mutation, unsafe XMP overwrite or corrupt export is a Gate
blocker regardless of average quality.

### 7.3 RAW workflow-time reporting

If RAW-assisted workflow time is measured, report it as a distinct RAW study:

- active editing/review time,
- Lightroom transition/open/import overhead,
- compute/wait time,
- export time,
- delivery-quality approval.

It cannot be merged into the JPEG G4/G6 numerator or denominator without a new
versioned product-scope decision.

---

## 8. Human review procedure

Where practical:

- hide candidate/model identity,
- randomize or counterbalance presentation order,
- do not label a result "AI", "baseline" or "photographer" during quality rating,
- preserve the mapping outside the review UI,
- use the same calibrated viewing environment for a comparison session.

For G2, the photographer may compare Photographer Edited vs J0 reconstruction
because the question is representation fidelity.

For G3, the reviewer evaluates candidate/baseline results without access to
which model produced each image.

Review disagreements or uncertain outcomes are recorded rather than forced into
ACCEPT_NO_CORRECTION.

---

## 9. Time-study protocol

### 9.1 Two time measures

**Active working time** and **total elapsed time** are always reported
separately.

```text
active_time_saving =
    1 - (T_ProGrapher_active / T_Normal_active)
```

### 9.2 Active-time boundary

For an Event, active time includes user attention spent on:

- import/open/select workflow required for the compared path,
- review,
- manual corrections,
- transitions between required applications,
- export initiation/configuration,
- delivery-readiness checks,
- other hands-on steps necessary to reach the same delivery state.

Idle compute, upload/download and unattended waiting are excluded from active
time but included in total elapsed time.

### 9.3 Equal-quality condition

A faster run does not count as time saving if delivery quality is lower.

Both workflows must reach the same predeclared delivery requirement.

If the ProGrapher result needs additional cleanup to reach that level, that
cleanup time belongs in `T_ProGrapher_active`.

### 9.4 Order / memory control

Because editing the same Event twice creates memory/learning effects, the study
uses a predeclared counterbalanced design where practical:

- comparable unseen Events assigned in alternating order, or
- comparable Event subsets with order counterbalanced,
- no deliberate practice round counted as the measured run.

The assignment/order is recorded before the timed result.

### 9.5 Profile/onboarding cost

Profile creation/onboarding is not hidden inside the first Event result.

Report separately:

- photographer active minutes to provide/approve material,
- compute time,
- uploaded/stored bytes where applicable,
- monetary service cost,
- cumulative Event count/time until setup cost is recovered by measured savings.

---

## 10. G4 — local value Gate

Frozen G4 threshold from Master Workflow section 7:

- **>= 30% median active-time saving**
- measured on **at least two new Events** of the target Photographer,
- delivery quality approved,
- required Windows x64 and Apple Silicon operational/performance evidence for
  the supported local path.

Event-level active-time saving is calculated first; the Gate uses the median of
those Event values.

G4 justifies investment in the full commercial envelope. It does **not** prove
a 70–80% market claim.

---

## 11. G6 — Release 1 value Gate

Initial beta evidence target:

- at least **3 Photographers x 3 new Events each**,
- **>= 70% median active-time saving across beta Events**,
- **80%+** is an aspirational target, not the pass/fail minimum,
- **>= 50% median active-time saving for every beta Photographer**,
- delivery quality approved for every Event counted as delivered,
- no open release-blocking safety/security/billing/data-loss defect.

Report each Photographer separately and the Event-level distribution.

A global average cannot hide a Photographer below the per-Photographer floor.

These thresholds constrain what may be marketed. They are not current product
claims.

---

## 12. Performance planning budgets

These are initial engineering budgets from Master Workflow section 7, not yet
final published system requirements.

Measure on the reference systems defined by PG-01.07, with SSD local storage and
a fixed approximately-24MP JPEG set unless the test states otherwise.

| Operation | Planning budget | Measurement rule |
|---|---|---|
| Cold start to usable work state | <= 10 s | Installed package; profile already local; no dev tooling |
| Open cached existing Event to first image | <= 3 s | At least 20 repetitions; report p95 |
| Navigate between cached images | p95 <= 250 ms | Measure idle and with background job |
| Control response | visual feedback <= 100 ms; preview p95 <= 1 s | Preview <= 2048px; final render measured separately |
| Process + export 2,000 supported JPEGs | <= 30 min target | Decode + features + model + render + encode; excludes human review |
| Peak memory | <= 8 GiB target on 16 GB reference system | Whole process tree; CPU/Mac unified-memory context recorded |
| Recovery | completed work not needlessly redone; zero saved-edit loss | Scheduled kill/sleep/relink scenarios |

After the first representative benchmark, budgets may change only with a
documented reason and protocol/version update before the affected model/product
promotion experiment.

---

## 13. Numerical diagnostic metrics

Numerical metrics support diagnosis and reproducibility.

Depending on the representation they may include:

- pixel MAE,
- PSNR / SSIM,
- color error,
- recipe-parameter error,
- median / P90 / P95 error,
- latency p50 / p95,
- peak RAM,
- CPU/GPU utilization,
- export throughput.

They are secondary to the Gate-specific primary metrics unless a later protocol
version explicitly promotes one.

Do not infer artistic preference from one pixel metric.

---

## 14. Zero-tolerance release blockers

Any observed instance of the following blocks the affected Gate until resolved
and reverified:

- source RAW/JPEG modification by a path that promises read-only source safety,
- silent overwrite of photographer-owned XMP,
- wrong-source/wrong-account data exposure,
- loss of saved corrections,
- export failure marked as success,
- corrupt output presented as completed,
- cross-account data leakage,
- incorrect billing/entitlement action at commercial Gates.

"Zero observed in testing" is evidence, not a guarantee that a defect can never
occur.

---

## 15. Required immutable evaluation record

Every promotion run records:

```text
protocol_version:
run_id:
date:
git_commit:
dependency_lock:
photographer_id:
dataset_snapshot_id:
train_ids:
validation_ids:
locked_test_ids:
source_group_contract:
candidate_id:
previous_candidate_id:
baseline_id:
feature_contract:
color_contract:
recipe_contract:
renderer_contract:
OS + hardware:
primary_metric:
primary_threshold:
secondary_metrics:
coverage_denominator:
accepted_n / evaluated_n:
serious_failure_n / evaluated_n:
excluded_n + reasons:
results_by_event:
results_by_weak_group:
runtime / memory / cost:
human_review_protocol:
decision: PROMOTE / REJECT / REQUEST_DATA / CHANGE_REPRESENTATION / BLOCKED
artifact_paths + SHA256:
known_limitations:
```

Missing denominator, split identity, candidate identity or protocol version
makes a promotion result incomplete.

---

## 16. Threshold/version change control

Protocol 1.0 freezes the initial G2/G3/G4/G6 thresholds before real candidate
selection.

A change requires:

1. new protocol version,
2. rationale unrelated to making an already-seen candidate pass,
3. affected Gate/claim listed explicitly,
4. future evaluation under the new version,
5. preservation of prior results under their original protocol.

Old results are never silently reinterpreted under a new threshold.

---

## 17. PG-01.06 Definition of Done

Prepared-state completion requires:

- JPEG G2 and G3 protocols separated and explicit,
- RAW evaluation separated from JPEG claims,
- G3 primary metric frozen,
- G2/G3/G4/G6 thresholds copied from the active Master and fixed here,
- every primary rate has an explicit denominator,
- serious failure and systematic serious failure defined,
- locked-Test reuse rules explicit,
- time-study active/elapsed boundaries explicit,
- normal-workflow baseline protected,
- performance planning budgets captured,
- immutable evaluation record defined,
- threshold change control defined.

Phase 01 formally enters after G0, therefore PG-01.06 remains **◐** until G0 and
ratification even though the protocol draft is frozen for preparation.
