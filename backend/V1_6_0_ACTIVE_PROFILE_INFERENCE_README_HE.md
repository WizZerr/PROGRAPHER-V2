# ProGrapher Backend V1.6.0 — Active Profile Inference

זהו שלב 3 של Closed Loop V1.

## מה נסגר עכשיו

לראשונה ה-Production AI Profile הפעיל מחובר לתמונות של אירוע אמיתי:

RAW / Photo
→ Vision באותו preprocessing ששימש באימון
→ DEFAULT + ACTIVE AI Profile
→ Production Recipe Contract V1
→ Prediction נשמרת לתמונה

## חשוב: Train / Inference parity

לפני הגרסה הזו, ניתוח תמונות אירוע השתמש ב-JPEG preview של האתר.
האימון של FiveK השתמש ב-RAW embedded preview / rawpy.

V1.6.0 מסיר את הפער הזה:
Production Vision משתמש ב-`load_vision_image()` וב-`extract_training_metadata()`
בדיוק כמו Training Vision.

## DB

אין שום צורך באיפוס Database.

נוספות שתי טבלאות בצורה additive/idempotent:
- `photo_ai_predictions`
- `event_ai_inference_jobs`

שום Dataset / Vision / Training / Event קיים לא נמחק.

## Inference

Prediction נשמרת עם:
- photo_id
- registry_id
- ACTIVE profile_version_id
- profile_version_number
- brain_analysis_id
- Recipe Contract version
- canonical recipe
- provenance

אותה תמונה + אותה גרסת Profile + אותו Vision לא מחושבים שוב.

## Event batch

חדש:
- `POST /api/events/{event_id}/ai/inference/start`
- `GET /api/events/{event_id}/ai/inference/status`

העבודה רצה ב-thread ברקע ומדווחת progress.
אם המנוע מופעל מחדש, job מסומן interrupted/failed אבל Predictions שכבר נשמרו נשארות,
ובהרצה חדשה הן reused במקום להתחשב מחדש.

## Per-photo

חדש:
- `POST /api/photos/{photo_id}/ai/infer`
- `GET /api/photos/{photo_id}/ai/prediction-latest`

## מה עדיין לא משתנה

ה-Darkroom הישן עדיין לא משתמש ב-Production Recipe לצורך rendering/sliders.
זה בכוונה: זהו שלב 4 הבא.

Stage 3 אחראי לכך שהמוח האמיתי כבר מסוגל לעבור על אירוע חדש ולהפיק Prediction תקנית לכל תמונה.
