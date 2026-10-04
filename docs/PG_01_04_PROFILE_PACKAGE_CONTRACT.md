# PG-01.04 — Portable Profile Package Contract

Date: 2026-10-04  
Status: **◐ PREPARED / G0 RATIFICATION BLOCKED**

## Purpose

A ProfileVersion must be portable and immutable. Moving the package to another local path must not change its identity or behavior.

This Part is prepared while PG-00.02/G0 remain paused. It cannot become V until the Phase-01 entry gate is satisfied and the contract is ratified.

## Package

Extension used by fixtures/examples: `.pgprofile` (ZIP container).

Root manifest:

`profile_manifest.json`

Schema:

`prographer.profile-package.v1`

The package binds:

- canonical Profile UUID,
- immutable ProfileVersion UUID,
- Photographer UUID,
- version number,
- learning source (JPEG or RAW),
- model contract version,
- feature contract version,
- recipe contract version,
- renderer contract version,
- engine compatibility range,
- metrics,
- artifact role/path/size/SHA-256 records.

Required artifact roles:

- `weights`,
- `normalizer`.

Additional versioned artifacts may be included under explicit roles.

## Portability

Package identity never depends on:

- source filesystem path,
- destination/cache path,
- ZIP filename.

The importer can load the same package after it is copied or renamed.

## Compatibility

Activation/import is fail-closed.

The runtime must match:

- learning source,
- model contract,
- feature contract,
- recipe contract,
- renderer contract,
- declared engine-version range.

An incompatible package is rejected before a final local ProfileVersion directory is created.

There is no partial activation.

## Integrity

Every artifact is hashed with SHA-256 and has a declared byte size.

The importer rejects:

- missing required roles,
- file/hash mismatch,
- unexpected ZIP members,
- duplicate members/roles,
- path traversal,
- symlink entries,
- non-canonical manifest JSON,
- invalid/non-canonical UUIDs,
- an already-installed immutable ProfileVersion.

Import extracts into a temporary directory and promotes it atomically only after full validation.

## Deterministic package writing

The builder:

- uses canonical JSON,
- sorts artifact roles,
- uses fixed ZIP timestamps/permissions,
- refuses to overwrite an existing output package.

The final archive SHA-256 is returned to the caller for the ProfileVersion registry.

## Boundary

This is a local package/compatibility primitive.

It does not provision Supabase, upload packages, activate commercial profiles or claim any model quality.
