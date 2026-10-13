# SP-AUTO-01 — Lightroom Smart Preview Bridge (research only)

## What is now implemented

**Goal:** once the photographer opens the authorized *disposable* research catalog, ProGrapher sends ONE local `EXTRACT_NEUTRAL_SMART_PREVIEW` task. The enabled Lightroom SDK plug-in polls the authorized local research folder, identifies the *only master photo* in that catalog, saves its original Develop settings, **creates a Virtual Copy automatically**, switches Lightroom to that exact copy in Develop, calls official SDK Reset + crop reset if needed, exports a neutral JPEG from the offline Smart Preview, and writes a terminal result. No manually created Virtual Copy, Reset, or Export is required by this experiment.

**This is experimental**, not Windows/Lightroom-validated yet, and definitely not production-safe for other catalogs. The disposable catalog is deliberately modified (one extra VC per attempted job); the master Develop is only read and its complete serialized snapshot compared before/after. No rollback or automatic retries; failures can leave a partial VC. Work *only on this test catalog.* Neutrality independent of historical edited targets remains NOT PROVEN; training-ready is always zero.

Verified SDK building blocks used by the experiment: `LrCatalog:createVirtualCopies` (async, selects new copies), `LrCatalog:setSelectedPhotos`, `LrApplicationView.switchToModule`, `LrDevelopController.resetAllDevelopAdjustments` (Develop module only), `LrDevelopController.resetCrop`, `LrPhoto:getRawMetadata('smartPreviewInfo')`, `LrPhoto:getDevelopSettings`, `LrExportSession`. Version/runtime caveats remain; success must be observed on Windows.

## Step 1 — Python contract tests in a NEW detached worktree

Run this in PowerShell. Do not reset, clean, pull or checkout the user's main working folder:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"

if (Test-Path $review) { throw "Existing review folder; do not overwrite" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $repo worktree add --detach $review origin/feature/sp-auto-01-neutral-bridge
if ($LASTEXITCODE -ne 0) { throw "Worktree creation failed" }

$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m pytest -q -rs `
        (Join-Path $review "backend\tests\test_sp_auto01_neutral_bridge.py") `
        (Join-Path $review "backend\tests\test_sp01_smart_preview_analysis.py")
    if ($LASTEXITCODE -ne 0) { throw "SP-AUTO-01 synthetic tests failed" }
}
finally { $env:PYTHONPATH = $old }
```

These tests do NOT start or modify Lightroom, do not access real RAWs, and do not load CLIP.

## Step 2 — one isolated automatic Lightroom run (ONLY after Step 1 passed)

Preconditions: `SP_01_OFFLINE_PROOF.lrcat` is the **disposable copied** test catalog, with exactly ONE non-virtual master and an existing matching `SP_01_OFFLINE_PROOF Smart Previews.lrdata`. The temporary test-original folder stays renamed to `ללא ערוך_HIDDEN_TEST`; source is unavailable and Lightroom should show `Smart Preview`, NOT `Original + Smart Preview`. No originals, live catalog, or other user folders may be renamed or modified. Photographic research permission remains required.

1. Open **only** `SP_01_OFFLINE_PROOF.lrcat` in Lightroom.
2. Lightroom > File > Plug-in Manager > Add, select the **new** plug-in directory from the *isolated review worktree*:
   `$review\integrations\lightroom_classic\spauto01\ProGrapherAutoNeutral.lrdevplugin`
   Confirm enabled. This new research plug-in starts a background poller on load and stays inert unless a job is prepared and the exact authorized catalog is open.
3. On PowerShell, run the following. This command creates **one** job. No photo selection or manually-triggered Lightroom menu command is required:

```powershell
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m app.lightroom_bridge.sp_auto01 prepare --research-consent
    if ($LASTEXITCODE -ne 0) { throw "Job preparation failed; stop" }
}
finally { $env:PYTHONPATH = $old }
```

4. Wait for Lightroom to execute the job (the plug-in polls every 3 seconds). It may switch temporarily to Develop. This is part of the experiment: **do not manually create a VC, reset, or export**. Once work stops, run:

```powershell
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m app.lightroom_bridge.sp_auto01 verify --research-consent
    $verifyExit = $LASTEXITCODE
}
finally { $env:PYTHONPATH = $old }
Write-Host "SP-AUTO-01 verify exit: $verifyExit"
```

If verification says `NOT_COMPLETE_PREPARED` the worker has not started; `NOT_COMPLETE_RUNNING` means it is ongoing or interrupted; `NOT_COMPLETE_ERROR` means it failed and MUST NOT be retried against the same research catalog/workdir without inspection. **Never delete any research evidence or job to force a retry.**

If verification fails, share ONLY non-sensitive diagnostic fields:

```powershell
$folder = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_OFFLINE_PROOF\SP_01_AUTO_BRIDGE"
$state = @{}
Get-Content (Join-Path $folder "result.txt") | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { $state[$matches[1]] = $matches[2] }
}
[PSCustomObject]@{
    Status = $state.status
    Stage = $state.stage
} | Format-List
```

**Do not share** `job.txt`, private master target snapshot, JPEG, catalog, job IDs, private paths, or error text (the error may contain paths). No "PASS" claim until Lightroom actually completes and Python `verify` returns success.

## Safety / scope / next engineering

- Python protocol: `backend/app/lightroom_bridge/sp_auto01.py`; Lightroom plug-in: `integrations/lightroom_classic/spauto01/ProGrapherAutoNeutral.lrdevplugin/`.
- No GUI button yet; the Python `prepare` command is the equivalent of what ProGrapher's future UI will dispatch.
- Auto-worker is enabled only for the exact one-photo `SP_01_OFFLINE_PROOF` research catalog. It refuses an online original and refuses a catalog without a Smart Preview.
- The raw source is not touched. The *disposable test catalog* gains a Virtual Copy, which remains for forensic inspection; no automatic cleanup.
- Original Lightroom Develop is snapshotted privately before the VC is created; full nested settings are serialized for provenance but not claimed as supported model targets. Further validation needed for masks/profile/processing defaults and unchanged master.
- There is **no guarantee** that Reset removes historical influence or that pixel values reconstruct camera RAW. Camera/Smart Preview baseline settings and Adobe rendering may still influence the neutral JPEG.
- Run one job only. Multi-job queue, recovery, restart, customer UI, restore/cleanup and leak-proof training-pair validation belong to later Parts.
- Do not merge this branch into `main` until Windows pytest, Lua plug-in runtime, JPEG export and baseline/target-separation evidence are all reviewed.
