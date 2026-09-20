# Phase 4B — WebView2 Offline Installer Fix

## הבעיה

ב-Windows Sandbox נקי, המתקין עם `downloadBootstrapper` הוריד את WebView2
אבל נתקע בשלב ההתקנה שלו.

## החלטה

להחליף את:

`downloadBootstrapper`

ב:

`offlineInstaller`

כך שה-NSIS setup יכיל את מתקין WebView2 המלא ולא יהיה תלוי בהורדה בזמן
התקנת ProGrapher.

## השפעה

- מתקין ProGrapher גדל משמעותית (Tauri מתעד בערך 127MB תוספת).
- התקנת ProGrapher יכולה להשלים WebView2 גם בסביבה ללא אינטרנט.
- Windows שכבר כולל WebView2 יכול להמשיך להשתמש ב-runtime המותקן במערכת.

## בדיקת קבלה

1. לבנות מחדש את המתקין.
2. לפתוח Windows Sandbox חדש.
3. להעביר לתוכו רק את setup.exe החדש.
4. להתקין ללא Python / Node / Rust.
5. לפתוח ProGrapher.
6. לוודא `המנוע מחובר`.
7. לסגור עם X.
8. לוודא שאין `prographer-engine.exe`.
9. להסיר ProGrapher בצורה רגילה.
