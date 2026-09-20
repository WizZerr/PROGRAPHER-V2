# ProGrapher Backend V1.8.0 — Production Learning Capture

שלב 5 של Closed Loop V1.

## מה נסגר עכשיו

לראשונה אישור ותיקון ב-Darkroom נרשמים כ-Ground Truth נקי של ה-Production AI Profile.

הזרימה:

ACTIVE Profile Prediction
→ הצלם מאשר או מתקן
→ נשמר AI Recipe
→ נשמר Photographer Final Recipe
→ נשמר Delta
→ נשמר Profile Version
→ נשמר Vision/EXIF/Semantic feature snapshot
→ מוכן ל-Retraining בשלב 6

## הפרדה מוחלטת מ-Style DNA הישן

Stage 5 **לא** כותב לטבלת `feedback` הישנה ולא מזין את `Style DNA V1`.

הסיבה:
- Temperature החדש הוא Kelvin מוחלט.
- Lightroom Legacy נשמר בערכים native.
- אסור לערבב אותם עם ה-Recipe הישן.

הטבלה החדשה:
- `ai_learning_samples`

## למה נשמר Feature Snapshot

כל Sample שומר עותק של input המודל:
- CLIP embedding
- Semantic Context
- EXIF / metadata

לכן גם אם אירוע נמחק אחר כך, הדוגמה עדיין יכולה לשמש ל-Retraining.
ה-FK לתמונה/אירוע/Prediction מוגדר `ON DELETE SET NULL` ולא מוחק את Sample.

## Revisions

לכל Prediction יש Decision נוכחי אחד.

אם הצלם משנה החלטה:
- ההחלטה הישנה נשארת להיסטוריה עם `is_current=0`
- ההחלטה החדשה מקבלת `is_current=1`
- `supersedes_sample_id` שומר את השרשרת

Stage 6 משתמש רק ב-current decisions.

## API

- `GET /api/photos/{photo_id}/ai/decision-latest`
- `POST /api/photos/{photo_id}/ai/decision`
- `GET /api/ai/learning/summary`

POST payload:

אישור:
```json
{"verdict":"approved"}
```

תיקון:
```json
{
  "verdict":"corrected",
  "photographer_recipe": {
    "exposure": 1.15,
    "temperature": 5200
  }
}
```

השרת תמיד לוקח את AI Recipe ואת Profile Version מה-Prediction הפעילה בעצמו.

## DB

אין צורך באיפוס Database.

נוספת רק טבלת `ai_learning_samples`.
שום Training / Dataset / Vision / Event / Prediction קיים לא נמחק.
