# ProGrapher V2 — Phase 4B Part 3 — Windows Installer

## מטרה

לבנות מתקין Windows אמיתי של ProGrapher שמכיל גם את ה-Tauri app וגם את
ה-Python Engine הארוז כ-sidecar.

## פורמט

בשלב הזה משתמשים ב-NSIS בלבד (`*-setup.exe`).

ההתקנה מוגדרת ל-`currentUser`, ולכן אינה אמורה לדרוש הרשאות Administrator
רק כדי להתקין את ProGrapher.

WebView2 מוגדר כ-`downloadBootstrapper`. ב-Windows 10/11 הוא בדרך כלל כבר
קיים; אם חסר, המתקין רשאי להשלים אותו.

## Build

מתוך `backend`:

```powershell
.\.venv\Scripts\python.exe .\packaging\build_windows_installer.py
```

הסקריפט:
1. בונה מחדש את ה-Python sidecar.
2. מעתיק אותו בשם target-triple ש-Tauri דורש.
3. מריץ Tauri release build.
4. בונה NSIS setup.
5. מדפיס `WINDOWS_INSTALLER_READY=...`.

לאחר מכן:

```powershell
.\.venv\Scripts\python.exe .\packaging\verify_windows_installer.py
```

## בדיקת התקנה אמיתית

1. לסגור את `tauri dev`.
2. להפעיל את קובץ `*-setup.exe`.
3. להשלים התקנה.
4. להפעיל ProGrapher מתפריט Start / קיצור הדרך של ההתקנה.
5. לוודא שהממשק עולה.
6. לוודא שמופיע `המנוע מחובר`.
7. לסגור את ProGrapher ולוודא שהוא נסגר בלי Engine שנשאר ברקע.
8. לפתוח שוב ולוודא שהחיבור חוזר.

בשלב הזה SmartScreen/Unknown Publisher אפשרי כי עדיין אין Code Signing.
זו אינה בדיקת חתימה; חתימה תטופל לפני הפצה חיצונית.

## תנאי מעבר

Part 3 עובר בצד Windows כאשר:
- installer נבנה,
- installer מותקן,
- האפליקציה המותקנת עולה,
- sidecar עולה מתוך ההתקנה,
- סגירה ופתיחה מחדש עובדות.

בדיקה על מחשב Windows נקי ללא Python/Node/Rust עדיין נדרשת כדי לסגור את
דרישת ה-clean-machine של Phase 4B.

macOS Apple Silicon נשאר NOT TESTED.
