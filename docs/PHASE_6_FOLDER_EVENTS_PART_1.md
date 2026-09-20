# ProGrapher V2 — Phase 6 Part 1 — Folder-based Events

## מה נוסף

- Native folder picker דרך Tauri Dialog plugin.
- בחירת תיקייה מקומית, ללא browser upload.
- סריקה רק של פורמטי צילום נתמכים.
- RAW נשאר במקום ונקרא Read-only.
- SQLite מקומי תחת תיקיית נתוני ProGrapher.
- אירועים נשמרים בין הפעלות.
- פתיחת אותה תיקייה שוב מעדכנת את אותו אירוע ולא יוצרת אירוע כפול.
- קובץ זהה פיזית שמופיע פעמיים באותו אירוע מזוהה באמצעות fingerprint ולא מוכפל.
- נתיבים ושמות Unicode/עברית נשמרים.

## Fingerprint

בשלב זה זהות קובץ מחושבת לפי:
- גודל,
- 64KiB ראשונים,
- 64KiB אחרונים.

זהו fingerprint לזיהוי/Relink, לא full-file cryptographic hash.
Phase מאוחר יותר יכול להוסיף full hash במקום שבו שלמות מקור מחייבת זאת.

## מה עדיין נשאר ל-Part 2

- סריקה מדורגת עם progress אמיתי לאירועים גדולים.
- מצב Missing ברור כשכונן או קובץ אינם זמינים.
- Relink של אירוע לתיקייה שעברה מיקום.
- בדיקת כונן חיצוני בפועל.
- בדיקות macOS/Finder/case sensitivity.

לכן Phase 6 עדיין אינו DONE אחרי Part 1.
