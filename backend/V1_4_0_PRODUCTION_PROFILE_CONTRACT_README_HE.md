# ProGrapher Backend V1.4.0 — Recipe Contract + Production AI Profile V1

זהו שלב 1 של סגירת Closed Loop V1.

## מה השתנה

- נוסף **EditRecipe V1** — חוזה אחד רשמי לכל החלטות העריכה.
- `temperature` הוא תמיד **Kelvin מוחלט**. אין יותר ערבוב עם `-100..100` של ה-renderer הישן.
- V1 / V2 / Legacy / Baseline / Constants מתכנסים ל-Production Profile אחד.
- בחירת מקור לכל Target נעשית **רק על אותו canonical VALIDATION של Recipe V2**.
- TEST לא נקרא ולא משתתף בבחירה.
- Target שבו baseline טוב יותר מהמודל נשמר כ-baseline במקום להפעיל מודל גרוע יותר.
- Constant targets נשמרים כערכים קבועים.
- Sparse / Suspicious / Unsupported לא נפלטים ב-production inference.
- נוצר `production/production_profile_v1.json` לדיאגנוסטיקה.
- נוצר `production/production_profile_v1.joblib` ל-inference אמיתי בשלב הבא.
- נוסף `predict_production_recipe()` — entry point יחיד לשלב ה-Inference הבא.

## API

- `GET /api/ai/recipe-contract/v1`
- `GET /api/lightroom/profile-imports/{profile_id}/production-profile`
- `POST /api/lightroom/profile-imports/{profile_id}/production-profile/rebuild`

ה-GET של Production Profile בונה אותו אוטומטית אם הוא עדיין לא קיים או אם V1/V2 השתנו.

## Database

**אין צורך באיפוס Database ואין migration למסד בשלב הזה.**
ה-Production Profile נשמר בתוך תיקיית ה-AI Profile הקיימת תחת `production/`.
