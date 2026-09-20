# ProGrapher V2 — Phase 3 Backend Audit

## מטרת השלב
להפריד את מנוע FastAPI למודולים קטנים, לשמור את חוזי ה-API שכבר עובדים, ולהכין תשתית ניידת ל-Windows ול-macOS.

## מה בוצע בחבילה הזאת

### P03-01 — Backend refactor
- `main.py` נשאר entry point קטן.
- יצירת האפליקציה עוברת ל-`application.py`.
- Routes עוברים ל-`app/api/routes/`.
- Security עובר ל-`app/core/security.py`.
- Config עובר ל-`app/core/config.py`.
- Services עוברים ל-`app/services/`.
- Schemas עוברים ל-`app/schemas/`.

### P03-02 — Metadata
- Metadata נקרא דרך `exifread`.
- שדה חסר נשמר כ-`None`.
- אין יותר fallback שקט ל-0.
- קובץ שלא קיים / אינו קובץ / נכשל בקריאה מחזיר שגיאה מפורשת.
- נוסף endpoint מאובטח: `POST /api/metadata/read`.

### P03-04 — Portability foundation
- שימוש ב-`pathlib.Path`.
- נתיבי Data/Cache מוגדרים לפי מערכת ב-`app/platform/paths.py`.
- אין BAT ואין נתיבי Windows קשיחים בקוד החדש של ה-backend.

## מה עדיין לא מסומן DONE

### P03-03 — Recipe / Exposure / Blacks / Legacy XMP
ה-V2 החדש עדיין לא מכיל את מנגנון Recipe/XMP הסופי ולכן אסור לטעון שתוקנו טווחי Blacks/Exposure או Legacy mapping.
את החוזים האלה נכניס ונבדוק כשנבנה את שכבת Recipe/Lightroom המתאימה.

### macOS
הקוד נכתב בצורה ניידת, אבל macOS נשאר NOT TESTED עד להרצה אמיתית על Mac.

## בדיקות
- `pytest`
- `/health`
- `/api/runtime` עם ובלי secret
- metadata של קובץ חסר
- metadata חסר נשמר כ-None ולא 0
