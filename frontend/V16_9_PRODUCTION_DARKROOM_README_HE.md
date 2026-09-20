# ProGrapher Frontend V16.9 — Production Darkroom

שלב 4 של Closed Loop V1.

## השינוי העיקרי

פתיחת תמונה ב-Darkroom כבר לא מבקשת:
- "נתח תמונה"
- Recipe heuristic
- Style DNA הישן
- Render מהמתכון הישן

במקום זה:

תמונה
→ ACTIVE AI Profile
→ Production Prediction
→ Darkroom
→ Preview
→ Sliders

## Sliders

המחוונים נטענים ישירות מה-Recipe של Production Profile.

Temperature מוצג ונערך ב-Kelvin אמיתי.

Targets שלא קיימים ב-Production Recipe לא מוצגים כאילו נלמדו.

בפרופיל FiveK Legacy הנוכחי מוצגים גם:
- Brightness
- Recovery
- Fill Light

עם neutral values נכונים ל-Legacy Preview.

## חשוב

ה-Preview עדיין מסומן כקירוב בלבד.
הוא אינו Lightroom/Adobe RAW renderer.

בשלב 5 נחבר Approve / Correct ל-Prediction + Profile Version וללמידה החדשה.
לכן בגרסה הזו לא נשלח Production Recipe למנגנון Style DNA הישן.
