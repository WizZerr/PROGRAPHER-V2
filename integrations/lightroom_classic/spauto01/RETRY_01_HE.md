# SP-AUTO-01 — ניסיון שני מבודד לאחר אבחון Reset

**למחקר בלבד.** אין להריץ שוב את המשימה שנכשלה על `SP_01_OFFLINE_PROOF`. הקטלוג הישן ותיקיית `SP_01_AUTO_BRIDGE` שלו נשארים ללא שינוי. הניסוי השני משתמש ב-`SP_01_AUTO_RETRY_01`.

## למה זה נחוץ

מ־History של ה־Virtual Copy שנוצרה בפועל:
- `Create Virtual Copy` נרשם
- `Reset Crop` נרשם
- לא הופיע שלב `Reset Settings`
- Basic: Exposure=-0.60, Highlights=-41, Shadows=+50, Blacks=-13

הפלט הקודם: `status=error; stage=develop_reset; RESET_READBACK_FAILED`. הנתונים מצביעים על Reset כללי שלא השפיע, אך לא מוכיחים את הסיבה. Adobe מתעדת תלות במודול Develop ויש תיעוד קהילתי למצבי Race בתזמון של בחירת התמונה והאיפוס.

**תיקון SP-AUTO-01 RETRY:** ה־Bridge דורשת כעת שממשק Develop ידווח **שני פרמטרים** (Exposure, Highlights) התואמים ל־Develop של ה־Virtual Copy לפחות שלוש פעמים רצופות. היא קוראת `resetAllDevelopAdjustments()` רק לאחר מכן, ומחכה עד 12 שניות לשינוי אמיתי ב־Develop fingerprint. אם לא חל שינוי: `SPAUTO_RESET_NO_DEVELOP_CHANGE_AFTER_12S`, ועוצרים ללא Export. אם יש שינוי אבל ערכים לא מאומתים: `SPAUTO_RESET_NONZERO_EXPOSURE_REQUIRES_BASELINE_POLICY`; אין אימון.

## שלב 1 — רק עם Lightroom סגורה לחלוטין

הרץ את הקטע הבא ב־Windows PowerShell. אין להפעיל `git pull` או `git reset` בתיקיית הפרויקט שלך.

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$review = Join-Path $env:TEMP "ProGrapher_SPAUTO01_Review"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"

if (Get-Process | Where-Object { $_.ProcessName -match "Lightroom" }) {
    throw "Close Lightroom Classic completely before cloning the research catalog."
}
if (-not (Test-Path -LiteralPath $review -PathType Container)) {
    throw "Previous research worktree missing."
}
if (git -C $review status --porcelain) {
    throw "Research worktree has uncommitted changes: STOP."
}

git -C $repo fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git -C $review switch --detach origin/feature/sp-auto-01-neutral-bridge
if ($LASTEXITCODE -ne 0) { throw "Research checkout failed" }

$old = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m pytest -q -rs `
        (Join-Path $review "backend\tests\test_sp_auto01_neutral_bridge.py") `
        (Join-Path $review "backend\tests\test_sp_auto01_retry_setup.py")
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: do not clone" }

    & $python -m app.lightroom_bridge.sp_auto01_retry_setup clone --research-consent
    if ($LASTEXITCODE -ne 0) { throw "Clone failed: do not reopen until reviewed" }
}
finally { $env:PYTHONPATH = $old }

$private = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private\SP_01_Catalog_Test"
$retryCatalog = Join-Path $private "SP_01_AUTO_RETRY_01\SP_01_AUTO_RETRY_01.lrcat"
if (-not (Test-Path -LiteralPath $retryCatalog -PathType Leaf)) {
    throw "Cloned catalog missing"
}
Write-Host "RETRY CATALOG READY" -ForegroundColor Green
```

## שלב 2 — הכנת Lightroom לבדיקה החדשה (בלי Job עדיין)

1. פתח רק את `SP_01_AUTO_RETRY_01.lrcat`.
2. בדוק שמתחת להיסטוגרמה כתוב **Smart Preview** בלבד. התיקייה `ללא ערוך_HIDDEN_TEST` נשארת מוסתרת; אין לשנות את RAW המקורי או את תיקייתו.
3. ב־File > Plug-in Manager: **Disable** את תוסף `ProGrapher SP-AUTO-01 — Research ONLY` הישן וסגור/פתח מחדש את Lightroom אם התוסף עדיין נטען מ־Lua cache. Enable מאותה תיקיית plug-in לאחר עדכון הקוד בחשבון ה־worktree. תפריט `Library > Plug-in Extras > SP-AUTO-01 Research Bridge Status`.
4. הסטטוס הצפוי: `Authorized research catalog open: true`; `Job state: NO JOB PREPARED`.

**עצור כאן ושלח רק את הסטטוס. אל תריץ עדיין `prepare`.** בריצה הבאה נוודא שאין שום Job ישן, ואז נפעיל פעם אחת באופן אוטומטי.

## מה לא נחשב הצלחה

- יצירת VC לבדה אינה הוכחת Reset.
- Reset Crop לבדו אינו הוכחת איפוס Develop.
- שוויון Exposure=0 לבדו לא מוכיח קלט נטול עריכת צלם.
- ייצוא הצליח ≠ target leakage PASS.
- תהליך זה אינו מאמן את Brain ואינו תומך בקטלוג לקוח אמיתי.
