# PG-01.05 — Data Ownership, Consent & Lifecycle Contract

Version: **0.1 DRAFT**  
Prepared: 2026-10-05  
Workflow Part: **PG-01.05**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`  
Related contracts: `RELEASE_1_PRODUCT_CONTRACT.md`, `PG_01_02_DATA_IDENTITY_CONTRACT.md`, `PG_01_04_PROFILE_PACKAGE_CONTRACT.md`

> This contract defines ownership, source-of-truth, consent, quota and deletion semantics for Release 1. It is a product/data contract only. It does not provision Supabase, upload photographer material, start managed training, or authorize any broader use of customer data.

## 1. Non-negotiable ownership rules

1. **Local source photos remain the photographer's files.**
2. ProGrapher never treats a source RAW/JPEG path as cloud-owned merely because the file is indexed locally.
3. **Profile sync is not photo backup.**
4. Syncing or restoring a Profile/ProfileVersion never implies that Events or source photos can be restored.
5. No Event or PhotoAsset is automatically uploaded to cloud storage.
6. Review/approval of an edit does not itself grant permission to upload the underlying photo.
7. Personal managed training and product-wide/global learning are separate consent purposes.
8. A product-improvement/global-learning consent can never be inferred from:
   - account creation,
   - subscription purchase,
   - profile sync,
   - local editing,
   - review approval,
   - exporting a JPEG/XMP.
9. Clearing cache never means deleting source files, Events, Reviews, Profiles or cloud account data.
10. Deleting ProGrapher metadata never silently deletes arbitrary files outside ProGrapher-owned storage.

## 2. Canonical data classes

Release 1 distinguishes these classes because they have different owners, storage locations and deletion semantics.

### A. Photographer source media

Examples:

- Event RAW,
- Event JPEG,
- photographer-owned XMP,
- edited-reference JPEG selected by the photographer.

Default location: photographer-controlled filesystem.

Default cloud upload: **No**.

ProGrapher may read these files only for the user-requested workflow and must not modify source media through normal edit/export flows.

### B. Local operational records

Examples:

- Event,
- PhotoAsset,
- Run,
- RecipeRevision,
- Review,
- Export,
- local Dataset metadata,
- job/checkpoint state.

Source of truth: local SQLite / versioned local manifests.

Default cloud upload: **No**.

### C. Local derived/cache data

Examples:

- previews,
- thumbnails,
- feature cache,
- renderer cache,
- temporary encoded output,
- rebuildable indexes.

Source of truth: none; these are derived data.

They may be deleted/evicted without changing canonical product state, provided the user can rebuild them from canonical inputs.

### D. Profile registry metadata

Examples:

- Profile identity,
- ProfileVersion identity,
- active version,
- contract versions,
- package SHA-256,
- metrics,
- compatibility metadata.

Release-1 commercial source of truth: cloud Profile registry when cloud is enabled; cached locally for operation.

Profile registry sync does **not** include Event source images.

### E. Profile package bytes

Examples:

- weights,
- normalizer,
- feature/recipe/renderer compatibility metadata,
- immutable `.pgprofile` package.

Cloud source of truth after commercial sync is enabled: private profile-package storage.

Local copy: cache/install artifact.

A ProfileVersion is immutable. Updating a profile creates a new ProfileVersion.

### F. Selected learning material

Examples:

- explicitly selected source photos,
- explicitly selected edited references,
- manifests/provenance required for a managed personal-training job.

Default state: local only.

Cloud upload requires **explicit purpose-specific consent** and an explicit selection set.

"Selected learning material" never means "all Events".

### G. Managed-training derived artifacts

Examples:

- extracted training features,
- target representations,
- training checkpoints,
- candidate artifacts,
- evaluation summaries.

These may exist in managed infrastructure only for an authorized training purpose.

They are not source-photo backup.

### H. Account/control-plane data

Examples:

- Account,
- Photographer,
- Device,
- Entitlement,
- consent grants,
- Profile registry,
- training-job metadata.

Source of truth when commercial cloud is enabled: cloud control plane.

### I. Diagnostics

Examples:

- app/engine version,
- failure codes,
- job state,
- performance timings,
- hardware/OS metadata,
- sanitized logs.

Diagnostics must exclude source image bytes by default and must not include arbitrary local paths when a redacted identifier is sufficient.

## 3. Source-of-truth matrix

| Data / entity | Canonical source of truth | Local copy | Cloud copy by default | Restore expectation |
|---|---|---:|---:|---|
| Account | Cloud control plane | minimal session/cache | Yes | Account metadata only |
| Photographer | Cloud control plane | cached | Yes | Photographer metadata |
| Device | Cloud control plane | installation identity | Yes | Authorization state |
| Entitlement | Cloud control plane | cached | Yes | Subscription/eligibility |
| Profile | Cloud registry | cached | Yes | Profile registry |
| ProfileVersion metadata | Cloud registry | cached | Yes | Version metadata |
| Profile package | Private profile storage | installed/cache copy | Yes once sync exists | Package can be restored |
| Event | Local SQLite | Yes | **No** | Not restorable from profile sync |
| PhotoAsset | Local SQLite + source filesystem | Yes | **No** | Source photo not restorable |
| Source RAW/JPEG | Photographer filesystem | direct access | **No** | Photographer backup responsibility |
| Photographer-owned XMP | Photographer filesystem | direct access | **No** | Photographer backup responsibility |
| RecipeRevision | Local SQLite | Yes | No automatic mirror | Local backup/recovery contract |
| Review | Local SQLite | Yes | No automatic mirror | Local backup/recovery contract |
| Export record | Local SQLite | Yes | No automatic mirror | Output file remains external |
| Exported JPEG/XMP | User-selected destination | external | **No** | User storage responsibility |
| Dataset metadata | Local manifest/SQLite | Yes | only if explicitly submitted | Depends on explicit dataset submission |
| Selected learning media | Photographer filesystem until selected | optional managed copy | **No without consent** | Not general photo backup |
| Managed-training artifacts | Managed training storage | optional result cache | only for authorized job | Job/profile evidence, not photo backup |
| Preview/feature/render cache | Derived local cache | Yes | No | Rebuildable; no backup promise |
| Diagnostics | Local diagnostics store | Yes | only explicit support/upload path | Not user-data backup |

## 4. Consent model

Consent is purpose-specific. One grant must not silently authorize another purpose.

### C0 — Local processing

Required for normal product use.

Scope:

- read user-selected local source media,
- index locally,
- infer/render locally,
- save local work state,
- export to a user-selected local destination.

This is not a cloud-photo-upload grant.

### C1 — Profile package sync

Scope:

- Profile/ProfileVersion registry,
- profile package bytes,
- profile settings/compatibility metadata.

C1 **does not permit source RAW/JPEG upload**.

### C2 — Managed personal training on selected material

Separate explicit opt-in.

Scope:

- only the files/items the user explicitly selected,
- only for producing/evaluating that photographer's personal ProfileVersion,
- required provenance and derived training artifacts.

The consent record must bind:

- `account_id`,
- `photographer_id`,
- purpose,
- dataset/selection identifier,
- granted_at,
- policy/contract version,
- status,
- revoked_at when applicable.

C2 must not be inferred from C1.

### C3 — Product-improvement / broader learning

Separate explicit opt-in from C2.

Release 1 does **not** enable this purpose merely by defining the contract.

Before any C3 ingestion is implemented, a later versioned policy must define:

- exact eligible data,
- retention,
- withdrawal effect,
- whether already-trained aggregate models can be practically unlearned,
- privacy/legal requirements,
- user-facing disclosure.

Until that later policy exists, **C3 data ingestion is disabled**.

## 5. Consent state rules

Consent records are append/audit oriented.

Allowed operational states:

- `granted`,
- `revoked`,
- `expired` when a future policy uses expiry.

Rules:

1. New upload/action checks the current grant before transfer begins.
2. Revocation blocks new transfers for that purpose immediately.
3. Revocation does not reinterpret prior local editing as unauthorized.
4. A consent change never deletes photographer source files.
5. A purpose must be shown separately in UI; a single generic "agree" cannot authorize C1+C2+C3 silently.
6. Consent version must be recorded so future policy changes require a new explicit decision when scope materially changes.

## 6. Upload-selection contract

For C2 managed personal training, cloud upload must be based on an explicit immutable selection manifest.

The manifest must identify selected artifacts by stable dataset/photo identity and integrity evidence, not by "upload this whole folder forever".

At transfer time ProGrapher must be able to answer:

- which Event/Dataset supplied the item,
- which local asset was selected,
- which byte fingerprint was authorized,
- which consent grant allowed it,
- which managed-training run received it.

Adding new files to the local Event later does not automatically add them to an existing upload selection.

## 7. Quota contract

Numeric commercial limits are plan/configuration values and are intentionally not hard-coded in this Phase-01 contract.

The product domain must support independent quota dimensions such as:

- profile package storage bytes,
- retained ProfileVersion count,
- selected-learning storage bytes,
- concurrent managed-training jobs,
- retained managed-training artifacts.

Quota behavior is fixed even when numbers change:

1. Exceeding a quota rejects or pauses the **new** cloud operation with an explicit reason.
2. Quota enforcement never deletes photographer source files.
3. Quota enforcement never silently deletes an active ProfileVersion.
4. Existing cloud data is not automatically evicted merely to make a new upload appear successful.
5. Any future automatic cloud-retention/eviction policy must be versioned and user-visible.
6. Local derived cache limits are separate from cloud commercial quotas and may use safe LRU/size eviction because cache is rebuildable.

## 8. Lifecycle and deletion matrix

| User action | Must delete / deactivate | Must preserve | Must never imply |
|---|---|---|---|
| Clear local cache | previews/features/render/temp cache | Event/Review/Profile state; source media | "Event deleted" |
| Remove Event from ProGrapher | local Event catalog/work state according to recovery policy | source RAW/JPEG/XMP and external exports | deleting source folder |
| Delete local Profile cache | installed/cache package | cloud ProfileVersion if still owned | deleting Profile from account |
| Delete/deactivate Profile | active registry relationship; profile package per later cloud retention policy | Events/source photos; immutable audit references needed by completed Runs | deleting photographer photos |
| Delete Dataset record | dataset manifest/state according to retention/consent | unrelated Events/Profiles | deleting all Events |
| Revoke C2 consent | future C2 uploads; pending eligible transfers | local files; completed local edits | C3 revocation or account deletion |
| Delete selected managed-training material | managed copy according to job/retention state | photographer local originals | deleting local Event |
| Revoke Device | device authorization/session | account/profile/source files | deleting account |
| Delete Account | account/control-plane data and private cloud artifacts according to final commercial/legal policy | local source media on user storage | remote wipe of arbitrary photographer disks |

## 9. Event deletion semantics

Deleting/removing an Event from ProGrapher is a catalog/work-state action.

It must:

- clearly state whether saved local Review/RecipeRevision state is also being removed,
- never delete source RAW/JPEG/XMP unless a future, separate explicit file-management feature is intentionally built,
- never delete exported files from arbitrary user-selected folders,
- not trigger cloud deletion of unrelated Profile/ProfileVersion data,
- not resurrect stale Review state merely because the same folder is re-added as a new Event, unless the user explicitly chooses a recovery/import path.

## 10. Profile deletion semantics

Profile deletion/deactivation is independent from Event deletion.

A Profile action must distinguish:

- deactivate Profile for inference,
- remove a local cached package,
- delete a cloud Profile/ProfileVersion artifact,
- delete training material associated with that Profile.

These are not one implicit destructive operation.

An immutable ProfileVersion referenced by historical Run/Export metadata may require a tombstone/audit record even after package bytes are removed.

## 11. Account deletion semantics

The later commercial implementation must provide an account-deletion workflow that can enumerate cloud-held categories before deletion.

At minimum the workflow must distinguish:

- authentication principal,
- Account/Photographer metadata,
- Device/Entitlement records,
- consent records,
- Profile/ProfileVersion registry,
- private profile packages,
- selected learning copies,
- managed-training artifacts.

Local Event source files are outside remote account-deletion authority.

No cloud account deletion operation may attempt a generic recursive delete of user-selected source folders.

## 12. Retention rules

Release 1 uses category-specific retention rather than a single "keep everything forever" rule.

### Local operational data

Retained until:

- the user removes the relevant Event/Profile state,
- a supported cleanup/recovery action removes it,
- an application migration deliberately transforms it.

### Derived local cache

May be evicted automatically under documented cache limits because it is rebuildable.

### Profile packages

An active ProfileVersion package must remain available while that version is considered restorable/synced.

Exact cloud retention counts/durations are commercial policy values and must be versioned separately from the domain identity.

### Selected managed-training material

Retention must be no broader than required for the consented managed-training purpose.

The eventual implementation must expose the retention class before or at upload.

### Diagnostics

Local diagnostic retention must be bounded. Explicit support bundles are user-initiated exports.

No diagnostic retention policy may convert image data into implicit telemetry.

## 13. Backup / sync truth

User-facing language must distinguish:

- **Profile sync/backup** — Profile registry, compatible settings and ProfileVersion packages.
- **Local project/event recovery** — local SQLite/manifests/backups.
- **Photo backup** — **not a Release-1 ProGrapher promise** unless a future product capability is explicitly added.

Prohibited wording/behavior:

- "Your photos are backed up" when only profile data is synced.
- implying a new computer can restore Events whose source media was never uploaded.
- treating selected-training uploads as a general backup archive.

## 14. Failure semantics

If consent, quota or cloud availability blocks an optional cloud action:

- local source photos remain usable,
- local editing/export does not become corrupt,
- the blocked operation reports a specific reason,
- the product does not pretend upload/sync succeeded.

A cloud failure must not downgrade local source ownership or silently move the source-of-truth to a partial remote copy.

## 15. Security boundary for later implementation

When cloud work eventually begins:

- all user-accessible cloud rows require account-scoped authorization,
- storage is private by default,
- service-role credentials never ship in the desktop app,
- signed/session-scoped access does not become a canonical entity identity,
- consent checks occur server-side for managed data operations as well as in the client,
- deletion and consent changes must be auditable.

These are requirements, not evidence that PG-12+ is implemented.

## 16. Migration implications

Current implementation gaps that later persistence/cloud Parts must respect:

- Event ID is still path-derived and must become stable identity.
- Reviews/jobs/exports are not yet all durable canonical entities.
- local profile/testing state is not yet the final Profile/ProfileVersion registry.
- selected-learning consent records do not yet exist.
- cloud quota enforcement does not exist.
- account deletion is not implemented.
- diagnostics/privacy export hardening belongs to later reliability/commercial Parts.

This contract prevents those implementations from inventing incompatible semantics later.

## 17. PG-01.05 completion checklist

PG-01.05 may move to V only when:

- [x] every Release-1 data class has an explicit canonical source of truth,
- [x] source RAW/JPEG ownership remains local by default,
- [x] Profile sync is explicitly separated from photo backup,
- [x] local/cache/cloud categories are distinguished,
- [x] C1 Profile sync and C2 selected managed training are separate purposes,
- [x] broader/global learning requires separate consent and is disabled until a later explicit policy,
- [x] upload selection is explicit and immutable for a training submission,
- [x] quota failure semantics are defined without destructive eviction,
- [x] Event/Profile/Device/Account deletion semantics are distinct,
- [x] cache clearing is explicitly non-destructive to canonical data,
- [x] retention categories are defined,
- [x] current implementation gaps are documented,
- [ ] G0 is signed,
- [ ] product owner ratifies this lifecycle/consent contract.

Until G0 + ratification, PG-01.05 is **◐ CONTRACT PREPARED**, not V.
