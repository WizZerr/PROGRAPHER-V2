# ProGrapher Backend V0

זהו ה-Backend המקומי הראשון של ProGrapher.

המטרה של V0 היא **לא AI עדיין**. המטרה היא לחבר את האתר שלך אל המחשב ולגרום לזרימה הבסיסית לעבוד באמת:

**יצירת אירוע → העלאת תמונות → שמירה מקומית → יצירת Preview → הצגה באתר**

## מה כבר בנוי

- FastAPI.
- SQLite.
- יצירת אירועים.
- עריכת פרטי אירוע.
- העלאת כמה תמונות בבת אחת.
- שמירת Originals ללא שינוי.
- יצירת Previews ל-JPEG / PNG / WEBP / TIFF.
- תמיכה אופציונלית ב-RAW דרך rawpy.
- רשימת תמונות לאירוע.
- API לפרופיל הסגנון.
- העלאת זוג Original + Edited ללימוד הסגנון.
- API לשמירת Feedback של העורך.
- סטטיסטיקות Acceptance Rate.
- נתוני CPU / RAM / Disk.
- זיהוי RTX דרך `nvidia-smi`.
- CORS מוכן ל:
  - localhost
  - https://prographer.proride.co.il

## התקנה מחר במחשב

1. חלץ את ה-ZIP לתיקייה, לדוגמה:
   `C:\Users\Matan\Desktop\ProGrapher_Backend_V0`

2. ודא שמותקן Python 3.11 או 3.12.

3. הפעל:
   `setup_windows.bat`

4. בסוף ההתקנה הפעל:
   `start_backend.bat`

5. פתח:
   `http://127.0.0.1:8000/docs`

אם אתה רואה Swagger עם כל ה-API - המנוע עובד.

## בדיקה מהירה

אפשר להריץ:
`check_backend.bat`

או לפתוח בדפדפן:
`http://127.0.0.1:8000/api/health`

## איפה נשמרות התמונות

ברירת מחדל:

`ProGrapher_Backend_V0\data\events\<EVENT_ID>\`

ובתוך כל אירוע:

- `originals`
- `previews`
- `edited`
- `metadata`

### אם אתה רוצה כונן ייעודי

ערוך את `.env` ושנה:

`PROGRAPHER_DATA_DIR=D:\ProGrapherData`

כך כל התמונות וה-DB יישמרו מחוץ לתיקיית הקוד.

## RAW

ב-setup ישאל אותך אם להתקין תמיכת RAW.

אם תבחר כן, יותקן `rawpy`.

בשלב הראשון אני ממליץ לבדוק קודם עם 10 JPG.
אחרי שהזרימה עובדת, עוברים ל-RAW.

## API עיקרי

- `GET /api/health`
- `GET /api/system`
- `GET /api/stats`
- `GET /api/events`
- `POST /api/events`
- `GET /api/events/{id}`
- `PATCH /api/events/{id}`
- `POST /api/events/{id}/photos`
- `GET /api/events/{id}/photos`
- `GET /api/photos/{id}`
- `POST /api/photos/{id}/feedback`
- `GET /api/style/profile`
- `PUT /api/style/profile`
- `POST /api/style/pairs`
- `GET /api/style/pairs`

## אבטחה

V0 מיועד כרגע למחשב שלך בלבד.

לפני שנפתח את המנוע בצורה קבועה דרך:
`engine.prographer.proride.co.il`

נוסיף שכבת אימות מסודרת ונחבר Tunnel מאובטח.

**לא לפתוח פורט 8000 ישירות בראוטר לאינטרנט.**

## מחר - מה עושים ביחד

אחרי שתפעיל את ה-Backend ותשלח לי מה מופיע ב:
`http://127.0.0.1:8000/api/health`

נעשה:

1. חיבור מאובטח מהמחשב החוצה.
2. כתובת engine.prographer.proride.co.il.
3. נחבר את Frontend V3 ל-API.
4. ניצור אירוע אמיתי דרך האתר.
5. נעלה 10 JPG מהאתר.
6. נוודא שהם הגיעו למחשב שלך.
7. נציג thumbnails אמיתיים באתר.

רק אחרי שזה עובד מושלם עוברים למנוע העריכה ול-RTX 4070.
