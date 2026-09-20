# ProGrapher Backend V1.9.0 — Adaptive Retraining / Candidate Profile

שלב 6 של Closed Loop V1.

## מה נסגר

Production Learning Samples הופכים עכשיו לגרסת Profile חדשה.

הזרימה:

ACTIVE Profile V1
→ 20+ החלטות צלם
→ deterministic TRAIN / VALIDATION split
→ residual context models
→ Validation מול העריכה הסופית של הצלם
→ רק Targets שמשתפרים נכנסים
→ Candidate Profile V2 = READY
→ הפעלה מפורשת בלבד

## למה Residual Learning

המערכת לא זורקת את המודל המקורי.

היא לומדת:
`Photographer Final - Current Active Profile`

כלומר Candidate חדש הוא:
`Current Active Profile + contextual correction layer`

כך גם אישורים (`delta=0`) וגם תיקונים מלמדים את המערכת.

## למידה מצטברת

ה-Retraining משתמש בכל ה-current learning samples של אותו Registry,
גם אם הם נוצרו בגרסאות Profile קודמות.

לכל Sample מחושבת מחדש התחזית של ה-ACTIVE Profile הנוכחי,
ואז נלמד Residual חדש מול ה-Final Recipe.

כך V3 בעתיד יכול ללמוד מההיסטוריה כולה ולא רק מהאירוע האחרון.

## Validation

- מינימום 20 Decisions.
- ~20% נשמרים ל-Learning Validation.
- TEST של FiveK לא משמש לבחירת Candidate.
- כל Target חייב מספיק Variation.
- Residual Target נכנס רק אם Validation MAE משתפר לפחות 2%.

אם שום Target לא משתפר:
`status = no_improvement`
ולא נוצרת גרסת Profile חדשה.

## Candidate

גרסה חדשה נרשמת ב-Profile Registry כ-`READY`.

היא **לא** מחליפה את ה-ACTIVE Profile לבד.

רק Activation מפורש הופך:
- V1 → SUPERSEDED
- V2 → ACTIVE

## API

- `GET /api/ai/retraining/status`
- `POST /api/ai/retraining/start`

Activation ממשיך להשתמש ב:
- `POST /api/ai/profiles/{registry_id}/versions/{version_id}/activate`

## DB

אין צורך באיפוס.

נוספת רק:
- `ai_retraining_runs`

Learning Samples, Events, Vision, Dataset וכל ה-Profile Versions הקיימים נשארים.
