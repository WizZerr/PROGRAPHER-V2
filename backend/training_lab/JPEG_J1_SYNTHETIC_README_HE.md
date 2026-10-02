# JPEG Brain J1 — Synthetic Recipe Prediction

J1 הוא הניסוי הראשון שבו יש **מודל מאומן** שמנסה לחזות JPEG Recipe מתמונה שלא שימשה לאימון.

המטרה היא עדיין הנדסית בלבד:

> לוודא ששרשרת `JPEG → Features → Model → Predicted Recipe → Render → Evaluation`
> עובדת מקצה לקצה ויודעת להכליל לאירועים סינתטיים שלא שימשו לאימון.

זה עדיין **לא** מבחן איכות של סגנון צלם אמיתי.

## מה המודל לומד

הקלט הוא סט Features מדידים מתוך JPEG:

- ממוצעי RGB
- סטיות תקן RGB
- אחוזוני luminance
- contrast / luma spread
- saturation
- clipping בהירים
- shadow fraction
- warmth
- green-magenta balance

הפלט הוא delta של ה־`quadratic_rgb_polynomial` Recipe של J0.

כלומר:

```text
JPEG
  ↓
Measured Features
  ↓
Small Ridge Regressor
  ↓
Predicted J0 Recipe
  ↓
Renderer
  ↓
Predicted Edited JPEG
```

## חלוקת הנתונים

החלוקה נעשית לפי **אירועים שלמים**, לא לפי תמונות אקראיות:

- 8 אירועי Train
- 2 אירועי Validation
- 2 אירועי Test נעולים

ברירת המחדל היא 18 תמונות לכל אירוע:

- Train: 144
- Validation: 36
- Test: 36

אירועי Test אינם משמשים לאימון המשקלים.

## Baselines

J1 מושווה לשני קווי בסיס:

1. **No Edit** — להשאיר את ה־JPEG המקורי ללא שינוי.
2. **Mean Recipe Baseline** — להפעיל את ה־Recipe הממוצע שנלמד רק מ־Train על כל תמונה.

המטרה היא להראות שהמודל לומד תגובה **תלויה בתמונה**, ולא רק ממוצע סגנון קבוע.

## הרצה

```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER V2\backend"

python training_lab\jpeg_j1_synthetic_brain.py --output "C:\Users\Matann\Desktop\jpeg_j1_synthetic" --clean
```

## תוצרים

```text
jpeg_j1_synthetic/
├── summary.json
├── validation_results.csv
├── test_results.csv
├── validation_contact_sheet.jpg
├── test_contact_sheet.jpg
├── dataset/
│   ├── dataset_manifest.json
│   ├── originals/
│   └── ground_truth/
├── model/
│   ├── j1_model.npz
│   └── model_contract.json
├── validation/
└── test/
```

### test_contact_sheet.jpg

כל שורה:

```text
ORIGINAL | GROUND TRUTH | J1 PREDICTION | MEAN BASELINE
```

זה מאפשר לראות האם J1 באמת מגיב לתמונה טוב יותר מ־Recipe ממוצע.

## Gate סינתטי

Validation עובר אם:

- median J1 MAE קטן מ־65% מ־Mean Recipe baseline
- וגם השיפור החציוני מול No Edit הוא לפחות 75%

Test נעול עובר אם:

- median J1 MAE קטן מ־70% מ־Mean Recipe baseline
- וגם השיפור החציוני מול No Edit הוא לפחות 70%

Gate כזה הוא **בדיקת sanity של pipeline בלבד**.

PASS אינו אומר שהמוצר יודע לערוך חתונה אמיתית או לחקות צלם אמיתי.

## למה זה חשוב

אם J1 עובר, הוכחנו לפני הגעת החומר המקצועי שהרכיבים הבאים עובדים יחד:

- Dataset versioned
- Event-level split
- Feature extraction
- Train-only normalization
- Model fitting
- Model artifact
- Inference
- Recipe reconstruction
- JPEG renderer
- Baseline comparison
- Validation
- Locked Test
- Visual contact sheet

כשהחומר האמיתי יגיע, נוכל להחליף את ה־Synthetic Ground Truth בזוגות אמיתיים ולא להתחיל לבנות את כל תשתית הלמידה מאפס.

## מה J1 לא מוכיח

- לא Photographer Adapter אמיתי.
- לא DINOv3/CLIP.
- לא Scene Context.
- לא local edits.
- לא retouching.
- לא General Model.
- לא איכות אנושית.
- לא 70%–80% חיסכון.

אלה ייבדקו רק על חומר מקצועי מייצג ובאירועים שלא נכנסו לאימון.
