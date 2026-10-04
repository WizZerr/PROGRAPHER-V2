# PG-04.04 — Safe Atomic JPEG Filesystem Export Contract

Date: 2026-10-04  
Status: implementation committed; manual delta verification required before V.

## Purpose

PG-04.04 takes the already verified JPEG bytes from PG-04.03 and publishes them safely to a user-selected filesystem destination.

It does not change JPEG color/metadata/quality semantics.

## Destination boundary

- JPEG output must be outside the tracked source Event folder.
- The source Event tree is never used as an export destination.
- The source relative directory structure is preserved below the selected export root.
- Two source files with the same basename in different Event subfolders therefore remain distinct.

This also prevents exported JPEGs from being rediscovered as new Event sources on a later scan.

## Existing files and duplicate names

Supported collision policies:

- `fail` — default. If the destination exists, export fails and the existing file remains byte-identical.
- `unique` — allocate `name (1).jpg`, `name (2).jpg`, etc.

PG-04.04 deliberately does not provide an overwrite mode. Replacing an arbitrary existing user file is not required to satisfy safe Release-1 export and would widen the data-loss surface.

## Atomic publication

For each file:

1. resolve and validate the separate export destination,
2. hash the source,
3. obtain verified encoded bytes from PG-04.03,
4. write a hidden temporary file in the final destination directory,
5. flush + fsync the temporary file,
6. verify temporary-file SHA-256,
7. recheck that the final name is still free,
8. promote the temporary file with same-filesystem `os.replace`,
9. verify final-file SHA-256,
10. hash the source again.

A success response is returned only after final verification.

Temporary files use the suffix `.prographer-tmp` and are removed on failure.

ProGrapher serializes concurrent exports targeting the same logical path.

## Disk-full and write failures

- ENOSPC / Windows disk-full are classified explicitly as insufficient-storage failures.
- A failed temporary write, fsync or promotion does not return success.
- A failed export cleans its temporary artifact.
- If source bytes change during export, the newly created output is discarded and the operation fails.

## Source integrity

The source JPEG is never opened for writing.

`source_sha256_before == source_sha256_after` is required for success.

The response records the source SHA-256 and output SHA-256.

## API

`POST /api/events/{event_id}/files/{fingerprint}/jpeg-export/write`

Request adds:

- `output_dir`
- `collision_policy: fail | unique`

Response is JSON and is emitted only after durable publication + integrity verification.

## Boundary to PG-04.05

PG-04.05 will freeze reference/golden render cases and measure preview-vs-export agreement after actual JPEG encoding.
