# ProGrapher Backend V1.5.0 — Profile Registry + Active Version

זהו שלב 2 של Closed Loop V1.

## מה נוסף

- `ai_profile_registries` — Registry מסודר לכל סגנון/AI Profile.
- `ai_profile_versions` — גרסאות immutable של Production Profile.
- הגרסה הראשונה נרשמת אוטומטית כ-`ACTIVE`.
- גרסה חדשה בעתיד נרשמת כ-`READY` ולא מחליפה Production אוטומטית.
- הפעלה של גרסה חדשה היא פעולה מפורשת ואטומית.
- נשמרת היסטוריית גרסאות (`ACTIVE` / `READY` / `SUPERSEDED`).
- לכל משתמש יכול להיות Profile ברירת מחדל אחד.
- ה-Artifact של כל Version מועתק ל-snapshot נפרד, כך ש-Rebuild עתידי לא משנה גרסה שכבר הייתה פעילה.
- Rebuild זהה לא יוצר Version מזויף: יש fingerprint ודדופליקציה.
- נוסף resolver יחיד ל-Stage 3 שמחזיר רק את ה-DEFAULT + ACTIVE Profile.

## מיגרציית DB

אין צורך, ואסור, לאפס את ה-Database.

ב-restart הראשון נוצרות שתי טבלאות חדשות בצורה additive/idempotent בלבד.
שום טבלה קיימת לא נמחקת ושום Dataset/Vision/Training/Event לא מאופס.

## API

- `GET /api/ai/profiles`
- `GET /api/ai/profiles/active`
- `GET /api/ai/profiles/{registry_id}`
- `POST /api/ai/profiles/{registry_id}/make-default`
- `POST /api/ai/profiles/{registry_id}/versions/{version_id}/activate`
- `POST /api/lightroom/profile-imports/{profile_id}/production-profile/register`

## Lifecycle

```
Production Profile
      ↓
Registry Version 1
      ↓
ACTIVE

future retrain/rebuild
      ↓
Registry Version 2
      ↓
READY
      ↓ explicit activation
Version 1 = SUPERSEDED
Version 2 = ACTIVE
```

## Files

Version snapshots live under:

`data/ai_profiles/<user>/<profile>/registry/versions/v0001/`

Each version contains:
- `production_profile.joblib`
- `production_profile.json`
