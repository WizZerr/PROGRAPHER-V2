# ProGrapher Frontend V16.3 — Automatic Dataset Builder

אחרי לחיצה על "צור את פרופיל ה-AI שלי" אין יותר מסך סטטי.

המסך עובר אוטומטית ל-progress של בניית Dataset ומציג שלבים פשוטים לצלם.
בסיום מוצגים מספר הזוגות התקינים ו-Train / Validation / Test.

ה-Frontend מבצע polling ל-Local Engine וממשיך להציג את ה-build גם אחרי refresh באמצעות מזהה הפרופיל ב-localStorage.
