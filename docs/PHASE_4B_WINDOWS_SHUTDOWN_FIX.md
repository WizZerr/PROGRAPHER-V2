# Phase 4B — Windows Sidecar Shutdown Fix

## התקלה שאושרה

לאחר סגירת ProGrapher המותקן נשאר `prographer-engine.exe` פעיל.

הסיבה הסבירה היא מבנה `PyInstaller --onefile`: יש process ראשי ותהליך child
שנוצר בזמן חילוץ/הרצה. `CommandChild.kill()` של Tauri מסיים PID אחד בלבד,
ולכן תהליך נוסף יכול להישאר orphan.

## התיקון

ב-Windows נשמר ה-PID של ה-sidecar ובסגירת האפליקציה מופעל:

`taskkill.exe /PID <pid> /T /F`

הדגל `/T` מסיים את כל עץ התהליכים. אם הפעולה נכשלת, הקוד חוזר ל-
`CommandChild.kill()` כ-fallback.

`CREATE_NO_WINDOW` מונע חלון CMD קופץ בזמן shutdown.

## בדיקת קבלה

1. לבנות מחדש installer.
2. להתקין.
3. לפתוח ProGrapher מתפריט Start.
4. לסגור באמצעות X.
5. להמתין 2–3 שניות.
6. להריץ:
   `tasklist | findstr /I "prographer-engine"`
7. אין פלט = PASS.
8. לחזור על פתיחה/סגירה פעם נוספת.
9. להסיר את ProGrapher בלי taskkill ידני.

macOS lifecycle נשאר NOT TESTED.
