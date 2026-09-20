# ProGrapher V0.9 — Batch Brain Analyzer + Training Lab V1

## מה חדש ב-V0.9

### 1) ניתוח Batch לאירוע שלם
Endpoints חדשים:

- `GET /api/events/{event_id}/brain/coverage`
- `POST /api/events/{event_id}/brain/analyze-all`
- `POST /api/events/{event_id}/brain/analyze-missing`

המטרה:
- לנתח את כל התמונות באירוע בלי לעבור ידנית photo_id אחרי photo_id
- לשמור embedding + semantics לכל תמונה
- לבנות coverage אמיתי של המוח על האירוע

### 2) Training Lab V1
קבצים חדשים:

- `training_lab/common.py`
- `training_lab/train_recipe_model.py`
- `training_lab/evaluate_recipe_model.py`
- `training_lab/predict_recipe.py`
- `requirements-train.txt`
- `install_training_lab.bat`

## Workflow מומלץ

1. להעלות אירוע
2. להריץ:
   - `POST /api/brain/warmup`
3. להריץ:
   - `POST /api/events/{event_id}/brain/analyze-all`
4. לאסוף feedback / תיקונים
5. להריץ:
   - `POST /api/brain/dataset/export`
6. להתקין training deps:
   - `install_training_lab.bat`
7. לאמן:
   - `.venv\Scripts\python.exe training_lab\train_recipe_model.py`
8. להעריך:
   - `.venv\Scripts\python.exe training_lab\evaluate_recipe_model.py`

## איך מאמנים אותו להיות טוב באמת

הדרך הנכונה:
- לצבור הרבה תמונות עם embedding
- לצבור feedback / corrected / approved
- עדיף מאוד בעתיד להוסיף יבוא עריכות אמיתיות מ-Lightroom/XMP
- למדוד לא רק loss אלא Acceptance Rate בעולם האמיתי

## מה V1 של האימון עושה

המודל לומד מתוך:
- embedding של התמונה
- EXIF בסיסי
- סיכום semantic של scene / lighting / people / framing / technical

והוא מנסה לנבא:
- exposure
- highlights
- shadows
- whites
- blacks
- contrast
- temperature
- vibrance
- clarity

כרגע זה עדיין Training Lab, לא מנוע inference מחובר ל-Frontend.
המטרה שלו היא להוכיח שה-data pipeline עובד ושהלמידה מתחילה להיות אפשרית.
