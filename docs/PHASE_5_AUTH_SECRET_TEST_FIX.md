# Phase 5 — Auth secret lifecycle fix

## מה נכשל

לאחר הוספת בדיקות Phase 5, שלוש בדיקות ישנות החזירו 401.

הסיבה לא הייתה ש-Phase 5 שבר את ה-API.

מספר test modules הגדירו `PROGRAPHER_ENGINE_SECRET` לערכים שונים בזמן
pytest collection. ה-auth middleware קרא את משתנה הסביבה מחדש בכל request,
ולכן Client שנוצר עם secret אחד היה יכול לקבל secret אחר מאוחר יותר.

## התיקון

ה-secret נקרא פעם אחת בזמן `create_app()` ומועבר ל-middleware.

מכאן:
- secret של תהליך Engine נשאר קבוע לאורך חיי התהליך;
- שינוי environment מאוחר יותר אינו משנה auth של process שכבר רץ;
- בדיקות נפרדות אינן דורכות זו על זו.

זו גם התנהגות נכונה יותר ל-production, כי ה-session secret של ה-sidecar
אמור להיקבע בזמן startup ולא להשתנות באמצע הריצה.
