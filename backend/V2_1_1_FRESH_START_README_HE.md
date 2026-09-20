# ProGrapher V2.1.1 — Fresh Start / Hard Reset

מיועד בדיוק ל-Smoke Test של התקנה חדשה כאילו המוצר התחיל את חייו על מכונה חדשה.

## HARD RESET

1. סגור `start_backend.bat`.
2. הרץ `HARD_RESET_FRESH_INSTALL.bat`.
3. הקלד `HARDRESET`.

הסקריפט קורא את `PROGRAPHER_DATA_DIR` האמיתי מתוך `.env`,
ולא מניח שה-Data נמצא דווקא בתיקיית `./data`.

הוא מוחק את כל Runtime/Product Data, כולל:
Users, Events, Photos, Lightroom imports, datasets, Vision records,
Production Profiles, Versions, Predictions, Learning, Retraining ו-XMP exports.

הוא לא מוחק:
- Source
- `.env`
- `.venv`
- Python packages
- Hugging Face/Foundation model cache

אלה Dependencies/Deployment Configuration ולא Product Data.

## אימות

לאחר ה-Reset:
1. הפעל `start_backend.bat`.
2. הרץ `VERIFY_FRESH_INSTALL.bat`.

PASS אומר:
- Schema נבנה מחדש בהצלחה.
- Users = 0
- Events = 0
- Photos = 0
- AI Profiles = 0
- Predictions = 0
- Learning = 0
- Retraining = 0
- Exports = 0

## Browser

Session ישן הופך לא תקף ברגע שה-DB נמחק, וה-Frontend מוחק אותו אוטומטית.
ב-Registration חדש גם pointer ישן של Lightroom Profile מנוקה מה-localStorage.

## Fix נוסף

`/api/health` מדווח עכשיו על Version `2.1.1` במקום version ישן שנשאר בטעות.
