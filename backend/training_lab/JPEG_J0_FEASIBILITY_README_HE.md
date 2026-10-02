# JPEG Brain J0 — Edit Representation Feasibility

המטרה של J0 היא **לא לאמן עדיין מוח שחוזה עריכה לתמונה חדשה**.

הניסוי עונה קודם על השאלה הבסיסית:

> האם ייצוג JPEG קומפקטי וגלובלי מסוגל לשחזר בצורה טובה את העריכה הסופית של הצלם כאשר ידועים גם ה־Original וגם ה־Edited?

אם הייצוג עצמו אינו מסוגל לשחזר את עריכת הצלם, אין טעם לאמן מודל שינסה לחזות אותו.

## מה J0 עושה

לכל זוג ב־`manifest.json`:

1. קורא את JPEG המקור.
2. קורא את JPEG הערוך של הצלם.
3. בודק geometry.
4. מתאים טרנספורמציית צבע/טון גלובלית קטנה:
   `quadratic_rgb_polynomial`.
5. שומר Recipe נפרד לזוג.
6. מייצר JPEG משוחזר.
7. מודד את המשוחזר מול ה־JPEG של הצלם.
8. יוצר השוואה:
   `ORIGINAL | PHOTOGRAPHER | J0 RECONSTRUCTION`.

ההתאמה משתמשת ב־pixel holdout פנימי: חלק מהפיקסלים משמשים להתאמת ה־Recipe וחלק אחר למדידת השגיאה.

## מה J0 לא עושה

- אין כאן Brain מאומן.
- אין prediction על תמונה שלא נראתה.
- אין Lightroom sliders מומצאים.
- אין טענת איכות.
- אין שינוי בקובצי המקור.
- אין כתיבה למסלול production.

זהו ניסוי Research בלבד.

## הרצה עם מאגר ה־JPEG הנוכחי

מהתיקייה:

```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER V2\backend"
```

הרצה:

```powershell
python training_lab\jpeg_j0_feasibility.py --manifest "C:\Users\Matann\AppData\Local\ProGrapher\testing_datasets\c437d6d1a583721b53495699\manifest.json" --output "C:\Users\Matann\Desktop\jpeg_j0_results"
```

לבדיקה מהירה על 3 זוגות בלבד:

```powershell
python training_lab\jpeg_j0_feasibility.py --manifest "C:\Users\Matann\AppData\Local\ProGrapher\testing_datasets\c437d6d1a583721b53495699\manifest.json" --output "C:\Users\Matann\Desktop\jpeg_j0_results_smoke" --limit 3
```

## תוצרים

בתיקיית ה־output:

```text
summary.json
results.csv
contact_sheet.jpg

recipes/
  001_..._recipe.json

reconstructions/
  001_..._j0.jpg

comparisons/
  001_..._compare.jpg
```

### contact_sheet.jpg

זה הקובץ החשוב ביותר לבדיקה הראשונה.

כל שורה מציגה:

```text
ORIGINAL | PHOTOGRAPHER | J0 RECONSTRUCTION
```

צריך להסתכל בעיקר על:

- חשיפה כללית
- white balance / color cast
- skin tones
- contrast
- blacks / highlights
- saturation
- האם האווירה הכללית נשמרה
- איפה יש הבדלים מקומיים שה־Recipe הגלובלי לא מצליח לייצג

## מדדים

`summary.json` ו־`results.csv` כוללים:

- `baseline_mae_255` — ההפרש Original → Photographer ללא עריכה.
- `reconstruction_mae_255` — ההפרש J0 → Photographer.
- `reconstruction_rmse_255`.
- `reconstruction_p95_abs_255`.
- `reconstruction_luma_mae_255`.
- `reconstruction_psnr_db`.
- `mae_improvement_fraction`.

המדדים אינם לבדם שער קידום. צריך לבדוק גם את התמונות בעין.

## איך מפרשים את הניסוי

### אם J0 קרוב מאוד לעריכת הצלם

זה אומר שהייצוג הגלובלי מספיק חזק כדי להצדיק את הניסוי הבא:

```text
Original JPEG
    ↓
Features / Encoder
    ↓
Predict JPEG Recipe
    ↓
Apply Recipe
    ↓
Compare to held-out Photographer Edit
```

זה יהיה JPEG Brain J1.

### אם J0 עדיין רחוק

לא מתחילים אימון.

בודקים מה חסר בייצוג:

- Tone curve עשירה יותר
- HSL / selective color
- 3D LUT
- local contrast
- local / semantic corrections

ומייצרים Candidate representation חדש.

## עיקרון חשוב

כל גרסת JPEG Recipe נשמרת כמועמד השוואה.

לא מחליפים Recipe או Brain רק כי החדש מורכב יותר.
הוא מתקדם רק אם הוא משפר reconstruction ובהמשך prediction על Validation/Test נפרדים.
