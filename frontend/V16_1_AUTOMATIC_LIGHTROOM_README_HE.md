# ProGrapher Frontend V16.1 — Automatic Lightroom Intelligence

הממשק החדש נועד לצלם/עורך רגיל ולא למפתח.

## ה-flow
1. המשתמש לוחץ רק `חבר את Lightroom`.
2. אם נמצא קטלוג אחד — ProGrapher מנתח אותו אוטומטית.
3. אם נמצאו כמה — המשתמש בוחר קטלוג ואז הניתוח מתחיל אוטומטית.
4. המשתמש רואה רק:
   - תמונות מקור
   - תמונות עם עריכה
   - אחוז קבצים זמינים
   - קבוצות עריכה מתאימות
5. כל Adobe_images / Develop History / Virtual Copies / tables נשארים מאחורי הקלעים.
6. המשתמש בוחר קבוצת עריכה רלוונטית ויוצר Professional AI Profile.

יש fallback קטן לנתיב ידני רק אם הקטלוג לא נמצא אוטומטית.
