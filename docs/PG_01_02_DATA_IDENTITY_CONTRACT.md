# ProGrapher V2 — Data & Identity Contract v1

Version: **0.1 DRAFT**  
Prepared: 2026-10-04  
Workflow Part: **PG-01.02**  
Initial cloud provider: **Supabase**  
Authority: `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`

> This document defines canonical product identities and ownership boundaries. It is a contract, not a cloud deployment. Supabase is the first implementation provider; the product domain must remain portable enough to move providers later without redefining Account, Photographer, Profile or Event identity.

## 1. Storage boundary

### Local operational source of truth — SQLite

The desktop application keeps these operational records locally:

- Event
- PhotoAsset
- Run
- RecipeRevision
- Review
- Export
- local job state
- local cache/index metadata
- local profile package cache
- local Dataset records and source references

Local event source files remain on the photographer's storage.

### Cloud control-plane source of truth — Supabase

Release 1 initially uses:

- **Supabase Auth** — authentication principal
- **Supabase PostgreSQL** — Account, Photographer, Device, Entitlement, Profile registry, ProfileVersion registry, consent and selected-learning metadata
- **Supabase Storage** — private profile packages, model artifacts and explicitly selected learning artifacts

The cloud is **not** the default Event database and is **not** automatic photo backup.

## 2. Identity rules

1. **Identity is never a filesystem path.**
2. **Account, Photographer and Profile are different entities.**
3. **PhotoAsset identity is not its filename.**
4. **Content fingerprint is evidence about bytes; it is not the database primary key.**
5. Canonical domain IDs use UUID strings.
6. Local UUIDs may be generated offline.
7. Paths are mutable locators and may change after Relink.
8. RAW and JPEG learning identities never silently share one ProfileVersion.
9. Deleting a local Event does not delete source files.
10. Syncing a Profile does not imply syncing Event source photos.

## 3. Canonical entities

### Account

Represents the commercial/customer account.

Canonical fields:

- `account_id: UUID`
- `owner_auth_user_id: UUID`
- `status`
- `created_at`
- `updated_at`

Source of truth: **Supabase PostgreSQL**.

The Supabase Auth user ID is an authentication principal. It is referenced by Account but is not used as the Account primary key.

Release 1 has one photographer owner per account operationally, but Account remains a separate entity so future team support does not require changing identity semantics.

### Photographer

Represents the human editing style owner.

Canonical fields:

- `photographer_id: UUID`
- `account_id: UUID`
- `display_name`
- `locale`
- `created_at`
- `updated_at`

Source of truth: **Supabase PostgreSQL**, cached locally.

A Photographer is not an Account and is not a Profile.

### Device

Represents one authorized ProGrapher installation/device.

Canonical fields:

- `device_id: UUID`
- `account_id: UUID`
- `platform` — windows_x64 | macos_arm64
- `installation_public_id`
- `display_name`
- `last_seen_at`
- `revoked_at`

Source of truth: **Supabase PostgreSQL**.

No hardware fingerprint should be treated as an immutable human identity.

### Entitlement

Represents whether an Account may use a commercial capability.

Canonical fields:

- `entitlement_id: UUID`
- `account_id: UUID`
- `product_code`
- `plan_code`
- `status`
- `valid_from`
- `valid_until`
- `updated_at`

Source of truth: **Supabase PostgreSQL**.

Billing-provider IDs are external references, never ProGrapher primary keys.

### Profile

Represents the photographer's logical editing profile.

Canonical fields:

- `profile_id: UUID`
- `photographer_id: UUID`
- `name`
- `learning_source: jpeg | raw`
- `active_version_id: UUID | null`
- `status`
- `created_at`
- `updated_at`

Source of truth: **Supabase PostgreSQL registry**, with local cache.

JPEG and RAW profiles are explicitly separate logical profiles or profile families. They are not interchangeable merely because they belong to the same Photographer.

### ProfileVersion

Represents one immutable version of a Profile package.

Canonical fields:

- `profile_version_id: UUID`
- `profile_id: UUID`
- `version_number`
- `artifact_uri`
- `artifact_sha256`
- `model_contract_version`
- `feature_contract_version`
- `recipe_contract_version`
- `renderer_contract_version`
- `metrics_json`
- `created_at`
- `promoted_at | null`

Source of truth: metadata in **Supabase PostgreSQL**; package bytes in **private Supabase Storage**; active package cached locally.

A ProfileVersion is immutable. A new candidate creates a new version rather than overwriting an old artifact.

### Dataset

Represents a versioned learning/evaluation collection.

Canonical fields:

- `dataset_id: UUID`
- `photographer_id: UUID`
- `learning_source: jpeg | raw`
- `dataset_version`
- `purpose: train | validation | test | mixed_manifest`
- `provenance_status`
- `consent_scope`
- `manifest_sha256`
- `created_at`

Default source of truth: **local SQLite + local manifest**.

A cloud registry record exists only when the Dataset or selected material is explicitly submitted for managed training/sync.

A Dataset ID must not be derived from a folder path.

### Event

Represents a photographer event/work session.

Canonical fields:

- `event_id: UUID`
- `photographer_id: UUID`
- `display_name`
- `event_type`
- `root_locator`
- `availability_status`
- `created_at`
- `updated_at`

Source of truth: **local SQLite**.

`root_locator` is mutable. Relink changes the locator, not `event_id`.

The current implementation derives Event ID from a path hash. That is a migration gap and must be removed in the later persistence/migration Part; it is not the target contract.

Events are not automatically created in Supabase.

### PhotoAsset

Represents one logical source photo in an Event.

Canonical fields:

- `photo_asset_id: UUID`
- `event_id: UUID`
- `media_kind: jpeg | raw`
- `relative_locator`
- `filename`
- `content_fingerprint`
- `size_bytes`
- `modified_ns`
- `capture_metadata`
- `present`

Source of truth: **local SQLite**.

Filename and fingerprint may help reconciliation/pairing but neither is the database primary key.

If a source is selected for managed learning, its cloud learning record references the Dataset and provenance/consent; this does not make every PhotoAsset a cloud-synced Event asset.

### Run

Represents one execution attempt over an Event or Dataset.

Canonical fields:

- `run_id: UUID`
- `run_type: scan | inference | export | training | evaluation`
- `event_id | null`
- `dataset_id | null`
- `profile_version_id | null`
- `status`
- `progress`
- `started_at`
- `completed_at | null`
- `failure_code | null`
- `resume_state`

Editing/inference Runs are local.

Managed TrainingRun metadata may have a cloud projection later.

The current in-memory scan-job ID is not sufficient as the final durable Run contract.

### RecipeRevision

Represents an immutable editing-recipe revision for one PhotoAsset.

Canonical fields:

- `recipe_revision_id: UUID`
- `photo_asset_id: UUID`
- `run_id | null`
- `profile_version_id | null`
- `parent_revision_id | null`
- `source: predicted | user_corrected | imported_reference`
- `recipe_contract_version`
- `recipe_payload`
- `created_at`

Source of truth: **local SQLite**.

Changing sliders creates a new logical revision when committed; historical revisions are not overwritten as if they never existed.

RAW recipe and JPEG recipe payloads are contract-versioned separately.

### Review

Represents the photographer's decision about a PhotoAsset/RecipeRevision.

Canonical fields:

- `review_id: UUID`
- `photo_asset_id: UUID`
- `recipe_revision_id: UUID`
- `decision: approved | corrected | rejected | needs_attention`
- `reviewed_at`
- `learning_eligible`
- `learning_consent_scope`

Source of truth: **local SQLite**.

Selected learning evidence may later be uploaded according to consent. Review does not automatically mean permission for global training.

### Export

Represents one export operation/result set.

Canonical fields:

- `export_id: UUID`
- `event_id: UUID`
- `run_id: UUID`
- `profile_version_id | null`
- `output_locator`
- `format`
- `status`
- `written_count`
- `skipped_count`
- `created_at`
- `completed_at | null`

Source of truth: **local SQLite**.

Output path is mutable metadata, not Export identity.

## 4. Relationship contract

Canonical ownership:

```text
Supabase Auth User
        │
        ▼
     Account
        │
        ├──────── Device
        ├──────── Entitlement
        │
        ▼
   Photographer
        │
        ├──────── Profile ──────── ProfileVersion
        │
        ├──────── Dataset
        │
        └──────── Event
                    │
                    └──────── PhotoAsset
                                │
                                ├──────── RecipeRevision
                                │             │
                                │             └──────── Review
                                │
Event ───────────── Run ──────────────────────┘
  │
  └──────── Export
```

No relation above is inferred from a folder name.

## 5. Supabase Release 1 mapping

### Auth

Use Supabase Auth only as authentication identity.

The desktop application must never treat a raw session token as a permanent product identity.

### PostgreSQL tables — initial target

Cloud tables expected later in the commercial-control-plane phase:

- `accounts`
- `photographers`
- `devices`
- `entitlements`
- `profiles`
- `profile_versions`
- `dataset_registry`
- `training_runs`
- `consents`

Local Event/PhotoAsset/Review/Export tables are **not** mirrored automatically.

### Storage buckets — initial target

Private buckets:

- `profile-packages`
- `training-artifacts`
- `selected-learning-data`

There is intentionally no default `all-events` bucket.

### Access policy

When cloud implementation begins:

- Row Level Security is mandatory for user-accessible tables.
- A client may access only rows owned by its Account relationship.
- Storage objects are private by default.
- Service-role credentials never ship inside the desktop app.
- Desktop receives only end-user/session-scoped credentials.
- Managed training services use server-side credentials.

These are implementation requirements for the later cloud phase, not proof that cloud infrastructure exists today.

## 6. Local SQLite target ownership

The local database must evolve toward durable tables for:

- `events`
- `photo_assets`
- `runs`
- `recipe_revisions`
- `reviews`
- `exports`
- `local_datasets`
- `local_profile_cache`
- schema migrations

Current tables and JSON profile state are migration inputs, not the final contract.

## 7. Current-code gap map

| Current behavior | Contract target | Required later action |
|---|---|---|
| Event ID derived from root-path hash | Stable UUID Event identity | migrate Event identity without losing existing catalog data |
| Event has `root_path` | mutable locator | keep path as locator only; Relink updates locator |
| `event_files` keyed by fingerprint | PhotoAsset UUID + fingerprint attribute | migrate without losing file reconciliation |
| Photographer setup is singleton | Photographer entity scoped to Account | introduce explicit photographer ID |
| Testing profile uses string `photographer_id` and path-derived identity inputs | Profile + immutable ProfileVersion | migrate test profile format into versioned package contract |
| Reviews live in testing-profile JSON | Review + RecipeRevision durable entities | migrate to SQLite tables |
| Scan job exists primarily in memory | durable Run | add persistent resumable job state |
| Export returns response but lacks durable Export entity | Export record | persist export run/result metadata |
| No Account/Device/Entitlement store | Supabase control-plane entities | implement only in commercial cloud phases |
| JPEG manifest stores absolute local path | portable Dataset/Profile references | BUG-PG00-001 remains in bug batch |

## 8. Deletion and lifecycle rules

### Account deletion

Cloud-account deletion policy will be implemented later, but must distinguish:

- auth identity,
- commercial metadata,
- profile artifacts,
- selected learning data,
- legal/audit records.

It must not attempt to delete arbitrary local source photos from the photographer's computer.

### Event deletion

Deleting an Event from ProGrapher:

- removes catalog/work-state according to the local retention policy,
- does not delete original source files,
- does not resurrect old Review state when the folder is re-added as a new Event unless an explicit recovery/import action is chosen.

### Profile deletion

Deleting/deactivating a Profile must not delete source Events.

### Dataset deletion

Dataset deletion follows provenance/consent and training-retention policy; it is independent from local Event deletion.

## 9. Sync rules

Release 1 cloud sync is selective.

Allowed candidates:

- profile registry,
- profile packages,
- compatible settings,
- device/account state,
- consent records,
- explicitly selected learning artifacts.

Not automatic:

- all Events,
- all PhotoAssets,
- arbitrary source RAW/JPEG folders,
- local cache,
- every Review revision.

## 10. Provider portability rule

Supabase is the **initial provider**, not a domain dependency.

ProGrapher code must not expose provider-specific concepts such as Supabase table names or bucket URLs as domain IDs.

Portable domain interfaces should use:

- canonical UUIDs,
- domain records,
- artifact URIs/references,
- auth/session abstraction,
- storage abstraction where needed.

If ProGrapher later migrates to another PostgreSQL/Auth/Storage provider, Account/Profile/Event identities remain stable.

## 11. PG-01.02 completion checklist

PG-01.02 may move to V only when:

- [x] Account is separate from authentication identity.
- [x] Photographer is separate from Account and Profile.
- [x] Profile/ProfileVersion are explicit and RAW/JPEG cannot silently mix.
- [x] Dataset is separate from Event.
- [x] Event identity is explicitly not a path.
- [x] PhotoAsset identity is explicitly not filename/fingerprint.
- [x] Run is durable-domain state rather than only an in-memory job.
- [x] RecipeRevision, Review and Export have explicit identities.
- [x] local-vs-cloud source of truth is defined.
- [x] Supabase is mapped as the initial provider without becoming the domain model.
- [x] current implementation gaps are documented.
- [ ] G0 is signed and the contract is ratified for implementation.

Until G0, this contract is **◐ prepared**, not V.
