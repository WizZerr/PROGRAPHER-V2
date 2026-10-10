# ProGrapher -- surgical learning UI consistency fixes.
# Run after pulling main; preserves locally installed premium JPEG and RAW views.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$training = Join-Path $root 'frontend\src\features\training'
$profileCss = Join-Path $root 'frontend\src\features\profile\ProfileScreen.module.css'
$jpegTsx = Join-Path $training 'JpegTrainingView.tsx'
$jpegCss = Join-Path $training 'JpegTrainingView.module.css'
$rawTsx = Join-Path $training 'RawTrainingView.tsx'
$shared = Join-Path $training 'TrainingBreadcrumbs.tsx'
$sharedCss = Join-Path $training 'TrainingBreadcrumbs.module.css'

foreach ($path in @($profileCss, $jpegTsx, $jpegCss, $rawTsx, $shared, $sharedCss)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Missing file: $path. The original JPEG/RAW UI bundles must be installed first."
  }
}

function Replace-Once([string]$content, [string]$before, [string]$after, [string]$label) {
  if ($content.Contains($after)) { return $content }
  $occurrences = ([regex]::Matches($content, [regex]::Escape($before))).Count
  if ($occurrences -ne 1) {
    throw "Expected exactly one $label anchor; found $occurrences. No files have been changed."
  }
  return $content.Replace($before, $after)
}
function Read-Normalized([string]$path) {
  return [System.IO.File]::ReadAllText($path).Replace(([string][char]13 + [string][char]10), [string][char]10)
}
function Restore-LineEndings([string]$path, [string]$newText) {
  $raw = [System.IO.File]::ReadAllText($path)
  if ($raw.Contains(([string][char]13 + [string][char]10))) {
    return $newText.Replace([string][char]10, ([string][char]13 + [string][char]10))
  }
  return $newText
}

# Preflight: compute every change before writing a single file.
$oldProfile = Read-Normalized $profileCss
$beforeText = @'
.profileHeader,
.coveragePanel,
.learningSurface {
'@
$afterText = @'
.profileHeader,
.coveragePanel {
'@
$newProfile = Replace-Once $oldProfile $beforeText $afterText 'profile grouping border'
$beforeText = @'
.learningSurface {
  display: grid;
'@
$afterText = @'
.learningSurface {
  border: 0;
  box-shadow: none;
  display: grid;
'@
$newProfile = Replace-Once $newProfile $beforeText $afterText 'independent learning panels'

$oldJpegCss = Read-Normalized $jpegCss
$newJpegCss = Replace-Once $oldJpegCss '.arrowCircle svg { transform: rotate(180deg); }' '.arrowCircle svg { transform: none; }' 'JPEG arrow orientation'
$beforeText = @'
  gap: 8px;
  min-width: 0;
  color: #96a2c1;
'@
$afterText = @'
  gap: 9px;
  min-width: 0;
  color: #9eadd1;
'@
$newJpegCss = Replace-Once $newJpegCss $beforeText $afterText 'JPEG breadcrumb visual parity'

$oldJpeg = Read-Normalized $jpegTsx
$beforeText = @'
import styles from "./JpegTrainingView.module.css";
'@
$afterText = @'
import styles from "./JpegTrainingView.module.css";
import TrainingBreadcrumbs from "./TrainingBreadcrumbs";
'@
$newJpeg = Replace-Once $oldJpeg $beforeText $afterText 'JPEG breadcrumb import'
$beforeText = @'
            <div className={styles.crumbs} aria-label="מיקום נוכחי">
              <Glyph name="house" size={20} />
              <span>הפרופיל שלי</span><span className={styles.slash}>/</span>
              <span>בניית פרופיל</span><span className={styles.slash}>/</span>
              <b dir="ltr">JPEG</b>
            </div>
'@
$afterText = @'
            <TrainingBreadcrumbs media="jpeg" className={styles.crumbs} />
'@
$newJpeg = Replace-Once $newJpeg $beforeText $afterText 'JPEG breadcrumb markup'

$oldRaw = Read-Normalized $rawTsx
$beforeText = @'
import styles from "./RawTrainingView.module.css";
'@
$afterText = @'
import styles from "./RawTrainingView.module.css";
import TrainingBreadcrumbs from "./TrainingBreadcrumbs";
'@
$newRaw = Replace-Once $oldRaw $beforeText $afterText 'RAW breadcrumb import'
$beforeText = @'
        <nav className={styles.breadcrumbs} aria-label="מיקום נוכחי">
          <span>הפרופיל שלי</span><span className={styles.chevron}>←</span>
          <span>בניית הפרופיל</span><span className={styles.chevron}>←</span>
          <span>למידה לפי RAW</span>
        </nav>
'@
$afterText = @'
        <TrainingBreadcrumbs media="raw" className={styles.breadcrumbs} />
'@
$newRaw = Replace-Once $newRaw $beforeText $afterText 'RAW breadcrumb markup'

$changes = @(
  @{ Path = $profileCss; Content = $newProfile },
  @{ Path = $jpegCss; Content = $newJpegCss },
  @{ Path = $jpegTsx; Content = $newJpeg },
  @{ Path = $rawTsx; Content = $newRaw }
)
$pending = @($changes | Where-Object { [System.IO.File]::ReadAllText($_.Path) -ne (Restore-LineEndings $_.Path $_.Content) })
if ($pending.Count -eq 0) {
  Write-Host 'Learning UI polish already applied. Nothing changed.' -ForegroundColor Yellow
  exit 0
}
$backupDir = Join-Path $env:TEMP ("ProGrapher-Learning-Polish-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
foreach ($change in $pending) {
  [System.IO.File]::Copy($change.Path, (Join-Path $backupDir [System.IO.Path]::GetFileName($change.Path)), $true)
}
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($change in $pending) {
  [System.IO.File]::WriteAllText($change.Path, (Restore-LineEndings $change.Path $change.Content), $utf8)
  Write-Host ("Updated: " + $change.Path) -ForegroundColor Green
}
Write-Host ("Backups: " + $backupDir) -ForegroundColor Cyan
Write-Host 'Verify in frontend: npm.cmd run lint; npx.cmd tsc --noEmit; npm.cmd run build; npm.cmd run tauri dev'
