# ProGrapher Backend V1.7.0 — Production Prediction → Darkroom

שלב 4 של Closed Loop V1.

## מה השתנה

ה-Darkroom כבר לא צריך את מנגנון ה-Heuristic הישן כדי להתחיל עריכה.

המסלול החדש:

Active Profile Prediction
→ canonical `prographer-edit-recipe-v1`
→ Production Darkroom
→ Preview מקורב
→ Sliders באותן יחידות של ה-Recipe

## Endpoints

- `POST /api/photos/{photo_id}/ai/darkroom/prepare`
- `POST /api/photos/{photo_id}/ai/darkroom/preview`

`prepare`:
1. משתמש ב-DEFAULT + ACTIVE Profile בלבד.
2. יוצר Prediction אם עדיין אין.
3. יוצר Preview ראשוני אם עדיין אין.
4. מחזיר Recipe canonical + Profile Version + Process Family.

`preview`:
- מקבל Recipe canonical לאחר שינוי Slider.
- יוצר Live Preview זמני.
- לא משנה את Prediction המקורית.

## Lightroom Legacy

במהלך חיבור ה-Darkroom נוסף handling מפורש ל-Legacy neutral values:
- Contrast neutral/default = 25
- Blacks neutral/default = 5
- Brightness neutral/default = 50

הערכים עצמם נשארים הערכים המקוריים ב-Recipe; רק ה-JPEG Preview יודע לפרש אותם נכון.

Temperature נשאר Kelvin מוחלט. אין חזרה ל-`-100..100`.

## Preview

ה-Preview עדיין אינו RAW renderer של Adobe.

הוא מסומן בקוד כ-approximation בלבד. ה-Recipe canonical הוא מקור האמת.
זה מאפשר לסגור את חוויית ה-Darkroom עכשיו בלי לטעון שה-JPEG renderer זהה ל-Lightroom.

## DB

אין צורך באיפוס.

נוספת רק הטבלה:
- `photo_ai_preview_renders`

אין שינוי/מחיקה של Dataset, Vision, Training, Predictions או Feedback.
