# ProGrapher Backend V2.1.0 — Product Finish

זהו Product Finish Pass אחרי סגירת Closed Loop V1.

## Photographer Profile Overview

נוסף endpoint יציב ונקי:

`GET /api/ai/profile/overview`

הוא מחזיר רק מידע שמעניין צלם:
- Profile פעיל + גרסה.
- מקור הסגנון.
- החלטות שנלמדו.
- כמה אושרו וכמה תוקנו.
- Acceptance Rate כאשר יש מספיק נתונים.
- התקדמות לגרסה חדשה.
- Candidate READY אם קיים.
- העדפות שהצלם הגדיר ב-Onboarding.

ה-endpoint בכוונה לא מחזיר:
- MAE / P90 / P95
- Dataset Integrity
- CLIP Embeddings
- Sparse / Suspicious / Provenance
- Recipe V1/V2
- Feature Importance
- TEST / VALIDATION internals

כל החומר הטכני ממשיך להיות זמין ב-Diagnostics בלבד.

## Database

אין שינוי Schema ואין צורך באיפוס Database.
