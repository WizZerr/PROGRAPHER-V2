# SP-AUTO-01 — verified Lightroom JPEG to local source-only AI

Current status: user verified one autonomous Lightroom Smart Preview export (Python verify exit 0). This postprocess is READ-ONLY: it does not send a new Lightroom job, modify catalog, create Virtual Copies, reset or export images.

Windows PowerShell from existing project; updates ONLY the disposable detached review worktree:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $review -PathType Container)) { throw "Review worktree missing" }
if (git -C $review status --porcelain) { throw "Review worktree contains changes" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-01-neutral-bridge
if ($LASTEXITCODE -ne 0) { throw "Research checkout failed" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs (Join-Path $review "backend\tests\test_sp_auto01_postprocess.py")
  if ($LASTEXITCODE -ne 0) { throw "Synthetic postprocess tests failed" }
  & $python -m app.lightroom_bridge.sp_auto01 verify --research-consent
  if ($LASTEXITCODE -ne 0) { throw "Previous Lightroom bridge job no longer verifies" }
  & $python -m app.lightroom_bridge.sp_auto01_postprocess --research-consent --run-scene-ai
  if ($LASTEXITCODE -ne 0) { throw "Postprocess failed; do not retry without inspection" }
}
finally { $env:PYTHONPATH = $old }
```

The local CLIP model must already be cached; no download option. Produces source-only JPEG technical features and human-reviewable zero-shot scene diagnostics. No photographer Develop target is sent to CLIP, training_ready is always false.

Local output is under SP_01_AUTO_RETRY_01/SP_01_AUTO_BRIDGE/SP_01_AUTO_ANALYSIS:
- AUTO_ANALYSIS_PRIVATE.json: source path and hashes, target fingerprint/photo identities, pixel metrics, scene ranking — KEEP LOCAL and do not share.
- AUTO_ANALYSIS_AGGREGATE.json: no photo IDs, filenames, relative scene labels, or photographer Develop. Review locally before sharing.

Even a success establishes only postprocessing of the verified automatic JPEG, not independent photographer-target leakage prevention, source RAW equivalence, broad catalog support, or a production UI. Do not re-run analysis if its output folder exists; do not re-run prepare.
