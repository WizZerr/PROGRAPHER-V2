# PG-04.04 — Safe Atomic JPEG Filesystem Export Report

Date: 2026-10-04  
Status: **V**

## Implemented

- `backend/app/rendering/jpeg_file_export.py`
- `backend/app/api/routes/jpeg_export.py` write endpoint
- `backend/tests/test_jpeg_file_export.py`
- `docs/PG_04_04_JPEG_FILE_EXPORT_CONTRACT.md`

## Verified behavior

The committed PG-04.04 module was executed in a local integration harness with its external product dependencies stubbed at their public contracts. This avoids consuming hosted GitHub Actions minutes while still executing the exact committed filesystem-export implementation.

PASS:

- normal atomic publish,
- stable POSIX-form response relative paths across platform conventions,
- source relative directory preservation,
- duplicate basenames remain distinct through relative folders,
- existing destination with `fail` is rejected without replacement,
- `unique` allocates a new filename,
- export inside the tracked Event tree is rejected,
- disk-full during fsync is classified and leaves no final/temp artifact,
- promotion failure leaves no final/temp artifact,
- post-promotion verification failure removes the unverified final artifact,
- source mutation during export is detected and the new output is discarded,
- successful and failed flows preserve the source when the source itself is not externally modified,
- API route source compiles syntactically.

The immediate renderer/export baseline is PG-04.02–04.03, already verified before this Part.

Hosted Actions was not triggered because the monthly hosted-runner allowance is exhausted.

## Safety decisions

PG-04.04 deliberately exposes no arbitrary overwrite mode.

Collision policies are:

- `fail` — safe default,
- `unique` — preserve existing file and allocate a suffix.

This keeps existing user files outside the data-loss surface.

## Result

PG-04.04 is **V**.

Next executable Part: **PG-04.05 — reference/golden JPEG renders**.
