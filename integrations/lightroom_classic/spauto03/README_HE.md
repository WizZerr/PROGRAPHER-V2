# SP-AUTO-03 — VC-only counterfactual source-leakage research

Strictly private Windows Lightroom Classic research; no training, no production catalogs, no original RAW modifications. Parent: SP-AUTO-02 PR #6.

## What this experiment proves (if PASS)

- One authorized disposable catalog with exactly ONE offline master and no prior virtual copies.
- Capture original master full Develop fingerprint; create two new unique virtual copies A and B from same master.
- Apply deliberate, logged Exposure and Highlights perturbation to VC B ONLY (using Lightroom SDK withWriteAccessDo). Confirm committed readback; recheck unchanged master.
- Export P from perturbed B before Reset. Then reset the two VCs separately with verified Develop UI/controller synchronization; reset crop; require Exposure near zero and no crop.
- Compare FULL serialized Develop setting fingerprints after reset (not just Exposure). Export A and B separately with identical JPEG/sRGB settings.
- Python verifies 3 unique JPEG paths, offline master, Smart Preview, unique IDs, unchanged master, guard flags, and zero decoded RGB difference A vs B. P must show nonzero decoded RGB difference vs A. Exact equality required for pass.

**Scientific scope:** PASS shows VC-only counterfactual reset-render invariance on one Smart Preview. It cannot show whether historic adjustments were baked into Smart Preview at generation time, whether every custom Camera Default/AI mask is clean, or RAW-linear equivalence. training_ready=false regardless of outcome.

## Preparation: Lightroom completely CLOSED

Update detached Windows review worktree to origin/feature/sp-auto-03-input-independence. Run synthetic tests in backend/tests/test_sp_auto03_input_independence.py plus regression suite test_sp_auto02_one_command.py. ONLY if tests pass, use the clone helper with --leakage-clone:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (Get-Process | Where-Object { $_.ProcessName -match "Lightroom" }) { throw "CLOSE LIGHTROOM COMPLETELY" }
if (git -C $review status --porcelain) { throw "Worktree has changes; STOP" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-03-input-independence
if ($LASTEXITCODE -ne 0) { throw "Switch failed" }
$prior = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs `
    (Join-Path $review "backend\tests\test_sp_auto03_input_independence.py") `
    (Join-Path $review "backend\tests\test_sp_auto02_one_command.py")
  if ($LASTEXITCODE -ne 0) { throw "Synthetic tests failed; NO CLONE" }
  & $python -m app.lightroom_bridge.sp_auto01_retry_setup clone --research-consent --leakage-clone
  if ($LASTEXITCODE -ne 0) { throw "Research clone failed" }
}
finally { $env:PYTHONPATH = $prior }
Write-Host "SP-AUTO-03 CATALOG READY" -ForegroundColor Green
```

Source: SP_01_AUTO_RETRY_01 (known research master and Smart Preview, old job preserved); new isolated catalog: SP_01_AUTO_LEAK_01. No RAW, prior exports or prior job files are copied. Existing output destination never overwritten. Source catalog must be CLOSED. The Lightroom worker independently rejects non-single-master or preexisting VCs.

## One-time Lightroom preflight after safe clone

1. Lightroom Classic -> File > Open Catalog -> Documents/ProGrapher_Research_Private/SP_01_Catalog_Test/SP_01_AUTO_LEAK_01/SP_01_AUTO_LEAK_01.lrcat
2. Exactly ONE original master image; histogram must show Smart Preview ONLY, never Original or Original+Smart Preview.
3. File > Plug-in Manager: ADD the NEW separate plug-in from %TEMP%/ProGrapher_SPAUTO01_Review/integrations/lightroom_classic/spauto03/ProGrapherCounterfactual.lrdevplugin. Do NOT overwrite the working SP-AUTO-01 plug-in.
4. Library > Plug-in Extras > SP-AUTO-03 Counterfactual Status (Read-Only): exact catalog=true, Job state=NO JOB PREPARED.
5. CLOSE status modal with OK. No manual reset/export/VC creation. Stop and report status BEFORE issuing the one-shot job.

## After successful status preflight, ONE experiment command

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$work = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_LEAK_01\SP_03_BRIDGE"
if (Test-Path $work) { throw "Existing SP03 job; NO RETRY" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m app.lightroom_bridge.sp_auto03 run --research-consent --offline-smart-preview-confirmed
  $exitCode = $LASTEXITCODE
  Write-Host "SP-AUTO-03 EXIT CODE: $exitCode"
  if ($exitCode -ne 0) { throw "Research stopped, NEVER RETRY SAME JOB" }
  Get-Content -LiteralPath (Join-Path $work "SP03_AGGREGATE.json")
}
finally { $env:PYTHONPATH = $old }
```

Only aggregate JSON can be shared. Private JPEG, master target snapshot, local identifiers and catalog must stay local. If error/timeout, preserve all evidence and do not restart or delete. To verify a completed job again without mutation: `python -m app.lightroom_bridge.sp_auto03 verify --research-consent` with correct PYTHONPATH.

## Safe recovery after first DNG-sensitive clone failure

First Windows trial: 27 synthetic tests PASS, but cloned catalog setup returned a masked ValueError. Root cause strongly indicated by our old blanket RAW-extension guard: Lightroom Smart Previews.lrdata contains legitimate lossy DNG preview blocks.

Patched helper strictly permits .dng ONLY inside the fixed authorized Smart Previews.lrdata; rejects all other original RAW files, symlinks, unexpected staging artifacts, modified source, and differences in byte-level checksums between all source and staged files. It can finalize the existing validated .STAGING directory atomically without deleting, recopying or overwriting any prior experiment.

With Lightroom COMPLETELY CLOSED, and from clean detached worktree:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (Get-Process | Where-Object { $_.ProcessName -match "Lightroom" }) { throw "CLOSE LIGHTROOM" }
if (git -C $review status --porcelain) { throw "Research worktree has changes" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-03-input-independence
if ($LASTEXITCODE -ne 0) { throw "Switch failed" }
$stage = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_LEAK_01.STAGING"
if (-not (Test-Path -LiteralPath $stage -PathType Container)) { throw "STAGING missing: STOP, no clone retry" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs (Join-Path $review "backend\tests\test_sp_auto03_input_independence.py")
  if ($LASTEXITCODE -ne 0) { throw "Tests failed; no finalization" }
  & $python -m app.lightroom_bridge.sp_auto01_retry_setup clone --research-consent --finalize-leakage-staging
  if ($LASTEXITCODE -ne 0) { throw "Staging validation failed; preserve evidence" }
}
finally { $env:PYTHONPATH = $old }
Write-Host "SP-AUTO-03 CATALOG READY" -ForegroundColor Green
```

If staging does not exist or verification fails, STOP and report the sanitized error code. No deletion, no retry, and no changes to Lightroom originals. This command does not issue a Lightroom job. Smart Preview source folder and catalog clone require SHA256 byte-perfect validation.
