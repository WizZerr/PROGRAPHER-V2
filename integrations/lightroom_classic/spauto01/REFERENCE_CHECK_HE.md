# SP-AUTO-01 — auto-export versus manual neutral reference, read-only

Goal: compare the SDK-generated automatic JPEG (from previously VERIFIED one-photo SP-AUTO-01) against the manually generated neutral Smart Preview JPEG for the SAME photo. Both artifacts already exist in private research; no Lightroom operation is performed. The manual reference comes from the original SP_01_OFFLINE_PROOF research session.

This is an **engineering render-equivalence candidate** only. A match does NOT prove the neutral representation is independent of the photographer's edited Develop target, that sensor RAW values were recovered, or that samples are training-ready. A mismatch is an actionable discrepancy but could reflect Lightroom export policy, JPEG resize/crop/profile, or the wrong reference rather than model failure.

## Windows execution

Run with Lightroom allowed to remain open; it is not contacted. Do not prepare a new job, edit catalogs, reset Virtual Copies or reexport JPEG.

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $review -PathType Container)) { throw "Review worktree missing" }
if (git -C $review status --porcelain) { throw "Worktree has local changes" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-01-neutral-bridge
if ($LASTEXITCODE -ne 0) { throw "Worktree switch failed" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs (Join-Path $review "backend\tests\test_sp_auto01_reference_compare.py")
  if ($LASTEXITCODE -ne 0) { throw "Reference comparison tests failed" }
  & $python -m app.lightroom_bridge.sp_auto01 verify --research-consent
  if ($LASTEXITCODE -ne 0) { throw "Prior automatic JPEG no longer verifies" }
  & $python -m app.lightroom_bridge.sp_auto01_reference_compare --research-consent --same-photo-manual-reference-confirmed
  if ($LASTEXITCODE -ne 0) { throw "Reference comparison failed; do not retry without inspection" }
}
finally { $env:PYTHONPATH = $old }
$aggregate = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_RETRY_01\SP_01_AUTO_BRIDGE\SP01_AUTO_REFERENCE_CHECK\AUTO_VS_MANUAL_AGGREGATE.json"
Get-Content -LiteralPath $aggregate
```

Results remain inside the private workdir, no training, no source/target modifications. The aggregate contains only scalar comparison diagnostics, no image pixels, filenames, photo ID or catalog job ID.

The manual reference is hard-coded only for this single authorized proof as SP_01_OFFLINE_PROOF/SP_01_OFFLINE_NEUTRAL_EXPORT/0H1A4577.jpg. If a different file was used for the original proof, stop; do not switch manually to an unknown image or assert same-photo identity. Report the correct private path to the developer without sharing image pixels.
