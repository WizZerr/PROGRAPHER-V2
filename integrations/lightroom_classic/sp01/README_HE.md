# SP-01 — הוראות הרצה מקומיות (מחקר בלבד)

**סטטוס:** רכיבי קוד חדשים, עדיין לא אומתו ב-Lightroom או ב-Windows בסנכרון זה. לא להשתמש על קטלוג צלם אמיתי. `main` לא משתנה.

## 1. בדיקות מקומיות מתוך Worktree מבודד

ב-Windows PowerShell, כאשר התיקייה הראשית `C:\Users\Matann\Desktop\PROGRAPHER V2` נשארת ללא שינוי:

```powershell
$ErrorActionPreference = "Stop"
$repo = "C:\Users\Matann\Desktop\PROGRAPHER V2"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
$review = Join-Path $env:TEMP "ProGrapher_SP01_Review"

Set-Location $repo
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
if (Test-Path -LiteralPath $review) { throw "Review folder already exists; inspect, don't overwrite" }
git worktree add --detach $review origin/feature/sp-01-smart-preview-learning-research
if ($LASTEXITCODE -ne 0) { throw "Worktree creation failed" }

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m pytest -q (Join-Path $review "backend\tests\test_sp01_smart_preview_analysis.py")
    if ($LASTEXITCODE -ne 0) { throw "SP-01 synthetic tests failed" }
}
finally { $env:PYTHONPATH = $oldPythonPath }
```

**הבדיקות סינתטיות בלבד**: לא משתמשות ב-RAW של הצלם, לא מורידות מודל ולא יוצרות פלט ב-Lightroom.

## 2. ניתוח JPEG ניטרלי שכבר הופק ידנית

לאחר מעבר הבדיקות, להשתמש רק ב-JPEG שהופק מ-`SP_01_OFFLINE_PROOF` כשהמקור היה offline ומתחת להיסטוגרמה הופיע `Smart Preview`. לוודא ידנית Export ב-sRGB לאחר Reset על Virtual Copy בקטלוג המחקר.

```powershell
$research = Join-Path $env:USERPROFILE "Documents\ProGrapher_Research_Private"
$jpeg = Join-Path $research "SP_01_Catalog_Test\SP_01_OFFLINE_PROOF\SP_01_OFFLINE_NEUTRAL_EXPORT\0H1A4577.jpg"
$out = Join-Path $research ("SP_01_ANALYSIS_" + (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path -LiteralPath $jpeg -PathType Leaf)) {
    throw "Neutral JPEG not found; update the exact private file path first"
}

$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $review "backend"
try {
    & $python -m app.photographer.smart_preview_analysis `
        --neutral-jpeg "$jpeg" `
        --out-dir "$out" `
        --consent-acknowledged `
        --offline-smart-preview-confirmed `
        --neutral-reset-and-srgb-confirmed
    if ($LASTEXITCODE -ne 0) { throw "Neutral analysis failed" }
}
finally { $env:PYTHONPATH = $oldPythonPath }

Write-Host "Private report: $out"
```

התוצרים בתוך תיקיית המחקר הפרטית בלבד:
- `SP01_ANALYSIS_PRIVATE.json`: נתיב/Hash, מידות ומאפייני JPEG. **לא לשתף**.
- `SP01_AGGREGATE.json`: סיכום מחקר מצומצם. ניתן לשלוח לאחר סקירה אישית.

בריצה זו מסווג AI אינו פועל; `scene.status=AI_NOT_RUN`, והמדדים מתייחסים לתמונה מבוססת **sRGB**, לא לפענוח RAW לינארי.

## 3. להריץ את ה-AI הקיים (רק אחרי שהשלב הקודם עבר)

לפני הרצה לוודא שהתלויות `torch` ו-`transformers` מותקנות ושמשקולות CLIP נמצאות במטמון המקומי. כדי לקבל הצעות לסצנות באותו CLI, ליצור **תיקיית פלט חדשה** ולהוסיף `--run-scene-ai`. ברירת המחדל: אין הורדת משקולות. אם המשתמש אישר במפורש הורדת מודל, ניתן להוסיף `--allow-model-download`; הקוד לא שולח תמונות לרשת.

```powershell
# Example (run with the same other arguments as section 2):
# --run-scene-ai
```

הצעות CLIP הן דירוגים יחסיים בלבד, **לא הסתברויות מכוילות**. ברירת המחדל שלהן דורשת סקירה אנושית; המנגנון אינו מתאמן.

## 4. תוסף Lightroom מחקרי נוסף (ניסוי עתידי בלבד)

מיקום:
`integrations/lightroom_classic/sp01/ProGrapherSmartPreviewResearch.lrdevplugin`

הוא בודק שפתוח בדיוק הקטלוג **`SP_01_OFFLINE_PROOF.lrcat`** במסלול המחקר המאושר, שנבחר רק Virtual Copy אחד שכבר עבר Reset, ושה-RAW offline. הוא מייצא JPEG ל-`SP_01_PLUGIN_EXPORTS` ושומר בו קובץ פרטי עם subset של הגדרות Develop המקוריות מה-Master Photo; אינו משנה Develop ואינו יוצר Virtual Copies. יש ליצור מראש תיקיית `SP_01_PLUGIN_EXPORTS` ריקה. יש לוודא שהנתיב המאושר בקובץ Lua תואם למסלול קטלוג המחקר המקומי לפני הפעלה.

**עדיין לא נבדק ממש ב-Lightroom. לא להתקין אותו על קטלוג עבודה, לא להניח שצילום ה-target מלא, ולא להשתמש במידע לאימון.**

## 5. חסמים והגדרת ההצלחה

- נדרש להוכיח ש-Lua exporter אכן עובד על קטלוג המחקר, ושהתנהגות SDK של VC/metadata תקינה בגרסת Lightroom של המחשב.
- נדרש להוכיח אוטומציה בטוחה ליצירת VC ולנטרול Develop, **ללא שינוי ה-Master**, דרך SDK נתמך; כרגע האדם מבצע את השלבים האלה ידנית.
- נדרש ליצור מבחן עקביות מול שינויי Develop במקור, ולוודא שאין דליפת יעדי הצלם לקלט. צילום JPEG מתוך Smart Preview לא מספיק כדי להכריז זאת.
- צימוד סופי בין Photo UUID, Develop/Crop והקלט טרם עבר בקרה מלאה. אין נתוני אימון מאושרים.

**סיום Part התחלתי:** בדיקות סינתטיות + smoke ניתוח JPEG מקומי + review, לפני מיזוג GitHub.
