# SP-AUTO-02 — one-command real research test (Hebrew)

**Goal:** One command after opening the authorized fresh test catalog. Bridge automatically creates a VC, resets Develop/crop on the VC, exports sRGB JPEG from offline Smart Preview, validates job + readback, analyzes JPEG and CLIP, compares with manual neutral reference and inspects JPEG encoding. Master original Develop remains unchanged. Zero training.

**IMPORTANT:** The photographer deleted old VCs. An old successful job is still recorded in SP_01_AUTO_RETRY_01/SP_01_AUTO_BRIDGE; NEVER delete/edit/replay it. Clone the CLEANED research catalog to a new uniquely allowed disposable catalog before issuing a new job. This workflow assumes the VC cleanup took place in SP_01_AUTO_RETRY_01 (confirm with user). The worker will refuse a source containing more than one photo, including VCs.

## A. One-time safe setup — Lightroom Classic must be fully CLOSED

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (Get-Process | Where-Object { $_.ProcessName -match "Lightroom" }) { throw "Close Lightroom Classic completely" }
if (-not (Test-Path -LiteralPath $review -PathType Container)) { throw "Review worktree not found" }
if (git -C $review status --porcelain) { throw "Worktree has user changes; STOP" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-02-one-command
if ($LASTEXITCODE -ne 0) { throw "Worktree switch failed" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs `
    (Join-Path $review "backend\tests\test_sp_auto02_one_command.py") `
    (Join-Path $review "backend\tests\test_sp_auto01_neutral_bridge.py")
  if ($LASTEXITCODE -ne 0) { throw "Tests failed; do not create new catalog" }
  & $python -m app.lightroom_bridge.sp_auto01_retry_setup clone --research-consent --e2e-clone
  if ($LASTEXITCODE -ne 0) { throw "Safe catalog clone failed" }
}
finally { $env:PYTHONPATH = $old }
Write-Host "SP-AUTO-02 NEW RESEARCH CATALOG READY" -ForegroundColor Green
```

The clone copies `.lrcat`, `Smart Previews.lrdata`, optional `.lrcat-data`, and NEVER previous bridge job/results, exports, or negative/RAW files. It does not overwrite existing destination, and preserves source catalog. Output:

`C:\Users\Matann\Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_E2E_01\SP_01_AUTO_E2E_01.lrcat`

## B. One-time open + preflight

1. Restart Lightroom Classic and open the **new** SP_01_AUTO_E2E_01.lrcat only.
2. Select the sole **original master** and confirm histogram reads `Smart Preview` **without** `Original`. Keep the physical copied RAW hidden; do not touch photographer original RAWs.
3. Lightroom Plug-in Manager must show `ProGrapher SP-AUTO-01 — Research ONLY` enabled from the updated review worktree (restart Lightroom after code fetch to avoid stale Lua module cache).
4. Library > Plug-in Extras > SP-AUTO-01 Research Bridge Status must show `Authorized research catalog open: true` and `Job state: NO JOB PREPARED`. **Click OK to close the dialog**. A modal can postpone bridge processing.
5. Do not manually create a VC, Reset or Export. Do not run a second command while this job is underway.

## C. ONE run command — dispatch + verify + local CLIP + comparison + forensics

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m app.lightroom_bridge.sp_auto02_one_command run `
    --research-consent `
    --smart-preview-only-confirmed `
    --same-photo-manual-reference-confirmed
  $exitCode = $LASTEXITCODE
  Write-Host "SP-AUTO-02 EXIT CODE: $exitCode"
  if ($exitCode -ne 0) { throw "Pipeline stopped: DO NOT RETRY; inspect research state" }
}
finally { $env:PYTHONPATH = $old }
```

Command uses cached CLIP without downloads. It creates exactly one new local job and waits up to 180 seconds. It does not automatically retry after a timeout; if the modal is open, close it but NEVER dispatch a new job. If error/timeout, preserve local `SP_01_AUTO_BRIDGE` job folder and report only anonymized `status`/`stage` fields. No automatic cleanup of VC.

## D. Verification report (no private photos sent)

On success only:

```powershell
$aggregate = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_E2E_01\SP_01_AUTO_BRIDGE\SP01_ONE_COMMAND_AGGREGATE.json"
Get-Content -LiteralPath $aggregate
```

The public aggregate contains no image, filenames, photo IDs, Develop data, or private paths. KEEP all other JSON/TXT/JPEG and Lightroom files local. Report `Training ready: False` until independent anti-leakage, neutral profile policy and photographer target provenance are verified. **One command** automates the pipeline AFTER one-time clone/open setup, but it is research CLI, not a polished app UI. Main remains untouched, PR is DRAFT.
