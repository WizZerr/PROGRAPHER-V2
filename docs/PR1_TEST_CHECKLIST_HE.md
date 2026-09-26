# PR #1 — Windows Manual Validation Checklist

מטרה: לבדוק את מסלול הבדיקה החדש על Windows לפני Merge ל-`ui-v2-overhaul`.

## 0. לפני שמתחילים

- [ ] לעבוד על branch `cursor/testing-ready-77c3`.
- [ ] לוודא שהאפליקציה עולה במהירות הרגילה של גרסת `ui-v2-overhaul`.
- [ ] לוודא שה-Engine מגיע ל-Ready בלי המתנה חריגה.
- [ ] לא לבדוק על חומר שאין לו גיבוי.

## 1. Smoke Test כללי

- [ ] Dashboard נפתח.
- [ ] Events נפתח.
- [ ] Gallery נפתח.
- [ ] Darkroom נפתח.
- [ ] Training / מעבדת בדיקה נפתחת.
- [ ] מעבר בין המסכים לא זורק שגיאות.
- [ ] סגירה ופתיחה מחדש שומרות את המידע המקומי.

## 2. RAW + XMP

להשתמש קודם במדגם קטן ואמיתי.

- [ ] לבחור תיקיית RAW.
- [ ] לבחור תיקיית XMP תואמת.
- [ ] לבנות בסיס RAW.
- [ ] מספר RAW נכון.
- [ ] מספר XMP נכון.
- [ ] מספר זוגות תואמים הגיוני.
- [ ] Exposure / Temperature / Tint מוצגים רק כאשר באמת קיימים.
- [ ] ערך חסר נשאר חסר ואינו הופך ל-0.
- [ ] שמות כפולים / התאמה לא חד-משמעית מסומנים ולא נכנסים לבסיס.
- [ ] XMP עם local adjustments אינו נכנס לבסיס של שלושת היעדים.
- [ ] Gallery מציגה את קבצי ה-RAW של האירוע.
- [ ] Preview אמיתי של המצלמה מופיע עבור RAW נתמך.
- [ ] פתיחת תמונה ב-Darkroom עובדת.
- [ ] מעבר קדימה/אחורה בין תמונות עובד.
- [ ] Undo / Redo עובדים.
- [ ] Exposure / Temperature / Tint ניתנים לשינוי.
- [ ] מעבר לתמונה אחרת וחזרה אינו מאבד תיקון שעדיין לא נשמר.
- [ ] "שמור תיקון/אישור" שומר Review בלי ליצור XMP.
- [ ] ההמחשה מסומנת במפורש כהמחשה ולא כתוצאת Lightroom ומגיבה גם ל-Tint.
- [ ] Export יוצר XMP בתת-תיקייה נפרדת של האירוע בתוך תיקיית הייצוא.
- [ ] קובץ RAW המקורי אינו משתנה.
- [ ] XMP קיים שלא נוצר על ידי ProGrapher אינו נדרס.
- [ ] XMP ש-ProGrapher יצר בעצמו יכול להתעדכן באופן בטוח.
- [ ] שני אירועים עם אותו filename אינם דורסים זה את זה כאשר מייצאים לאותה תיקיית יעד.

## 3. JPEG Original + JPEG Edited

להכין שתי תיקיות שונות:
`ORIGINALS` ו-`EDITS`.

- [ ] לבחור "מסלול JPEG".
- [ ] לבחור תיקיית JPEG מקור.
- [ ] לבחור תיקיית JPEG ערוך.
- [ ] לבנות Dataset.
- [ ] מספר קבצי המקור נכון.
- [ ] מספר הקבצים הערוכים נכון.
- [ ] מספר הזוגות השמישים נכון.
- [ ] קבצי RAW שנמצאים בטעות בתיקייה לא נכנסים ל-JPEG Dataset.
- [ ] שמות כפולים בין שתי מצלמות לא מתחברים בטעות לאותה עריכה.
- [ ] בחירה באותה תיקייה בדיוק כמקור וכערוך נפסלת כטעות.
- [ ] שני קבצים שונים שהם byte-identical אינם נפסלים אוטומטית.
- [ ] נוצר `manifest.json` של זוגות ה-JPEG.
- [ ] לכל זוג ב-manifest יש original path, edited path ושני fingerprints.
- [ ] UI אינו טוען שקיים כבר מודל JPEG מאומן.
- [ ] אין Export XMP במסלול JPEG.
- [ ] Gallery מציגה JPEG ומציגה ספירת JPEG אמיתית.
- [ ] JPEG preview נטען.
- [ ] הרבה previews אינם גורמים לטעינה מחדש בכל מעבר; cache עובד.

## 4. מעבר RAW ↔ JPEG

- [ ] לבנות RAW profile.
- [ ] לבצע לפחות Review אחד.
- [ ] לבנות JPEG Dataset.
- [ ] לחזור ל-RAW בלי לבנות אותו מחדש.
- [ ] RAW profile עדיין קיים.
- [ ] ה-Review של RAW עדיין קיים.
- [ ] לחזור ל-JPEG.
- [ ] JPEG Dataset עדיין קיים.
- [ ] אין ערבוב של Reviews או נתונים בין שני המסלולים.

## 5. Event / External Drive

- [ ] לפתוח אירוע מכונן חיצוני.
- [ ] לנתק את הכונן ולבדוק שהאירוע מסומן כחסר במקום לקרוס.
- [ ] לחבר מחדש.
- [ ] Relink לתיקייה הנכונה עובד.
- [ ] קבצים לא נכונים אינם מתקבלים כ-Relink של האירוע.
- [ ] אחרי Relink ה-Gallery וה-Darkroom חוזרים לעבוד.

## 6. Performance

- [ ] אירוע קטן: פתיחת Gallery מרגישה מיידית.
- [ ] אירוע של 100+ תמונות: רק thumbnails רלוונטיים נטענים.
- [ ] מעבר לתמונה שכבר נצפתה מהיר יותר בזכות preview cache.
- [ ] אין קפיצה משמעותית בזיכרון בזמן מעבר ממושך בין תמונות.
- [ ] Startup נשאר מהיר ולא חוזר לבעיה של packaged sidecar.

## 7. Automated Gate

GitHub Actions צריך לעבור:

- [ ] Backend PR1 tests.
- [ ] TypeScript `tsc --noEmit`.
- [ ] Next production build.
- [ ] Rust / Tauri `cargo check` על Windows.

## עדיין לא נחשב "עובד"

הדברים הבאים אינם טענה של PR #1 ואסור לסמן אותם כגמורים:

- Import אמיתי מ-Lightroom Catalog `.lrcat`.
- מודל JPEG מאומן.
- עריכה חכמה פר-תמונה ברמת Brain V2.
- תוצאת preview זהה ל-Lightroom.
- בדיקת macOS Apple Silicon.
- Release packaging סופי.
- טענת איכות של 70%/80%/100%.

## Gate ל-Merge

לא למזג עד ש:

1. ה-Automated Gate ירוק.
2. RAW manual smoke test עובר.
3. JPEG manual smoke test עובר.
4. מעבר RAW/JPEG שומר את שני המסלולים.
5. אין regression ב-startup.
6. אין כתיבה לקבצי המקור.
