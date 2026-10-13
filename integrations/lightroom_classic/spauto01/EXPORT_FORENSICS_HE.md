# SP-AUTO-02 — JPEG forensics: automatic versus manually exported neutral preview

Research status: first real Windows comparison completed but NOT pixel-identical: dimensions match; mean absolute decoded 8-bit RGB difference 0.048043; max 5; fraction of pixels exact across all 3 channels 0.948263; byte hashes differ. Tiny pixel residual could reflect JPEG encoder/compression/configuration, or a slight Develop/rendering difference. Cause NOT established.

This new component is READ ONLY and uses the same two already existing private JPEGs. It never contacts Lightroom or modifies the source/master/catalog. It inspects encoded JPEG quantization tables, chroma subsampling, progressive mode, ICC byte equality and EXIF presence (no EXIF contents), and measures signed RGB residuals and blurred residual. Even a match is NOT enough to mark training-ready.

Run in Windows PowerShell:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $review -PathType Container)) { throw "Research worktree missing" }
if (git -C $review status --porcelain) { throw "Uncommitted worktree changes; stop" }
git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-01-neutral-bridge
if ($LASTEXITCODE -ne 0) { throw "Review switch failed" }
$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
  & $python -m pytest -q -rs (Join-Path $review "backend\tests\test_sp_auto02_export_forensics.py")
  if ($LASTEXITCODE -ne 0) { throw "Forensics synthetic tests failed" }
  & $python -m app.lightroom_bridge.sp_auto01 verify --research-consent
  if ($LASTEXITCODE -ne 0) { throw "Existing bridge job no longer verifies" }
  & $python -m app.lightroom_bridge.sp_auto02_export_forensics --research-consent --same-photo-manual-reference-confirmed
  if ($LASTEXITCODE -ne 0) { throw "Forensics failed; do NOT rerun without inspection" }
}
finally { $env:PYTHONPATH = $old }
$report = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test\SP_01_AUTO_RETRY_01\SP_01_AUTO_BRIDGE\SP01_JPEG_ENCODING_FORENSICS\ENCODING_FORENSICS_AGGREGATE.json"
Get-Content -LiteralPath $report
```

Send back only this anonymized aggregate report (no private JSON, image, Lightroom catalog, target, or photo path). Cause-of-residual remains UNKNOWN even if encoding parameters differ; DO NOT adjust model training eligibility or change Develop thresholds based on these measurements alone.

Next gate is an independent controlled master-edit intervention in an isolated copy plus a fully specified neutral renderer/profile/crop/white balance policy. Neither was proven by JPEG forensics.
