# ProGrapher Frontend V18.0.1 — Fresh Start Hygiene

שינוי קטן שמיועד ל-Hard Reset / First Run:

כאשר נרשם משתמש חדש, ה-Frontend מוחק מהדפדפן
`prographer_active_ai_profile_import` ישן ומאפס את מצבי בניית ה-Profile.

Session ישן כבר מנוקה אוטומטית כאשר `/api/auth/me` מחזיר Unauthorized
לאחר Hard Reset.

כך Browser שכבר שימש לפיתוח מתנהג כמו Browser של משתמש חדש.
