# PG-04.04 — Safe Atomic JPEG Filesystem Export Report

Date: 2026-10-04  
Status: **◐ IMPLEMENTED / VERIFICATION PENDING**

## Implemented

- separate-folder filesystem export,
- preservation of source relative directories,
- duplicate basename handling through directory preservation,
- existing-file `fail` policy,
- non-destructive `unique` naming policy,
- no arbitrary overwrite mode,
- temporary same-directory write,
- flush + fsync,
- temporary and final SHA-256 verification,
- atomic final promotion,
- disk-full classification,
- temporary cleanup after failures,
- source hash before/after,
- discard output if source changes,
- JSON write API.

## Verification required

Run the PG-04.04 targeted delta tests for:

- duplicate basenames in different source folders,
- existing-file fail + unique behavior,
- export-root isolation,
- simulated disk full,
- simulated promotion failure,
- API success/conflict,
- source byte identity.

No hosted GitHub Actions run should be consumed merely for convenience while the monthly allowance is exhausted.
