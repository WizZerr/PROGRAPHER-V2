# ProGrapher V13.5.1 — Build Fix

תוקנה שגיאת TypeScript ב-build:

`onClick={refreshBackend}`

הפונקציה `refreshBackend` מקבלת פרמטר boolean אופציונלי, ולכן React ניסה להעביר אליה MouseEvent.

הכפתור שונה ל:

`onClick={() => refreshBackend(true)}`

אין שינוי עיצובי או לוגי אחר בגרסה הזו.
