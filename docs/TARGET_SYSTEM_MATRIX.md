# ProGrapher V2 — Target System Matrix

Prepared: **2026-10-06**  
Workflow Part: **PG-01.07**  
Status: **◐ CANDIDATE MATRIX PREPARED / G0 + PLATFORM MEASUREMENT PENDING**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

## 1. Purpose

This document defines the initial Release 1 hardware / operating-system support
groups before packaging, performance tuning and model selection make accidental
hardware assumptions expensive.

It is a support contract draft, not a marketing claim.

Two targets are mandatory for Release 1:

- **Windows x64**
- **macOS Apple Silicon arm64**

A platform does not become supported because another platform passed, because
the code compiled, or because one developer machine worked.

The numeric hardware requirements below are **candidate requirements** until
measured on representative machines in Phase 02 / Phase 09 / Phase 11.

## 2. Support vocabulary

| Class | Meaning |
|---|---|
| REQUIRED TARGET | Release 1 cannot ship without evidence for this platform family. |
| SUPPORTED | The exact OS/architecture tier has passed the required clean-install, functional, safety and performance evidence. |
| DEGRADED | ProGrapher may run, but a documented performance/capability limitation applies and the UI must state it truthfully. |
| UNVERIFIED | Technically plausible or planned, but there is not enough evidence to promise support. |
| UNSUPPORTED | Outside the Release 1 support contract unless a later versioned decision promotes it. |

## 3. Release 1 platform groups

| Platform group | Release 1 role | Candidate OS scope | Current evidence | Current status |
|---|---|---|---|---|
| Windows x64 | **REQUIRED TARGET** | Windows 11 x64 on a Microsoft-supported release; validate current shipping releases rather than pinning forever to one build | Real local Windows execution: clean product venv, backend regressions, frontend build/lint/TS, Rust/Tauri startup, JPEG + RAW manual flow | **PARTIAL REAL EVIDENCE / not yet commercial SUPPORTED** |
| macOS Apple Silicon arm64 | **REQUIRED TARGET** | Candidate floor macOS 15 or newer; final floor must be measured. Validate the release-current macOS plus an older supported floor before launch | No real Apple Silicon execution evidence yet | **UNVERIFIED / BLOCKING later platform gates** |
| macOS Intel x86_64 | Optional compatibility study only | No Release 1 promise | No product/package evidence | **EVALUATION ONLY / not a Release 1 blocker** |
| Windows on ARM | Outside initial scope | None | None | **UNSUPPORTED for Release 1** |
| Linux | Outside product scope | None | None | **UNSUPPORTED for Release 1** |

OS support follows vendor-supported consumer/workstation releases unless a
specific enterprise/LTSC exception is explicitly tested and versioned.

Windows 10 consumer support is not part of the normal Release 1 target. A later
enterprise/LTSC exception would require its own evidence and support decision.

## 4. Candidate hardware tiers

These values intentionally describe a professional event-editing workstation,
not the minimum hardware on which a window can technically open.

### 4.1 Candidate minimum supported tier

| Resource | Windows x64 | macOS Apple Silicon | Status |
|---|---|---|---|
| CPU / SoC | Windows 11-compatible 64-bit CPU; candidate floor 4 modern cores | Apple M1 or newer | Candidate until measured |
| RAM | **16 GB** | **16 GB unified memory** | Candidate until 2,000-photo workload measurement |
| System/app-data storage | SSD; **20 GB free** beyond OS/app installation | SSD; **20 GB free** beyond OS/app installation | Candidate |
| Event source storage | Local/internal SSD or stable external SSD | Local/internal SSD or stable external SSD | Candidate |
| Export destination | Free space must exceed estimated output with safety margin; preflight must fail clearly instead of partially exporting | Same | Contract requirement; numeric margin finalized in PG-05/09 |
| GPU | No discrete-GPU requirement may be promised yet | No separate GPU requirement beyond Apple Silicon | Model-dependent; finalize only after real candidate benchmarking |
| Display workspace | Candidate effective workspace **1440×900** or larger | Candidate effective workspace **1440×900** or larger | Candidate / UI verification required |
| Internet | Local edit/review/export must not require continuous internet | Same | Cloud account/sync/update behavior is a later commercial-layer requirement |

### 4.2 Recommended professional tier

| Resource | Recommendation |
|---|---|
| RAM | **32 GB** |
| CPU / SoC | 6+ modern CPU cores on Windows; Apple Silicon M2-class or newer as a planning reference, not a hard gate |
| Storage | Fast NVMe/internal SSD for app-data/cache; USB 3.x / Thunderbolt-class external SSD for large event libraries |
| Free app/cache space | **50 GB** recommended before large-event work |
| Display | 2560×1440-class workspace or equivalent high-density display |
| GPU acceleration | Optional until the selected Brain proves a measurable supported path; NVIDIA CUDA / Apple MPS must never be assumed without runtime capability detection |

### 4.3 High-volume / training workstation tier

A 64 GB RAM machine and hardware accelerator may become recommended for local
training, very large Events or future heavier models, but **Release 1 cannot
require this tier until the selected model and workload are measured**.

Managed/cloud training remains allowed by the product contract and must not be
used to disguise an unmeasured local requirement.

## 5. Degraded / unsupported candidates

| Environment | Candidate classification | Required behavior |
|---|---|---|
| 8 GB RAM | DEGRADED / likely below commercial floor | Do not promise 2,000-photo event performance; measure before deciding whether to allow with warning or block |
| HDD event/cache drive | DEGRADED | Correctness must remain intact; performance warning may be appropriate after measurement |
| Network share / NAS as live Event root | UNVERIFIED | No support claim until disconnect, locking, latency and relink behavior are explicitly tested |
| Cloud-synced folder as live Event root | UNVERIFIED | Must not assume atomicity/availability semantics match local disk |
| External SSD | Planned SUPPORTED path | Must pass disconnect/reconnect, relink, source-safety and resume tests |
| External HDD | DEGRADED candidate | Same correctness tests; performance may be below target |
| Windows 10 consumer editions | UNSUPPORTED candidate | No Release 1 support claim |
| Intel Mac | EVALUATION ONLY | No Release 1 blocker; no support promise unless promoted by a later decision |
| Virtual machines | UNVERIFIED | Useful for build smoke only; not quality/performance evidence |
| Remote desktop / virtualized GPU | UNVERIFIED | Not part of Release 1 support contract |

## 6. Accelerator policy

PG-01.07 deliberately does **not** freeze CUDA, MPS, Core ML, DirectML or a
specific GPU as a Release 1 requirement.

Reason:

1. the production Brain has not been selected,
2. current JPEG renderer / RAW safety flows are not evidence for future model
   inference cost,
3. forcing a GPU contract before PG-07/08/11 would make the product architecture
   fit an unproven model instead of measuring the model against the product.

The runtime must eventually expose capability detection rather than infer
support from brand names alone.

Candidate acceleration groups for later measurement:

- Windows CPU fallback,
- Windows NVIDIA CUDA where the selected model supports it,
- Apple Silicon CPU,
- Apple Silicon MPS/Metal where the selected model supports it.

AMD/other acceleration is UNVERIFIED until explicitly implemented and measured.

## 7. Required evidence per physical machine

Every support-matrix run records:

- evidence ID + date,
- machine model,
- CPU / SoC and architecture,
- RAM,
- GPU / accelerator and driver/runtime where relevant,
- internal/external storage type,
- OS version/build,
- display scale/resolution,
- ProGrapher Git commit/version,
- clean install/update path used,
- backend health/startup,
- frontend/Tauri startup,
- Unicode + Hebrew + spaces-in-path behavior,
- JPEG normal + MPO/MPF-backed `.JPG` open/edit/preview/export path,
- RAW preview + XMP path,
- source byte-preservation check,
- 2,000-photo event scan/gallery/edit workload,
- sleep/resume,
- application restart/resume,
- external-drive disconnect/reconnect + Relink where applicable,
- low-disk behavior,
- peak RAM,
- representative CPU/GPU utilization,
- key latency timings,
- crash/error logs.

A Windows PASS is never substituted for macOS evidence.

## 8. Performance measurements required before candidate minimum becomes final

PG-01.07 does not invent hard pass numbers before the workload exists.

For each candidate minimum and recommended machine, later Parts must measure at
least:

1. cold desktop startup to usable shell,
2. Event discovery/scan time for ~2,000 representative files,
3. time to first Gallery content,
4. filmstrip/navigation responsiveness,
5. interactive JPEG control latency,
6. authoritative JPEG preview latency (cold and warm),
7. full-event inference throughput once a real Brain exists,
8. peak RAM during Event scan/review/inference/export,
9. preview/cache disk growth,
10. export throughput and required free-space behavior,
11. RAW preview/XMP latency on supported RAW formats,
12. restart / sleep / external-drive recovery.

Only after those measurements may the candidate 16 GB / CPU / OS floors be
promoted to commercial minimum requirements.

## 9. Current Windows evidence — 2026-10-06

Evidence class: **real local engineering evidence on one Windows x64 development
machine; not broad hardware certification.**

Observed against the current mainline during the local verification session:

- Python **3.12.10** product environment created cleanly.
- Product dependency check: no broken requirements.
- Backend targeted verification: **118 passed / 0 failed**.
- JPEG renderer/product/control follow-up after performance work:
  **27 passed / 0 failed**.
- Frontend ESLint: PASS.
- TypeScript `tsc --noEmit`: PASS.
- Next production build: PASS.
- Rust/Tauri `cargo check`: PASS.
- `tauri dev`: PASS; desktop shell launched and the local FastAPI engine
  started automatically.
- Real Event JPEG manual verification: PASS.
- MPO/MPF-backed camera `.JPG` compatibility discovered and fixed; real-file
  preview confirmed.
- JPEG interactive preview, compare handle, normalized controls and background
  authoritative render behavior manually confirmed.
- RAW Exposure/Temperature/Tint preview path manually confirmed unchanged and
  working.

Not captured in this evidence record:

- exact CPU/GPU/RAM of the Windows machine,
- clean installer/upgrade on a second Windows machine,
- 2,000-photo performance metrics,
- external-drive disconnect/reconnect,
- low-disk/sleep recovery,
- commercial signed installer/updater.

Therefore Windows is **not yet labeled commercially SUPPORTED**.

## 10. Apple Silicon evidence required next

Phase 02 must obtain at least one real Apple Silicon Mac before any platform
gate can close.

Priority matrix:

1. candidate floor: M1-class / 16 GB if available,
2. representative professional tier: 32 GB Apple Silicon if available,
3. current macOS shipping release,
4. one older candidate-supported macOS release where practical.

The first Mac run must prove functional correctness before performance tuning:
clean build/package, engine startup, SQLite/app-data paths, JPEG/MPO, RAW/rawpy,
XMP, Hebrew/Unicode paths, local export and source safety.

MPS/model benchmarks come later once there is a real model candidate.

## 11. Intel Mac decision boundary

Intel Mac is **not a mandatory Release 1 target**.

PG-01.07 opens it as a separate feasibility decision:

- Phase 02 may perform a low-cost build/start smoke if suitable hardware is
  available.
- Failure on Intel Mac does **not** block Release 1.
- Supporting Intel cannot weaken Apple Silicon or Windows quality gates.
- No Intel Mac marketing/support claim exists unless a later versioned decision
  explicitly promotes it after packaging, dependency, performance and support
  cost evidence.

See D-014 in `docs/DECISIONS.md`.

## 12. PG-01.07 Definition of Done

Prepared-state completion requires:

- Windows x64 and Apple Silicon explicitly mandatory,
- initial support classes defined,
- candidate minimum/recommended tiers documented without presenting them as
  measured facts,
- Intel Mac separated from mandatory scope,
- per-machine evidence schema fixed,
- current Windows evidence recorded truthfully,
- missing Apple Silicon evidence remains visible.

Because Phase 01 formally enters after G0, this document remains **◐** while G0
is unsigned. Candidate minimum requirements also remain subject to later
measurement even after ratification.
