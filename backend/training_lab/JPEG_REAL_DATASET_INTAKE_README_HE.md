# ProGrapher — Real JPEG Dataset Intake & Evaluation

המסלול הזה נועד לרגע שבו מגיע חומר אמיתי מהצלם:

```text
JPEG מקור ישר מהמצלמה
        +
אותו JPEG אחרי העריכה הסופית של הצלם
```

המטרה היא לא להתחיל אימון מיד, אלא קודם להבטיח שהחומר:

- מזווג חד־משמעית.
- ניתן לפענוח.
- אינו מערבב אירועים.
- אינו מכניס crop/rotation לא נתמכים בלי שנדע.
- שומר provenance ו־SHA-256 מלא.
- מחולק לפי **אירועים שלמים** ל־Train / Validation / Test.
- נועל את ה־Test כך שלא נתחיל לכוון את המודל מולו.

אין שינוי בקובצי המקור.

---

## מבנה התיקיות

כל אירוע הוא תיקייה נפרדת:

```text
REAL_JPEG_DATASET/
├── wedding_001/
│   ├── ORIGINALS/
│   │   ├── IMG_0001.jpg
│   │   ├── IMG_0002.jpg
│   │   └── ...
│   └── EDITS/
│       ├── IMG_0001.jpg
│       ├── IMG_0002.jpg
│       └── ...
├── wedding_002/
│   ├── ORIGINALS/
│   └── EDITS/
└── wedding_003/
    ├── ORIGINALS/
    └── EDITS/
```

שמות `ORIGINALS` ו־`EDITS` אינם תלויי אותיות גדולות/קטנות, אבל בכל אירוע צריכה להיות בדיוק תיקייה אחת מכל סוג.

הזיווג עצמו משתמש באותו מנגנון pairing של PR1:

1. קודם relative stem.
2. אחר כך filename stem אם הוא חד־משמעי.
3. duplicate/ambiguous names אינם משויכים בשקט.

---

## שלב 1 — Intake

דוגמה:

```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER V2\backend"

python training_lab\jpeg_real_dataset_intake.py --root "C:\Users\Matann\Desktop\REAL_JPEG_DATASET" --output "C:\Users\Matann\Desktop\jpeg_real_intake" --photographer-id "photographer-01"
```

### מה נבדק לכל זוג

- SHA-256 מלא של Original ושל Edited.
- האם זה אותו קובץ פיזי.
- האם ה־bytes זהים לחלוטין.
- האם שני ה־JPEGים ניתנים לפענוח.
- רוחב/גובה.
- שינוי aspect ratio.
- orientation mismatch של 90°.
- האם הזוג מתאים ל־J0 first-pass recipe fitting.

### סטטוסים אפשריים

`usable`

זוג מתאים לניסוי J0 הראשוני.

`unchanged_final`

ה־Original וה־Edited זהים byte-for-byte. המקרה נשמר כי הוא יכול להיות משמעותי בהמשך, אבל אינו משמש כרגע להפקת Recipe target ב־J0.

`crop_or_geometry_mismatch`

יחס התמונה השתנה מעבר לסבילות. נשמר בדוח אבל אינו נכנס אוטומטית ל־J0.

`rotation_mismatch`

נראה כמו שינוי orientation של 90°.

`decode_error` / `read_error`

אחד הקבצים לא ניתן לקריאה/פענוח.

`same_physical_file`

שני הנתיבים מצביעים בפועל לאותו קובץ.

---

## Split Lock

החלוקה נעשית לפי **אירועים שלמים** בלבד.

אם יש לפחות 3 אירועים שימושיים, ההרצה הראשונה יוצרת:

```text
split_lock.json
```

ומחלקת באופן דטרמיניסטי:

```text
Train
Validation
Test
```

עותקים של אותו source ב־splits שונים מזוהים כ־cross-split leakage וחוסמים readiness.

### למה split_lock קיים

אחרי שהתחלנו לפתח מודל אסור ש־Test ישתנה בשקט בגלל שהוספנו אירוע חדש.

לכן:

- assignments קיימים נשמרים.
- אירוע חדש שמגיע אחרי lock קיים הופך ל־`unassigned`.
- כדי לשנות חלוקה צריך פעולה מפורשת עם `--rebuild-split-lock`.

אפשר גם לבחור Validation/Test במפורש בהרצה הראשונה:

```powershell
python training_lab\jpeg_real_dataset_intake.py --root "C:\Users\Matann\Desktop\REAL_JPEG_DATASET" --output "C:\Users\Matann\Desktop\jpeg_real_intake" --photographer-id "photographer-01" --validation-event "wedding_004" --test-event "wedding_005" --rebuild-split-lock
```

כל שאר האירועים השימושיים הופכים ל־Train.

---

## תוצרי ה־Intake

```text
jpeg_real_intake/
├── dataset_manifest.json
├── split_lock.json
├── evaluation_plan.json
├── event_report.csv
├── pair_report.csv
└── j0_manifests/
    ├── train__wedding_001.json
    ├── validation__wedding_004.json
    └── test__wedding_005.json
```

### dataset_manifest.json

זהו ה־source of truth של dataset ה־JPEG האמיתי.

הוא כולל:

- Photographer ID.
- כל האירועים.
- split לכל אירוע.
- כל הזוגות.
- full SHA-256.
- geometry.
- סיבת exclusion.
- leakage checks.
- readiness.

### evaluation_plan.json

מתעד במפורש:

- אילו אירועים Train.
- אילו Validation.
- אילו Test.
- אילו עדיין unassigned.
- כללי השימוש ב־splits.

---

## שלב 2 — J0 על חומר אמיתי

אחרי Intake תקין:

```powershell
python training_lab\jpeg_real_j0_batch.py --dataset-manifest "C:\Users\Matann\Desktop\jpeg_real_intake\dataset_manifest.json" --output "C:\Users\Matann\Desktop\jpeg_real_j0"
```

ברירת המחדל היא:

```text
Train + Validation בלבד
```

ה־Test נשאר נעול.

### למה

J0 משמש אותנו לבחירת/שיפור ה־JPEG Edit Representation. אם נסתכל שוב ושוב על Test ונשנה את ה־Recipe בהתאם, Test כבר לא יהיה Test אמיתי.

---

## פתיחת Test

רק כאשר מחליטים לבצע audit סופי של Candidate קפוא:

```powershell
python training_lab\jpeg_real_j0_batch.py --dataset-manifest "C:\Users\Matann\Desktop\jpeg_real_intake\dataset_manifest.json" --output "C:\Users\Matann\Desktop\jpeg_real_j0_test" --split test --unlock-test
```

זו פעולה מפורשת בכוונה.

---

## תוצרי J0 Real Batch

```text
jpeg_real_j0/
├── summary.json
├── event_results.csv
├── pair_results.csv
├── recipe_targets.json
├── train/
│   └── <event>/
│       ├── contact_sheet.jpg
│       ├── results.csv
│       ├── recipes/
│       └── reconstructions/
└── validation/
    └── <event>/
```

### recipe_targets.json

זהו הקובץ שנוכל להזין בהמשך ל־J1 Real Candidate.

לכל תמונה הוא שומר:

- pair id
- event
- split
- source SHA-256
- edited SHA-256
- J0 Recipe
- reconstruction metrics

Candidate עתידי יוכל:

```text
Train events
    ↓
Original JPEG → Features → Predict Recipe

Validation events
    ↓
בחירת Candidate / representation

Locked Test
    ↓
Audit סופי בלבד
```

---

## Smoke Test עכשיו, לפני שיש צלם

כדי לבדוק כבר עכשיו שכל intake/split plumbing עובד:

### יצירת fixture

```powershell
cd "C:\Users\Matann\Desktop\PROGRAPHER V2\backend"

python training_lab\jpeg_real_intake_smoke_fixture.py --output "C:\Users\Matann\Desktop\jpeg_real_intake_smoke_source" --clean
```

ה־fixture מייצר:

- 5 אירועים.
- 20 זוגות.
- זוג identity אחד.
- זוג geometry mismatch אחד.
- שאר הזוגות usable.
- PNG נוסף בכל אירוע כדי לבדוק שפורמט לא־JPEG אינו נכנס לזיווג.

### Intake

```powershell
python training_lab\jpeg_real_dataset_intake.py --root "C:\Users\Matann\Desktop\jpeg_real_intake_smoke_source" --output "C:\Users\Matann\Desktop\jpeg_real_intake_smoke" --photographer-id "synthetic-smoke"
```

מצופה לקבל Whole-event evaluation ready = YES, כל עוד אין leakage או שגיאת סביבה.

### J0 batch בלי לפתוח Test

```powershell
python training_lab\jpeg_real_j0_batch.py --dataset-manifest "C:\Users\Matann\Desktop\jpeg_real_intake_smoke\dataset_manifest.json" --output "C:\Users\Matann\Desktop\jpeg_real_j0_smoke"
```

זה אמור להריץ רק Train + Validation.

---

## מה עדיין לא נחשב מוכח

גם אם כל ה־Smoke וה־Synthetic עוברים:

- אין עדיין הוכחת סגנון של צלם אמיתי.
- אין עדיין J1 Real שעבר אירוע חדש.
- אין Photographer Adapter אמיתי.
- אין הוכחת local edits.
- אין טענת Lightroom equivalence.
- אין טענת 70%–80% חיסכון.
- אין טענת 100% אוטומציה.

השלב האמיתי מתחיל רק כאשר מגיעים כמה אירועים מקצועיים מאותו צלם, נשמרת הפרדה לפי אירוע, ויש Validation/Test שלא שימשו לאימון או לכיוון המודל.
