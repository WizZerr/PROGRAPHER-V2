# ProGrapher V2 — MASTER SOURCE OF TRUTH v4.0

**תוכנית האמת לפיתוח מסחרי — Lightroom-First, Photographer-Fidelity, Event-First**  
**תאריך:** 12.10.2026  
**מעמד:** החלטת כיוון מוצר מאושרת בשיחה; מסמך ביצוע v4.0 חדש. מסמך ביצוע פעיל ב־GitHub החל מ־12.10.2026; שערי איכות ותשתית קיימים נשארים פתוחים עד אימותם.  
**מאגר:** `WizZerr/PROGRAPHER-V2` · ענף `main` · SHA שנבדק בעת עריכת המסמך: `021dcc16fe4f84ac9546349f224dee8331bc8877`.  
**קהל יעד:** צלמי אירועים בישראל, ובהמשך שווקים נוספים. Windows x64 + macOS Apple Silicon. ממשק עברי מלא, RTL, שולחני, מקצועי.  
**מקורות היסטוריים:** `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` v3.1, החלטות D-015/D-016, מסמכי התקדמות וראיות POC מקומיות. התוכנית ההיסטורית בת 37 Phases נשמרת באמצעות מיפוי, ולא הופכת אוטומטית לתוכנית הביצוע הפעילה.

---

## 0. הצהרת המוצר שאסור לנו לסטות ממנה

**הצלם נשאר האמן. ProGrapher לומדת להיות העוזרת שלו.**

צלם מקצועי מתקין את ProGrapher, מחבר פעם אחת את Lightroom Classic, ומאפשר לה ללמוד מהאירועים שהוא עצמו כבר ערך (בכפוף להרשאות ולבדיקות תקינות). כאשר הוא פותח אירוע RAW חדש, ProGrapher מנתחת את התמונות, חוזה לכל אחת עריכה אישית בהתאם לסגנונו ולתנאי הצילום, מבצעת את העריכות האפשריות דרך Lightroom, מציגה רק חריגים שדורשים שיקול דעת, ולאחר אישור מפיקה בלחיצה אחת את האירוע כקובצי JPEG באיכות מסירה.

**הצלחה אינה חיזוי של סליידרים בלבד, אינה מסך יפה, ואינה הוכחת SDK על RAW אחד. הצלחה היא אירוע חדש שהצלם מוסר מהר יותר, בלי ירידה באיכות, עם פחות עבודה ידנית.**

### עקרונות מוצר בלתי־מתפשרים

1. **Photographer-fidelity:** לומדים את החלטות הצלם המסוים; לא מפעילים 'שיפור תמונה' גנרי שסותר את הסגנון שלו. תצלום כהה או תאורה צבעונית יכולים להיות בחירה מכוונת.
2. **Event-first:** יחידת הערך היא אירוע שלם עם אלפי תמונות, לא דוגמה בודדת.
3. **Hebrew-first, frictionless:** התקנה אחת, אשף חיבור פשוט, יצירת אירוע והפעלה בלחיצות בודדות. אין PowerShell, ZIP, XMP או Plug-in Manager בעבודת לקוח רגילה.
4. **Adobe Lightroom Classic is Renderer v1:** Lightroom מותקנת ומורשית במחשב הלקוח ומשמשת לפיתוח RAW, פרופילי צבע, החלת פקודות שנתמכות וייצוא JPEG.
5. **Engine-agnostic brain:** המוח ונתוני הלמידה אינם מוטמעים בתוסף Lightroom. מחזיקים גם משמעות כללית של כוונת עריכה וגם מתכון Adobe מקורי, כדי שנוכל לשנות מנוע בעתיד באמצעות כיול/אימון מחדש.
6. **Safe automation:** פעולה לא נתמכת או לא בטוחה אינה מתבצעת בשקט. ברירת המחדל היא עצירה מבוקרת, תיעוד, דחייה לסקירה או No-Edit כאשר זה מתאים.
7. **Private by default:** קובצי אירועים נשארים מקומיים; ענן רק לשירותים שהצלם אישר, ללא העלאה גורפת של RAW.
8. **Evidence before claims:** אין פרסום אחוזי הצלחה, חיסכון בזמן, 'עריכה אוטומטית של הכול' או 'AI masking מלא' לפני ניסוי מאומת.

---

## 1. החלטות ארכיטקטורה חדשות — D-018 עד D-021

| החלטה | מצב וכיוון | משמעות מעשית |
|---|---|---|
| **D-018 Lightroom-First** | כיוון מוצר מאושר, הטמעה מסחרית עוד לא הוכחה | ב־Release 1 נשתמש ב־Lightroom Classic כמנוע פיתוח/ייצוא; דרישת התקנה ורישיון למשתמש תוצג בגלוי. |
| **D-019 Universal Recipe + Adobe Adapter** | חובה ארכיטקטונית | נשמור `EditIntent` ניטרלי (מה רוצים להשיג) בנפרד מ־`AdobeDevelopRecipe` (איך מבצעים ב־Lightroom), יחד עם גרסאות ונתוני מקור. מעבר עתידי למנוע אחר מחייב תרגום מאומת, לא העתקת מספרים. |
| **D-020 Event Autopilot with Human Exception Review** | חזון מוצר מחייב; מנגנון אמינות טרם נבדק | רצף: ingest → analyze → predict → apply → verify → review → export; אין אירוע 'מוכן' עם כשל שלא טופל. |
| **D-021 Lightweight, Local Lightroom Bridge** | החלטת אבטחה ומוצר | תוסף Lua מינימלי ומתקין אחוד; המוח הקנייני אינו בתוסף; ללא מנגנון המסתמך על קטלוג Lightroom כבסיס נתונים שאנחנו כותבים אליו ישירות. |

**מסמכי המחקר `docs/D_015_RAW_FIRST_SCOPE.md` ו־`docs/D_016_PHOTOGRAPHER_FIDELITY_FIRST.md` נשארים בתוקף.** הכותרות D-015/D-016 ב־`docs/DECISIONS.md` שייכות להחלטות אחרות; להפניות למחקר יש להשתמש בשמות הקבצים המדויקים. פיתוח JPEG עצמאי נשאר מוקפא. החלטות JPEG-first ישנות נסוגות רק כאשר הן סותרות RAW-first/Lightroom-first. אין מחיקת קוד, תיעוד, Branch, ניסוי או Brain היסטורי; V1 המיושן נשאר retired.

**שינוי מסלול ביצוע, לא הבטחת מוצר:** המיקוד השתנה רשמית מהניסיון לפתח Adobe-equivalent renderer לשילוב Lightroom, אבל 'Lightroom מלא מאחורי הקלעים' עדיין דורש הוכחת אוטומציה, ביצועים, תאימות ועדכונים.

---

## 2. מה הוכח בפועל נכון ל־12.10.2026

### 2.1 ראיות חיוביות

| רכיב | ראיה | מה בדיוק מותר לומר |
|---|---|---|
| בסיס יישום | Tauri/Next.js/FastAPI/SQLite וקוד אירועים, גלריה, RAW/XMP, datasets ו־Brain V2 ב־GitHub | קיימת תשתית רחבה; אין מכאן מוצר AI שעורך אירוע מסחרי. |
| חקירת מקור | 5,210 RAW מקומיים מול קטלוג עם 7,023 רשומות RAW; 5,208 התאמות בשם קובץ בלבד | יש מועמדים לזיווג, **לא** 5,208 זוגות מאושרים לאימון. |
| RAW vision | 12/12 תצוגות מקור וניסוי CLIP עם 12 הצעות ו־abstention אחד | יכולת מחקר מקומית; דירוגי CLIP אינם ביטחון מכויל או הוכחה לנכונות סצנות. |
| Bridge v0.1.1 | `PASS`, JPEG בגודל 8,857,195 bytes, Exposure +0.55, Highlights −30, Shadows +20 | Lightroom החילה מתכון בסיסי והפיקה JPEG על תמונת מחקר אחת. |
| Bridge v0.2.0 | `PASS`, Adobe Standard + 10 הגדרות פיתוח שנקראו בחזרה, JPEG בגודל 9,152,353 bytes | קיים חיבור פיתוח/ייצוא עובד ל־10 שדות ולפרופיל ב־RAW אחד. |
| מסכות ניסיוניות | `getAllMasks()` החזירה טבלה עם מסכה אחת; המסכה נראתה בתמונה; Exposure מקומי 0.00 | קיימת מסכה בקטלוג הבדיקה; **לא** הוכחה יצירתה בוודאות על ידי התוסף, **לא** הוכחה החלת עריכה מקומית וייצוא מסכה תקין. |

### 2.2 מה עדיין לא הוכח

- אפס דוגמאות שעמדו בכל קריטריוני training-ready המאושרים; G0 עדיין לא חתום וה־Gates לא הועברו.
- אין מודל מאומן ומאומת על עריכות הצלם; אין אישור צלם לאיכות על אירוע חדש.
- אין Bridge batch עמיד לאלפי RAW, אין אוטומציה מוכחת ללא בחירת פקודות מתוך Lightroom, ואין installer מסחרי מחובר.
- אין אישור מלא ל־Subject/Sky/Background masking דרך API באופן אמין ואוטומטי; אין הבטחת Retouch/Heal מלא.
- אין ערובה ל־Lightroom נסתר לחלוטין או ליישום בלי דרישה ל־Lightroom Classic; נדרשת גרסה מותקנת ורישיון לקוח.
- אין ראיית macOS Apple Silicon מלאה, ואין מדידת חיסכון בזמן או יתרון איכותי מול Aftershoot/Imagen.

**POC packages v0.1–v0.3.x הן חבילות ניסוי מקומיות ואינן חלק מ־`main` עד שהקוד נבדק, הוכנס למודולים המקובלים ונעברו בדיקות רגרסיה.** אין לסמן אותן כיכולת מוצר קיימת.

---

## 3. חוויית הלקוח — זרימת האמת

### 3.1 התקנה וחיבור חד־פעמיים

- המשתמש מוריד **מתקין ProGrapher אחד**. המתקין מכין את אפליקציית Desktop ואת תוסף Bridge המינימלי למיקומו המתאים, בכפוף להיתרי מערכת ותמיכת Lightroom.
- אשף Setup בודק גרסת Lightroom Classic, רישוי/זמינות לפי מה שניתן לאמת, נתיב מודול, גרסת תוסף, חיבור heartbeat, הרשאות תיקייה ויכולת להריץ משימת demo בטוחה.
- אם Lightroom מחייבת פתיחה, אישור תוסף או יצירת קטלוג עבודה, האשף מנחה בבירור **פעם אחת**; אין הבטחה לאוטומציה נסתרת לפני הוכחה.
- קטלוג הצלם הקיים נשאר בלתי־מושפע. ProGrapher משתמשת בסביבת עבודה מבודדת, ב־Collection או בקטלוג ייעודי לפי בדיקת SDK ותלות ההפעלה. אין כתיבה ישירה למסד `.lrcat` חי.

### 3.2 אימון ראשוני

הצלם בוחר **אירועים ערוכים קודמים** ב־Lightroom (או עותק קטלוג ייצוא מתאים) ותיקיות RAW מקוריות, מאשר שימוש ללמידה, ומקבל דוח קליטה: כמה תמונות זוהו; כמה מתאימות בוודאות; כמה ממתינות לבדיקה; מה חסר; מה נתמך ומה לא. אין בקשה לסווג אלפי תמונות ידנית. אימות אנושי ממוקד לאירוע, זהות, סופיות ואמביגואיטיות נשאר חובה כשלא ניתן להסיק אותם אוטומטית בביטחון.

### 3.3 אירוע חדש

הצלם בוחר תיקיית RAW, שם האירוע ופרופיל אישי. המערכת מתעדת hashes וזהות תמונות; מעבדת בהדרגה, ללא טעינת אלפי קבצים לזיכרון בבת אחת; מפענחת תצוגה מקורית קבועה ומאפייני RAW; מזהה תנאי סצנה ומצלמה; בונה מתכון עריכה אישי לכל תמונה, כולל No-Edit/Abstain כאשר מתאים.

### 3.4 ביצוע ובקרת איכות

Bridge מפעילה מתכונים בתורים קטנים מול Lightroom, קוראת בחזרה מצבי Develop בגרסאות שנתמכות, מפיקה Preview נאמנה דרך Lightroom ככל ש־SDK מאפשר, מאמתת source identity ומחזירה סטטוס. תמונה עם פעולת Mask/Retouch שלא נתמכת מוצגת כ־Needs Review ולא מסומנת כערוכה מלאה.

### 3.5 אישור וייצוא

הצלם רואה גלריה עם ארבעה מצבים מפורשים: `READY_TO_REVIEW`, `APPROVED`, `NEEDS_ATTENTION`, `FAILED/UNSUPPORTED`. תמונות חשודות מוצגות בעדיפות; סטטוס אירוע `READY_TO_EXPORT` מותר רק אחרי שכל התמונות הרלוונטיות אושרו או טופלו בהחלטה מפורשת. לחיצה אחת על 'ייצוא האירוע' מפעילה JPEG export, בודקת ספירת קבצים/תקינות/סיום ומפיקה דוח. אין סימון PASS על קובץ חלקי או חסר.

---

## 4. הארכיטקטורה הטכנית המוסכמת

```text
PROGRAPHER DESKTOP  (Tauri + Next.js, Hebrew RTL)
    |
    +-- Local API / Event DB / Durable Job Queue (FastAPI + SQLite)
    |       |
    |       +-- RAW Source Intake & Integrity (read-only)
    |       +-- Vision + RAW Features (source-only)
    |       +-- Photographer Profile / Inference / Confidence
    |       +-- Universal EditIntent + AdobeDevelopRecipe (versioned)
    |       +-- Review / Corrections / Event State
    |       |
    |       +-- Lightroom Job Adapter (validated local IPC)
    |               |
    |               +-- Lightroom Bridge (minimal Lua plug-in)
    |                       |
    |                       +-- Lightroom Classic Develop/Mask API
    |                       +-- Adobe RAW / Color / Profiles / JPEG Export
    |                       +-- Readback + Progress + Error Return
    |
    +-- Optional Cloud Control Plane (later)
            Auth / License / Profile sync / consented learning artifacts
```

### 4.1 מי אחראי למה

- **ProGrapher** אחראית לנתוני פרויקט, זהות מקורות, ניתוח, חיזוי, בחירת עריכות, תורים, חריגים, סקירה, בקרה, מדידת איכות והתאוששות.
- **Lightroom** אחראית לפיתוח Adobe בפועל, פירוש מחוונים, צבע/פרופילים, פעולות מסכה שהוכחו, ותהליך JPEG export.
- **Bridge** היא Adapter דק עם רשימת פקודות מוגבלת, בדיקת קלט, אימות הרשאה מקומית, journal/ack, וגרסאות API. אין בה מודלים או לוגיקה קניינית של למידת צלם.
- **ענן עתידי** אחראי לזהות, זכאות ופרופילים שנבחרו. לא לרינדור אוטומטי של כל תמונה, ולא לשמירת כל ספריית הצלם כברירת מחדל.

### 4.2 חוזה מתכון העריכה

`EditIntent` (מונחים כלליים: שמירת בהירות פנים, הימנעות מהלבנת רקע, שמירת LED צבעוני) נפרד מ־`AdobeDevelopRecipe` (שדות Adobe המדויקים). יש לשמור מזהי גרסה, ProcessVersion, CameraProfile, WB, curves, HSL, grading, crop, local mask descriptors ו־flags לחוסר תמיכה. **לא כל שדה חייב להיתמך ב־v1; חוסר תמיכה מדווח במפורש.**

`PhotoEditJob` נושא `job_id`, `event_id`, `photo_asset_id`, source hash, Lightroom photo reference, recipe revision/version, idempotency key, adapter version, required capabilities, input preconditions, status, logs, readback, output hash and error class. פעולות חוזרות לא ייצרו מסכות כפולות או ידרסו עריכת צלם מאושרת.

### 4.3 ניהול קבצים וקטלוגים

- RAW מקורי בלתי־משתנה; XMP קיים של המשתמש אינו נדרס ללא אישור מפורש ו־backup/version.
- `.lrcat` של הצלם נקרא מעותק קריאה בלבד לצורכי מחקר/ייבוא, או דרך פעולה נתמכת של SDK; **לא כותבים ישירות לתוך SQLite של Lightroom**.
- לכל אירוע namespace מקומי משלו, מפתח זהות לפי hash/metadata ובדיקת כפילויות. אם יש Virtual Copies או עריכות חלופיות, לא מחליטים אוטומטית איזו היא 'סופית' ללא ראיה.
- ה־Bridge תומכת ב־checkpoint/resume, retry מוגבל, timeout, cancel ומצבי `UNKNOWN/FAILED`; לא משחזרת פתיחת Lightroom או החלפת קטלוג ללא תכנון והרשאות.

---

## 5. מקור האמת של הלמידה — לא דליפת תשובות

### 5.1 קלטי מודל מותרי־שימוש

רק RAW המקורי, embedded preview או preview מפותחת בשיטת source-only יציבה שניתן להפיק גם לאירוע חדש, EXIF/Camera, מאפייני פיקסלים לינאריים, הקשר אירוע ומאפייני סצנה שחושבו מהמקור. תצוגת מצלמה אינה זהה ל־Adobe Color; היא יכולה לשמש ל־Vision אם נבחנה אמפירית. אין חובה לשחזר Adobe Color בתוך מנוע המודל.

### 5.2 מטרות למידה בלבד

הגדרות Develop הסופיות המאומתות מתוך Lightroom Catalog/XMP, כולל פרופיל שנבחר במהלך העריכה, היסטוריית אישורים/תיקונים מאומתת, ותוצאות JPEG נבחרות לצורכי Evaluation כאשר נדרש (לא תנאי חובה לאימון RAW-first). **פרופיל Adobe שנמצא בקטלוג הסופי לא נכנס לתמונת ה־Vision מראש אם הוא חלק מהחלטת העריכה.**

### 5.3 אימות זוגות RAW → Develop

- זהות RAW: hash/source metadata/path mapping, לא רק שם קובץ.
- התאמת רשומת Lightroom מדויקת, Virtual Copy ו־ProcessVersion לפי מקור אמת.
- אישור שהעריכה נשמרה כסופית על ידי הצלם; לא מניחים שכל הערכים הסופיים שווים לשינויים היחסיים מנקודת הייבוא.
- אירוע ו־source-group ידועים; הפרדה מוחלטת של Train / Validation / Locked Test ברמת אירוע.
- שדות חריגים, מסכות מקומיות בלתי־מפורשות, נוסחאות חסרות ומידע מותר/אסור מסומנים בדוח ולא מוחבאים.
- הרשאות בעל זכויות והסכמה לשימוש בלמידה מתועדות; אין העלאת חומר צלם ל־GitHub או לצ'אט ללא אישור מתאים.

### 5.4 הכשרת פרופיל

נתחיל מ־strong simple baseline, אחריו מודל צילום-ספציפי גלובלי עם החלטת `No-Edit` ו־`Needs Review`. אם תוספת סצנה/encoder משפרת בפועל, נכניס אותה. כל Candidate נשמר בגרסה בלתי משתנה, כולל metrics, hashes, pipeline, recipe וגרסת Bridge. לא מעדכנים פרופיל פעיל באמצע אירוע, ולא מאמנים מחדש על פלט AI לא מאושר.

---

## 6. מה נכנס לגרסה הראשונה — ומה לא

| יכולת | Release 1 — התחייבות מותנית בהוכחה | מחוץ להבטחה הראשונה |
|---|---|---|
| RAW | קלט מקור RAW בתמיכת מצלמות שנבדקו | כל מצלמה/פורמט בשוק ללא בדיקה |
| למידה | פרופיל אישי לפי עריכות Lightroom מאומתות | לימוד מלא מצילום יחיד או מקטלוג לא מזווג |
| עריכה | מתכון פר־תמונה לעריכות גלובליות נתמכות | כל מחוון, brush, clone/heal ו־AI masking בכל גרסה |
| סקירה | חריגים, תיקון ואישור | הבטחה שאף תמונה לא תידרש לבדיקה |
| ביצוע | Lightroom Classic עם תוסף מחובר ונתמך | עריכה ללא התקנת Adobe, Web-only, Server Lightroom |
| מסכות | מסכות ב־beta/מחקר לפי capability matrix, רק לאחר POC מלא | מסכות מורכבות אוטומטיות כהבטחה מסחרית מוקדמת |
| ייצוא | JPEG דרך Lightroom + ספירה/verify/report | זהות byte-for-byte לכל JPEG היסטורי ללא settings |
| מוצר | Windows x64 + macOS Apple Silicon לאחר QA | Intel Mac לא מאומת; צוותים משותפים וגלריות מסירה |
| שירות | ממשק ותמיכה בעברית מלאה | טענת בלעדיות בעברית ללא סקר שוק |

**חוויית מוצר נדרשת:** חיבור Lightroom פעם אחת; יצירת אירוע, ניתוח, הצעות, Review ו־Export מתוך ProGrapher. אם Bridge אינה מסוגלת לבצע פעולה ללא מעבר ידני ל־Lightroom, היא נשארת במגבלת scope מפורשת ולא משווקת כחסרת חיכוך.

---

## 7. סדר הפיתוח הרשמי — Phases 00–18 עם Parts חדשים

שומרים את מספור Phase 00–18 ממסמך v3.1. המיפוי לתוכנית הישנה בת 37 Phases נשאר במסמך הארכיון. **מצב ישן של Part אינו משתנה רטרואקטיבית; שינוי יעד יוצר Part מתועד או גרסת חוזה חדשה.**

| Phase | מוקד לאחר D-018 | Parts ביצוע מחייבים / תוצר |
|---|---|---|
| **00 — Baseline & Adoption** | לאחד גרסאות ומסמכי אמת | `PG-00.LB01` רישום החלטה/היקף; `LB02` לשמר POC ולכייל רגרסיות; `LB03` לרשום SHA/גיבוי/מכשירים; G0 נשאר נפרד ולא נחתם אוטומטית. |
| **01 — Contracts** | Release 1 + LightRoom capability matrix | `PG-01.LB01` חוזה מוצר מחודש; `LB02` schema EditIntent/AdobeRecipe; `LB03` פרוטוקול RAW ותוצאה + ספי QA. |
| **02 — Platforms** | Windows + Apple Silicon | `PG-02.LB01` SDK compatibility matrix; `LB02` install/load/unload/restart על Windows; `LB03` smoke Mac עם גרסאות Adobe; `LB04` סביבת בדיקה מבודדת. |
| **03 — Data Integrity** | מקור מדויק ו־Lightroom targets | `PG-03.LB01` hash↔catalog IDs; `LB02` finality/virtual-copy; `LB03` unsupported/consent/whole-event split. |
| **04 — Lightroom Bridge** | POC → Adapter אמיתי | `PG-04.LB01` POC v0.2 regression; `LB02` plugin IPC & heartbeat; `LB03` recipe readback; `LB04` preview/export controls; `LB05` capabilities/abstain; `LB06` mask research isolated. |
| **05 — Jobs & Persistence** | תורי אלפי תמונות | `PG-05.LB01` journal/idempotency; `LB02` chunks/batching; `LB03` cancel/resume/restart; `LB04` backup/restore, relink, error UX. |
| **06 — Photographer Intake** | Dataset מאושר מאירועים קודמים | `PG-06.LB01` wizard קליטה; `LB02` identity/finality/human exceptions; `LB03` consent; `LB04` event split; G1. |
| **07 — Representation / Baselines** | מתכוני Adobe ויעדים ניתנים ללמידה | `PG-07.LB01` Global-only target policy; `LB02` NoOp/fixed/scene baselines; `LB03` coverage/unsupported audit; G2. |
| **08 — Personal Brain** | מודל אישי שמנבא תמונות חדשות | `PG-08.LB01` source-only features; `LB02` train+Validation; `LB03` unseen-event Test; `LB04` calibration/abstain; G3. |
| **09 — Event Autopilot** | מוצר אירועים end-to-end | `PG-09.LB01` יצירת אירוע; `LB02` predict-batch; `LB03` bridge queue; `LB04` photographer review; `LB05` verified JPEG export. |
| **10 — Feedback** | תיקונים מאושרים משפרים ProfileVersion | `PG-10.LB01` tracking revisions; `LB02` consent and candidate building; `LB03` promote/rollback. |
| **11 — Local Alpha** | בדיקת איכות וזמן עם צלם ראשון | `PG-11.LB01` שני אירועים לא־מאומנים; `LB02` performance/reliability; `LB03` delivery acceptance/time study; G4. |
| **12 — Auth** | חשבונות וזכאות מסחרית | `PG-12.LB01` identity/login; `LB02` offline grace; `LB03` device control/data isolation. |
| **13 — Profile Sync** | גיבוי פרופילים מאושרים | `PG-13.LB01` version registry; `LB02` opt-in artifacts; `LB03` compatibility and deletion. |
| **14 — Commercial Operations** | תמחור, רישוי, פרטיות ותמיכה | `PG-14.LB01` license/terms; `LB02` economics; `LB03` support+diagnostics+privacy. |
| **15 — Packaging & Updates** | מתקין אחד + תוסף | `PG-15.LB01` signed installer; `LB02` automatic plugin install/repair; `LB03` Adobe version checks; `LB04` safe updates+rollback; G5. |
| **16 — Israeli Beta** | מספר צלמים ואירועים חדשים | `PG-16.LB01` guided onboarding; `LB02` 3 photographers × 3 events target; `LB03` failure classes/benchmarks; G6 candidate. |
| **17 — Release 1** | שחרור מסחרי בהיקף שנבדק | `PG-17.LB01` go/no-go; `LB02` public docs; `LB03` support+pricing+release monitor. |
| **18 — Continuous Improvement** | מוח חדש רק עם שיפור מוכח | `PG-18.LB01` feedback dataset; `LB02` candidate experiments; `LB03` locked audit; `LB04` gradual rollout/rollback. |

**Execution order בפועל:** (א) PG-00 / PG-01 / isolated LB-PoC, (ב) בטיחות נתונים + Bridge batch + jobs במקביל כאשר אין תלות, (ג) Authorized dataset/G1, (ד) baseline, brain/G2–G3, (ה) real event/G4, (ו) installer/business/beta/G5–G6. עבודת Mac מתחילה מוקדם; לא דוחים גילוי מגבלות Adobe/macOS עד סוף הדרך.

---

## 8. התוכנית המיידית — חמש חבילות עבודה, לא עוד מסכה אחת

### WORK PACKAGE 01 — `LB-01` — Freeze & Integrate POC

**תוצר:** מקור קוד POC שנשמר כראיה במודול ייעודי, עם תיעוד v0.1.1/v0.2.0 PASS ו־v0.3.x mask pending; בלי private RAW ב־GitHub. **Done:** בדיקת smoke על קטלוג מחקר עוברת מחדש, original RAW hash לא השתנה, API statuses ברורים. אין שינוי מיידי ב־main בלי בדיקות/סנכרון מפורש.

### WORK PACKAGE 02 — `LB-02` — Autonomous Batch Contract

**תוצר:** תוסף Bridge שמסוגל לקבל JobQueue מקומית באופן מבוקר, גם ללא פתיחת תפריט ידנית לכל משימה, תחילה על 10 RAW, ואז 100. **Done:** כל מקור משויך למתכון נכון, readback נכון, JPEG export חוזר; restart/retry אינם משכפלים פעולות או פוגעים במקור; תקלות מוצגות ולא מוחבאות. נבדוק התנהגות Lightroom כשהיא סגורה/פתוחה, ממוזערת, busy ועם קטלוג אחר.

### WORK PACKAGE 03 — `DATA-01` — Photographer Dataset Gate

**תוצר:** manifest פרטי מאומת ל־RAW↔Develop, עם consent, finality, event IDs, Train/Validation/Test, masks-unsupported. **Done:** לפחות כמה אירועים אמיתיים מוכנים ברמת אמת מוגדרת (אין סף תמונות קסום), ללא שימוש ב־Test להתאמת המודל. לפני זה מותר engineering בלבד ולא אימון production.

### WORK PACKAGE 04 — `BRAIN-01` — Global Editor Candidate

**תוצר:** Baseline פשוט + Candidate אישי + תחזיות global-only, No-Edit/Abstain. **Done:** תוצאה טובה יותר מבסיס חזק על אירועים חדשים ברף שנקבע מראש, בלי עלייה בכשלים חמורים. תוצאות מוזרמות לתור Bridge, לא כתיבה ישירה לקטלוג RAW ההיסטורי.

### WORK PACKAGE 05 — `EVT-01` — First Real Event Rehearsal

**תוצר:** אירוע חדש של 100–300 תמונות בתחילה, אחר כך אלפים, עם review, תיקון, verified JPEG export, resume ודוח. **Done:** הצלם בודק את התמונות ומאשר את איכותן; זמן עבודה וחומרת תקלות נמדדים. אין הרחבה למכירה לפני מעבר Gates.

**העבודה הקרובה ביותר:** לסיים `LB-01` ולפרק את `LB-02` למשימות קוד ניתנות לבדיקה. בעיית המסכה המקומית נשמרת כ־research bug ולא חוסמת Global-first training או batch.

---

## 9. Quality Gates — מה מאפשר לנו להתקדם

| Gate | תנאי מעבר רשמי | מצב נוכחי |
|---|---|---|
| **G0 — Engineering Baseline** | רגרסיות PR1, restore, checkout, backup ושחזור נתונים + החלטות מאושרות | **OPEN**; אין להציג כאילו נסגר בעקבות Bridge POC. |
| **B0 — Lightroom Single-RAW POC** | החלת Adobe Profile + 10 שדות + readback + JPEG מתוך Lightroom | **PASS בהיקף RAW מחקר יחיד / Windows**. |
| **B1 — Bridge Batch** | תור 10→100 RAW, ללא לחיצות ידניות, crash-recovery, source safety, correct JPEG/recipe matching | **NOT RUN**. |
| **G1 — Validated Photographer Dataset** | consent, identity, finality, event groups, hashes, Train/Validation/Test | **BLOCKED**, עדיין 0 training-ready verified. |
| **G2 — Learnable Representation** | global target coverage, unsupported policies, baselines, photographer rubric, predeclared thresholds | **NOT PASSED**. |
| **G3 — Personal Brain Generalization** | נתוני source-only, unseen-event test, שיפור מעל baseline, ללא כשל חמור שיטתי | **NOT PASSED**. |
| **G4 — Real Local Product Value** | אירוע מלא + JPEG תקין + סקירה + חיסכון בזמן באיכות מאושרת, Windows/Mac | **NOT PASSED**. |
| **G5 — Independent Beta Installation** | installer plugin, entitlement, privacy, updates, compatibility, recovery, Mac/Windows QA | **NOT PASSED**. |
| **G6 — Commercial Go/No-Go** | בטא רב־צלמית, עלויות ותמיכה, שיפור זמן מוכח, אפס release blockers ידועים | **NOT PASSED**. |

**יעדי איכות ראשוניים לשימור מה־v3.1, בכפוף לגרסה RAW-first מעודכנת ומאושרת מראש:** G3 יעד לפחות +10 נקודות אחוז קבלה ללא תיקון מעל baseline פשוט חזק; G4 יעד לפחות 30% חיסכון בזמן עבודה פעיל בשני אירועים חדשים; G6 יעד לפחות 70% חיסכון חציוני באירועי בטא, 50% לכל צלם, מדגם תכנון של 3 צלמים × 3 אירועים. אלה **ספים מתוכננים, לא תוצאות**. אין להשתמש בתקציבי 2,000 JPEG ב־30 דקות מהמסלול JPEG הישן כטענה לביצועי Lightroom Bridge.

---

## 10. אבטחה, רישוי ופרטיות

- מתקין אחד ימוקם בחוויית לקוח; קוד Lua של תוסף Lightroom **ניתן לבדיקה ולהנדסה לאחור** ואינו מקום לשמירת secrets, weights או אלגוריתמים קנייניים. קוד המקומי כולו עלול להיחקר; רכיבים רגישים במיוחד יכולים לפעול בשרת בהסכמה, אך בלי להעלות אירועים כפתרון ברירת מחדל.
- תקשורת ProGrapher↔Bridge מוגבלת למחשב המקומי ול־allowlist פקודות; אימות session/job, הגנה מ־replay, מניעת arbitrary-path, journal ו־audit; אין לחשוף endpoint ללא הרשאה לרשת המקומית.
- Lightroom Classic נדרשת במחשב הלקוח עם רישיון משלו. מוודאים גרסת SDK, תמיכת מערכת הפעלה ותנאי שימוש/הפצה לפני שיווק. אין הטמעת פרופילים או בינאריים קנייניים של Adobe בלי הרשאה.
- צלם מעניק הרשאת שימוש בחומרי הצילום ללמידה. חתונה כוללת אנשים פרטיים; לא משתמשים בתמונות לזיהוי אישי או בסיווג רגיש. אירועי אמת אינם נכנסים ל־GitHub או לתמיכה ללא הסכמה.
- תוכנית פרטיות כוללת opt-in, מחיקת קבצים נגזרים, retention, זכויות, סינון לוגים, תמיכה ב־offline/grace ומנגנון הרשאות לאירוע ולפרופיל.
- אין שינוי bytes ל־RAW המקורי. Export לתיקייה נפרדת. אין overwrite של JPEG קיימים ללא בחירה מודעת וגיבוי מתאים.

---

## 11. סיכונים קריטיים ותגובה הנדסית

| סיכון | השפעה | איך בולמים |
|---|---|---|
| Adobe SDK לא תומך בכל פעולה | אירועים דורשים עבודה ידנית | capability matrix לפי גרסה; Global-first; unsupported→review; אין הבטחה לכל Mask. |
| Bridge לא פועלת ללא לחיצה ידנית | מוצר מסובך מדי | B1 dedicated automation/IPC test; אם נכשל, בוחנים XMP/supported export workflow במקום להעמיד פנים שזה אוטומטי. |
| חילוץ Develop שגוי / filename-only match | מוח לומדת עריכות של תמונה אחרת | Hash/ID/finality/virtual-copy/consent; G1 fail-closed. |
| Model predicts generic prettification | סטייה מסגנון הצלם | baseline, scene-aware, no-edit, unseen events, human acceptance. |
| אלפי תמונות / קטלוג גדול | עומס, תקיעה, השחתה, איטיות | chunking, resumable queue, memory limits, recoverable errors. |
| מסכה נוצרה אבל לא נערכה | תוצאות שגויות בשקט | readback + visual check + policy to exclude unsupported masks. |
| Mac/Adobe גרסאות שונות | חוסר תאימות והחזרות לקוחות | Apple Silicon smoke מוקדם, compatibility matrix, pinned bridge versions. |
| תלות ב־Adobe/מתחרים | lock-in, שינוי API | Universal EditIntent, stored original recipe, adapter boundary, optional native renderer R&D later. |
| צוות/לקוחות לא מבינים סטטוס | מסירת תמונות לא מוכנות | Review gate, explicit exceptions, verified export, no fake success. |

---

## 12. KPIs אמיתיים — לא מדדי יופי של AI

1. **Acceptance without correction:** מספר תמונות שהצלם מאשר למסירה ללא שינוי, מתוך כלל התמונות בתחום ההעריכה הנתמך באירוע; מדווחים גם שיעור unsupported מתוך כלל האירוע.
2. **Serious failure rate:** עריכה בלתי ראויה למסירה, פגיעה קשה בגווני עור, מקור שגוי, מסכה לא נכונה, קובץ שבור או נזק למקור; הניטור חייב להיות שמרני.
3. **Style fidelity:** הערכת הצלם עצמו מול עריכותיו המוכרות, על אירועים שלא נראו באימון.
4. **Active time saved:** כל זמן העבודה — הכנה, סקירה, תיקונים, פעולות Lightroom, export ותקלות — מול workflow הרגיל שלו באיכות מסירה שקולה.
5. **Unattended batch completion:** אחוז תמונות ש־Bridge השאירה במצב verified, יחד עם retry/error/mismatch rates.
6. **Time to first value:** ממועד התקנת מוצר חדש עד עריכה ראשונה מאושרת על ידי צלם אמיתי.
7. **Per-event and per-photographer reporting:** אלפי תמונות באותו אירוע אינן אלפי ניסויים בלתי־תלויים.

**הקלה בממשק אינה תחליף לדיוק:** בידול ישראלי (RTL, שירות, onboarding) הוא יתרון הפצה אפשרי, לא הוכחה לאיכות AI. נתעד feedback על מורכבות מתחרים בלי להניח שהלקוחות יעדיפו אותנו לפני שבדקו.

---

## 13. תנאי Done לכל Part ונהלי עבודה

Part נחשב `DONE` רק אם: (א) תוצר מוגדר ובר־שחזור קיים, (ב) unit/integration/Windows/Mac לפי הצורך עברו, (ג) שמירת מקור הוכחה, (ד) positive+negative+restart scenarios נבדקו, (ה) reports/logs/commit/hash/version נשמרו, (ו) doc `EXECUTION_BOARD` עודכן, (ז) אין טענת איכות מעבר להיקף הראיה.

**חוק הפיתוח:** בעיה אחת, שינוי אחד, סט בדיקות מוגדר, ראיה, ורק אז Part הבא. ל־Brain כל גרסה נשמרת; אין מחיקה של מועמד ישן. אין שילוב מחקר, שינוי UI גדול ומיגרציית נתונים לאותו PR. אין שימוש ב־private RAW כמבחן CI ציבורי.

**שימוש ב־Cursor / עוזר פיתוח:** בכל משימה מציינים `Phase/Part`, מצב קיים, קבצי יעד, שינוי מותר/אסור, acceptance tests, rollback plan, local-only/rights boundaries והחלטה האם נדרשת הרצה ב־Lightroom אמיתי.

---

## 14. תוכנית ה־90 יום הראשונה — סדר קדימויות, לא הבטחת לוח זמנים

**Wave 1 — Integrity & Bridge:** לשמר POC, לבצע B1 batch, לתקן setup/catalog safety, להגדיר capability matrix; לבדוק Windows על 10 ו־100 תמונות חוקיות; לפתוח smoke Mac מוקדם.

**Wave 2 — Verified Learning:** להסדיר הרשאות, זיהוי מקור, event/finality, Train/Validation/Test; לבנות target coverage ו־baseline; להכין training harness ללא העלאת חומר לא מורשה.

**Wave 3 — Personal AI + Pilot:** לאמן מועמד ראשון, להפעיל דרך Lightroom על אירוע חדש (בהיקף הולך וגדל), לתת לצלם Review/Correction, למדוד איכות וחיסכון; החלטת Continue/Improve/Stop לפי הנתונים, לא לפי התלהבות.

**לא פותחים מוקדם:** מסכות אוטומטיות מורכבות, מנוע RAW עצמאי, Marketplace, team workflows, הגשת אלפי תמונות לענן, subscription automation מלאה — עד שהחיבור, הדאטה והמוח מראים ערך אמיתי.

---

## 15. מצב הפרויקט בסוף מסמך זה — אמת אחת

**כבר בידינו:** תשתית תוכנה רחבה ב־GitHub; RAW/catalog research; Scene AI ניסיונית; Lightroom Bridge single-photo development/export שעבר v0.1.1 ו־v0.2.0; תכנון UX Hebrew-first.

**החסם הבא:** אין עדיין Dataset מאושר ואין אוטומציה מסחרית לאירוע. השאלה ההנדסית הראשונה היא האם אפשר להפעיל Bridge כ־batch ממערכת ProGrapher, ללא תפריט ידני, בבטיחות מלאה; השאלה המחקרית הראשונה היא האם אפשר ללמוד העדפות צלם אמיתיות מזוגות RAW/Develop שאומתו ולשפר את ההחלטות על אירועים שלא נראו.

**ה־North Star:** צלם מעלה אירוע → ProGrapher עורכת בסגנונו → הוא בודק חריגים → Lightroom מייצאת מאחורי הקלעים JPEG → אירוע מוכן למסירה. מוצר מוכר רק אם הדבר נמדד, חוזר ואמין.

**משימה הבאה כברירת מחדל:** `LB-01: Integrate and Freeze POC` ולא `Mask v0.3.4`. לאחר מכן `LB-02: Autonomous Batch Contract`. אין קפיצה לאימון Production Brain לפני G1.

---

## נספח A — מסמכים וקוד שעליהם מבוסס המסמך

- [`docs/MASTER_PLAN_SOURCE_OF_TRUTH.md`](https://github.com/WizZerr/PROGRAPHER-V2/blob/main/docs/MASTER_PLAN_SOURCE_OF_TRUTH.md) — תוכנית v3.1 ההיסטורית הפעילה עד אימוץ v4 במאגר.
- [`docs/D_015_RAW_FIRST_SCOPE.md`](https://github.com/WizZerr/PROGRAPHER-V2/blob/main/docs/D_015_RAW_FIRST_SCOPE.md) — RAW-first ו־JPEG freeze.
- [`docs/D_016_PHOTOGRAPHER_FIDELITY_FIRST.md`](https://github.com/WizZerr/PROGRAPHER-V2/blob/main/docs/D_016_PHOTOGRAPHER_FIDELITY_FIRST.md) — נאמנות לצלם.
- [`docs/EXECUTION_BOARD.md`](https://github.com/WizZerr/PROGRAPHER-V2/blob/main/docs/EXECUTION_BOARD.md) — התקדמות וחסמים קיימים.
- `backend/app/lightroom_bridge/` — קוד XMP/contracts קיים; **אינו** מימוש Bridge SDK מלא.
- ניסויי Lightroom Bridge המקומיים v0.1.1/v0.2.0/v0.3.x — ראיות מדווחות של המשתמש; אינם בהכרח Commit במאגר.

## נספח B — אימוץ v4.0 במאגר (12.10.2026)

- תוכנית v3.1 המלאה נשמרה בארכיון: [MASTER_PLAN_SOURCE_OF_TRUTH_v3.1_2026-10-12.md](archive/MASTER_PLAN_SOURCE_OF_TRUTH_v3.1_2026-10-12.md).
- `docs/MASTER_PLAN_SOURCE_OF_TRUTH.md` הוא מקור האמת הפעיל v4.0; README, מצב הפרויקט, לוח הביצוע והחלטות D-018–D-021 תואמו אליו.
- לוח הביצוע ומצב הפרויקט הקודמים נשמרו כצילום מצב בארכיון.
- D-017 כבר שייך במאגר ל־Profile Learning UX, ולכן החלטות v4.0 החדשות קיבלו D-018–D-021 ולא מחקו היסטוריה.
- זהו שינוי תיעוד בלבד, ללא שינוי קוד, ללא אישור אימון, וללא קידום G0–G6; B0 עבר רק על RAW יחיד ב־Windows.

**משפט סיום:** ProGrapher לומדת את החלטות הצלם, מנהלת עריכה אמינה של אירועים שלמים ומשתמשת ב־Lightroom Classic כמנוע הפיתוח הראשון שלה — עד שתוכח הצדקה למנוע חלופי.
