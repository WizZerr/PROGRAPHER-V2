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
- אינו מכניס crop/rotation/mirror/wrong-copy לא נתמכים בלי שנדע.
- מנרמל EXIF Orientation.
- ממיר ICC תקין ל־sRGB working space, ומתעד הנחת sRGB כש־ICC חסר ב־RGB.
- שומר provenance ו־SHA-256 מלא.
- מקפיא dataset snapshot שנבדק שוב לפני J0, J1 ולפני פתיחת Test.
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
- רוחב/גובה אחרי EXIF Orientation.
- ICC profile / ICC SHA-256 / פעולת Color normalization.
- working color space קבוע: sRGB.
- שינוי aspect ratio.
- alignment חזותי באמצעות features + homography.
- crop גם אם יחס הממדים נשאר זהה.
- rotation של 90°/180° ושאר residual rotation.
- mirror/flip.
- wrong-copy או זוג שלא ניתן לאמת בביטחון.
- האם הזוג מתאים ל־J0 first-pass recipe fitting.

### סטטוסים אפשריים

`usable`

זוג מתאים לניסוי J0 הראשוני.

`unchanged_final`

ה־Original וה־Edited זהים byte-for-byte. המקרה נשמר כי הוא יכול להיות משמעותי בהמשך, אבל אינו משמש כרגע להפקת Recipe target ב־J0.

`crop_same_ratio` / `crop_or_geometry_mismatch`

ה־alignment מצביע על crop/geometry edit. זה כולל גם crop ששומר על אותו aspect ratio.

`rotation_mismatch`

נמצאה rotation שנותרה אחרי נרמול EXIF Orientation.

`mirror_mismatch`

נמצא mirror/flip בין Original ל־Edited.

`wrong_copy_or_unverified`

לא ניתן להוכיח שזה אותו צילום באותה גאומטריה. הזוג נחסם במקום לנחש.

`color_contract_failed`

ICC/Color encoding אינו ניתן לנרמול בבטחה ל־working space.

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
├── dataset_snapshot.json
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
- ICC/EXIF/working-color evidence.
- visual geometry/alignment evidence.
- snapshot id/path.
- סיבת exclusion.
- leakage checks.
- readiness.


### dataset_snapshot.json

זהו snapshot קפוא של bytes שנקלטו ב־Intake.

לכל Original/Edited הוא שומר:

- role.
- pair id.
- locator נוכחי.
- size.
- mtime.
- SHA-256 מלא.

ה־snapshot id נגזר מה־content identity ולא מהנתיב. לכן Relocation מאומת יכול בעתיד לשנות locator בלי להחליף זהות Dataset.

לפני:

- J0,
- feature extraction / J1,
- Locked Test,

המערכת קוראת מחדש את הקבצים ומשווה SHA-256. אם קובץ השתנה, חסר או הוחלף — ההרצה נעצרת. צריך לבצע Intake חדש ולקבל snapshot חדש; אין המשך שקט על Dataset שהשתנה.

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

לפני כל J0 ה־dataset snapshot נבדק מחדש מול SHA-256. שינוי בקובץ אחרי Intake חוסם את ההרצה.

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


---

## שלב 3 — J1 Real Candidate

לאחר שנוצר `recipe_targets.json` מ־Train + Validation, אפשר לאמן Candidate ראשון:

```powershell
python training_lab\jpeg_real_j1_candidate.py --dataset-manifest "C:\Users\Matann\Desktop\jpeg_real_intake_smoke\dataset_manifest.json" --recipe-targets "C:\Users\Matann\Desktop\jpeg_real_j0_smoke\recipe_targets.json" --output "C:\Users\Matann\Desktop\jpeg_real_j1_smoke"
```

ה־Candidate:

- מאמת מחדש את dataset snapshot לפני feature extraction.
- קורא JPEG דרך אותו color-managed decoder של J0.
- מתאים משקלים רק על זוגות `Train`.
- משתמש ב־Validation להערכה בלבד.
- אינו פותח את Test.
- משווה מול `No Edit` ומול `Mean Recipe`.
- שומר Candidate immutable תחת:
  `candidates/<candidate_id>/`.
- שומר `model.npz`, חוזה מודל, תוצאות Validation ו־contact sheet.
- אינו מקדם את עצמו אוטומטית ואינו מייצר טענת איכות.

ב־smoke fixture אין לצפות למסקנת איכות, משום שיש מעט זוגות והעריכות הסינתטיות נועדו בעיקר לבדוק plumbing. המטרה היא לוודא שהמסלול:

```text
Train recipe targets
      ↓
Features
      ↓
Candidate fit
      ↓
Held-out Validation
      ↓
Immutable artifact
```

עובד בלי לגעת ב־Test.

---

## שלב 4 — Locked Test Audit

רק אחרי ש־Candidate מוקפא ומחליטים שלא לכוון אותו יותר מול אותו Test, פותחים Test במפורש.

ה־audit **אינו צריך J0 targets של Test**. הוא טוען את Candidate הקפוא ומפעיל אותו ישירות על Original JPEGs של Test, ואז משווה ל־Photographer Edited JPEG.

דוגמה:

```powershell
python training_lab\jpeg_real_j1_test_audit.py --dataset-manifest "C:\Users\Matann\Desktop\jpeg_real_intake_smoke\dataset_manifest.json" --candidate-dir "<CANDIDATE_DIR>" --output "C:\Users\Matann\Desktop\jpeg_real_j1_test_audit" --unlock-test
```

בלי `--unlock-test` הסקריפט מסרב לפתוח את Test.

ה־audit בודק גם שה־Candidate נבנה מול אותו dataset manifest קפוא באמצעות SHA-256, מאמת מחדש את dataset snapshot לפני קריאת Test, ולא משנה את משקלי המודל.

התוצרים:

```text
test_audit.json
test_results.csv
test_contact_sheet.jpg
predictions/
mean_recipe/
```

אחרי Test audit אין לכוון מחדש את אותו Candidate לפי התוצאה. אם התוצאה חושפת בעיה ורוצים לשנות architecture/features/recipe, יוצרים Candidate חדש ובמקרה הצורך Test חדש לפי פרוטוקול ההערכה.
