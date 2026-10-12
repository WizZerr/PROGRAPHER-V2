# LB-01 — Lightroom Bridge research integration (code-review candidate)

**2026-10-12 · Parent: ProGrapher v4.0 · Status: REAL Windows Lightroom smoke PASS; PR review/merge pending.**

## Decision

Keep Lightroom integration isolated from personal-AI Brain and application routes. Port only the verified v0.2.0 SDK operations (global Adobe Standard + ten scalar Develop fields + readback + one sRGB JPEG). No masks, batch queue, background worker, network protocol or auto-install in this Part.

### Evidence carried forward, not re-proven by this port

| Source | Result from user's actual Windows Lightroom test |
|---|---|
| v0.1.1 | Exposure +0.55, Highlights −30, Shadows +20; real JPEG, 8,857,195 bytes |
| v0.2.0 | Adobe Standard, ten settings read back, one JPEG, 9,152,353 bytes |
| v0.3.x | A visible Subject mask, but local exposure +0.25 was NOT proven; excluded from LB-01 |

POC reference archives saved privately; SHA-256 of archived zips for provenance:

- `ProGrapher-Lightroom-Bridge-POC-v0.1.1.zip`: `02255b8ecbb52c0d6c7c191659fa6de98c326c6f54257e3a72a8944ff84849bb`
- `ProGrapher-Lightroom-Bridge-POC-v0.2.0.zip`: `f4206eee9174bd34e5a9a189e6fb9d1396faa3187d5cc148fbace35a3a302bbe`

**Privacy:** Do not commit, attach or print any private catalog, RAW content, source filenames, customer paths, photo previews or per-photo manifests. This repository version deliberately uses configurable local test-photo input rather than the filename hardcoded in the original research POC. No zip archive containing private data is added to the repository.

## Files and ownership

- `backend/app/lightroom_bridge/lb01_poc.py`: local CLI preparation and final verification, allowlist, RAW SHA-256 before/after, manifest/result protocol validation and JPEG signature checks.
- `integrations/lightroom_classic/lb01/ProGrapherBridge.lrdevplugin/`: manual Lightroom Classic Lua SDK plugin. No proprietary model or user raw paths embedded.
- `backend/tests/test_lb01_lightroom_poc.py`: synthetic-only source/recipe/failure/overwrite/privacy regression suite.
- `integrations/lightroom_classic/lb01/README_HE.md`: human Windows smoke runbook.

## Safety contract

1. ONLY the exact `Documents/ProGrapher_Research_Private/ProGrapher_RAW_Test/ProGrapher_RAW_Test.lrcat` research catalog, not a photographer source catalog.
2. ONLY a copied `.CR3` directly in `Documents/ProGrapher_Research_Private/RAW_Parity_Test/`.
3. Output ONLY under `RAW_Parity_Test/BRIDGE_LB01/exports/`. No export to RAW folder root and no source/XMP mutation API.
4. One unique job ID; `prepared -> ok/error`; no silent reruns; manual review before clearing evidence. Python checks original RAW SHA-256 before/after and rendered JPEG magic/size.
5. Lua SDK cannot verify SHA-256: original hashing is performed by the Python preflight and postflight. Race-time substitution and hostile local filesystem manipulation are not solved; **do not market or deploy this POC to customers.**
6. Test catalog contents can be changed by `applyDevelopSettings()`; use backed-up test copies only. No writes directly to a Lightroom `.lrcat` SQLite database.
7. This is a **manual** plugin menu action. Actual unattended job ingestion, IPC auth, retries, batch/export and recovery belong to LB-02, not LB-01.

## Definition of Done and status

| Criterion | Result |
|---|---|
| Working original v0.2 SDK code studied and provenance recorded | PASS |
| Safe repo structure + research-only CLI + plugin source | IMPLEMENTED |
| Synthetic negative-path tests | PASS locally (14 tests) |
| Actual SDK smoke with NEW integrated code on authorized Windows research copy | **PASS — user-run integrated plugin, 2026-10-12** |
| Baseline RAW SHA unchanged + Lightroom readbacks + JPEG for new integrated code | **PASS — ten readbacks, profile, unchanged RAW SHA, and 9,154,074-byte JPEG verified** |
| Real Mac Lightroom smoke | NOT LB-01; required before cross-platform release |
| LB-01 complete | **WINDOWS EXPERIMENT VERIFIED; PR REVIEW/MERGE PENDING** — not a production capability |

### Windows test evidence (reported by user, without private artifacts)

The initial run safely stopped because the dedicated export folder was absent. The local prepare step was subsequently completed, and PowerShell showed the four expected entries (work folder, job.txt, result.txt, exports) present. The user then successfully ran the **new integrated LB-01 Lightroom plugin** and the Python verify step returned:

```text
PASS: 10 Develop readbacks, profile, original RAW hash and 9,154,074-byte JPEG verified
```

The verifier checks recipe/readback correspondence, job ID, profile, RAW SHA-256 unchanged since prepare, and a JPEG in the authorized export folder with correct magic bytes and byte count. This **only** proves one authorized Windows research CR3; no batch, masks, AI inference, Mac, or commercial deployment. Exact Lightroom build/version was not reported. Personal image/manifest and catalog remain local.

See `integrations/lightroom_classic/lb01/README_HE.md` for future controlled reproductions.

### Next

The LB-01 Windows run passed. After review/merge, design LB-02 as a separate contract: capability negotiation, authenticated local IPC, job ID/heartbeat, idempotence/restart, bounded 10→100 photo research batch, per-photo audit and source-safe export. Do not add it to LB-01 silently.
