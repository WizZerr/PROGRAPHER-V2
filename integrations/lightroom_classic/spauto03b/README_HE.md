# SP-AUTO-03B — geometry-controlled Lightroom counterfactual

## Why

SP-AUTO-03 SDK finished (status=ok), generated P/A/B. Final Python verifier rejected P vs A because P was historically cropped (938x1407), while neutral A/B were uncropped (1707x2560). A and B were pixel-perfect identical, 0.0 RGB MAE, and full Develop fingerprints agreed. The P/A comparison was NOT VALID and said nothing about whether Exposure+Highlights perturbation affected pixels.

## Four-stage correction (automatic SDK research only)

- Source: new, never-used `SP_01_AUTO_LEAK_02.lrcat` containing exactly one offline Master and its Smart Preview only, cloned from preexisting CLEAN `SP_01_AUTO_RETRY_01` with Lightroom fully closed.
- A and B: created from SAME Master and must initially share identical full Develop fingerprint, including crop. Master original develop fingerprint verified unchanged at every step.
- `U` = JPEG from untouched VC A BEFORE ANY RESET. Preserves historical crop.
- Perturb VC B Exposure + Highlights using SDK while holding original geometry/crop constant; verify numerical readback. `P` = JPEG from B BEFORE RESET. P must match U dimensions, and differ from U by at least one decoded RGB channel value.
- Reset VC A and VC B separately after SDK Develop controller agrees with selected copy 3 times. Reset crop separately. `A` and `B` = POST-RESET full-size neutral JPEG. Their full serialized Develop readbacks and every decoded RGB pixel must match EXACTLY.
- Strict one-use private workdir `SP_03B_BRIDGE`; results cannot be retried or overwritten. Each JPEG has its own output directory `U/P/A/B`.

**What PASS means**: for one photo, the deliberate same-crop pre-reset editing intervention produced visible pixel differences, and two independent reset paths converged perfectly; master unchanged. A pass is NOT proof that Smart Preview content itself is inherently edit-free, original RAW-linear, or safe for large-scale training. Training remains BLOCKED.

## 1. One-time Windows safety prep — Lightroom MUST BE CLOSED

Use a clean detached review worktree; NEVER update or edit `main`. Run synthetic tests before cloning:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (Get-Process | Where-Object { $_.ProcessName -match "Lightroom" }) { throw "CLOSE LIGHTROOM COMPLETELY" }
if (git -C $review status --porcelain) { throw "Research worktree has changes" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-03-crop-controlled-retry
if ($LASTEXITCODE -ne 0) { throw "Checkout failed" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs `
      (Join-Path $review "backend\tests\test_sp_auto03b_crop_control.py") `
      (Join-Path $review "backend\tests\test_sp_auto03_input_independence.py") `
      (Join-Path $review "backend\tests\test_sp_auto02_one_command.py")
  if ($LASTEXITCODE -ne 0) { throw "STOP - synthetic tests failed, no clone" }
  & $python -m app.lightroom_bridge.sp_auto01_retry_setup clone `
      --research-consent --crop-control-clone
  if ($LASTEXITCODE -ne 0) { throw "STOP - preserve clone evidence" }
}
finally { $env:PYTHONPATH = $old }
Write-Host "SP-AUTO-03B RESEARCH CATALOG READY" -ForegroundColor Green
```

## 2. Open new catalog and install NEW isolated plugin

- Open Lightroom Classic -> File -> Open Catalog -> `Documents/ProGrapher_Research_Private/SP_01_Catalog_Test/SP_01_AUTO_LEAK_02/SP_01_AUTO_LEAK_02.lrcat`.
- Verify exactly ONE Master, ZERO VCs, histogram Smart Preview ONLY, not Original.
- Lightroom File -> Plug-in Manager -> Add new folder `%TEMP%/ProGrapher_SPAUTO01_Review/integrations/lightroom_classic/spauto03b/ProGrapherCounterfactualV2.lrdevplugin`.
- Library -> Plug-in Extras -> `SP-AUTO-03B Crop-Controlled Status (Read-Only)` must show `Authorized isolated research catalog: true`, `Job state: NO JOB PREPARED`; CLOSE modal with OK.
- Old SP03 and SP02 plugins/catalogs MUST remain untouched; the new plugin uses unique toolkit ID and only responds to new LEAK_02 catalog.
- Stop and send status screenshot before starting one-shot experiment. Do not manually create/edit/export VCs.

## 3. ONE controlled research run only after status passes

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$work = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_LEAK_02\SP_03B_BRIDGE"
if (Test-Path -LiteralPath $work) { throw "EXISTING JOB: DO NOT RETRY" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m app.lightroom_bridge.sp_auto03b run --research-consent --offline-smart-preview-confirmed
  $exitCode = $LASTEXITCODE
  Write-Host "SP-AUTO-03B EXIT CODE: $exitCode"
  if ($exitCode -ne 0) { throw "STOP: keep evidence, no retry" }
  Get-Content -LiteralPath (Join-Path $work "SP03B_AGGREGATE.json")
}
finally { $env:PYTHONPATH = $old }
```

Failure/timeout leaves artifacts intact. No repeated run in that catalog. Only anonymous QC summary should ever be shared; never upload private JPEG, RAW, Develop targets or local IDs. No model training.
