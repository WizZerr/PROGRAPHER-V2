# ProGrapher Backend V2.0.0 — Event Completion + Lightroom XMP

שלב 7 והאחרון של Closed Loop V1.

## הזרימה הסופית

Event
→ AI Inference
→ Darkroom
→ Approve / Correct
→ Learning
→ Optional Candidate Profile
→ Event Completion
→ Lightroom XMP ZIP

## Final Decisions

אירוע מוכן לסיום רק כאשר לכל תמונה קיימת החלטה סופית:
- approved
- corrected

אין אישור אוטומטי שקט.

יש פעולה מפורשת:
`POST /api/events/{event_id}/completion/approve-remaining`

היא מאשרת רק תמונות שכבר קיבלו Prediction ושלא נערכו ידנית.

## XMP Export

`POST /api/events/{event_id}/completion/export`

יוצר ZIP:
- `XMP/*.xmp`
- `ProGrapher_export_manifest.json`
- `README_HE.txt`

Sidecar מקבל בדיוק את basename של ה-RAW:
`IMG_1234.CR3` → `IMG_1234.xmp`

Duplicate basenames גורמים לשגיאה במקום ליצור Sidecar לא נכון.

## Lightroom Legacy

Legacy export נשמר בשפה המקורית של Camera Raw:
- Exposure → `crs:Exposure`
- Contrast → `crs:Contrast`
- canonical Blacks → `crs:Shadows`
- Brightness → `crs:Brightness`
- Recovery → `crs:HighlightRecovery`
- Fill Light → `crs:FillLight`
- Temperature/Tint נשארים native

ProGrapher גם קורא מה-Dataset המקורי את:
- Camera Raw Version
- ProcessVersion כאשר קיים
- CameraProfile

לכן FiveK/Expert C נשאר `Version 4.5` / `ACR 4.4` במקום להמציא Process מודרני.

## Modern

Modern Recipes משתמשים ב:
- Exposure2012
- Contrast2012
- Highlights2012
- Shadows2012
- Whites2012
- Blacks2012
- Clarity2012

## Non-destructive

RAW מקורי לעולם לא משתנה.
הייצוא הוא Sidecar בלבד.

## Event Status

לאחר Export מוצלח:
- Event → `הושלם`
- Photos → `הושלם`

אם הצלם משנה החלטה לאחר מכן, ה-export מסומן stale לפי Decision Fingerprint
ואפשר לייצא ZIP מעודכן.

## DB

אין צורך באיפוס.

נוספת רק:
- `event_exports`
