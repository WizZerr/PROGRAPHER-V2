# PG-01.05 — Data Ownership & Lifecycle Preparation Report

Date: 2026-10-05  
Status: **◐ CONTRACT PREPARED / G0 RATIFICATION BLOCKED**

## Added

- `docs/PG_01_05_DATA_LIFECYCLE_CONTRACT.md`

## Contract now fixes

- canonical source of truth for every Release-1 data class,
- local-vs-cloud ownership boundary,
- Profile sync vs photo-backup truth,
- purpose-specific consent,
- explicit selected-learning upload scope,
- quota behavior,
- Event/Profile/Device/Account deletion separation,
- cache semantics,
- retention categories,
- diagnostics boundary,
- migration implications for later persistence/cloud implementation.

## Consent decisions

- C0 local processing is not a cloud upload grant.
- C1 profile sync cannot upload source photos.
- C2 managed personal training requires separate explicit consent and explicit selected material.
- C3 broader/product-improvement learning is a separate future opt-in and remains disabled until a later versioned policy defines retention/withdrawal/privacy semantics.

## Quota decisions

Commercial numbers remain plan/configuration values rather than being hard-coded in Phase 01.

The invariant behavior is frozen:

- reject/pause the new cloud operation when quota is exceeded,
- never delete source media,
- never silently evict active profile data,
- never claim a failed upload succeeded.

## Delete/retention decisions

Deleting ProGrapher metadata is not authority to delete arbitrary photographer filesystem content.

Event, Profile, Device and Account deletion are distinct operations.

Profile sync/backup is never presented as Event/photo backup.

## Status rule

PG-01.05 remains **◐**, not V.

The contract content is prepared, but Phase 01 entry/completion requires G0 and explicit product-owner ratification.

No Supabase/Auth/Cloud resources were created and no photographer files were uploaded.
