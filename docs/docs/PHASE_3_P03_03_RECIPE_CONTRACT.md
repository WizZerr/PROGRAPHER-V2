# ProGrapher V2 — P03-03 Recipe Contract

## מה תוקן

- Process Family הוא חלק מפורש מהחוזה: `modern` או `legacy`.
- Modern Blacks: טווח `-100..100`.
- Legacy Blacks: טווח `0..100`.
- Modern Blacks `-40` נשמר ולא הופך ל-0.
- Exposure בחוזה: `-5..5 stop`.
- ערך Exposure בקצה, לדוגמה `+5`, נשמר כ-`+5.00`.
- ערך מחוץ לטווח אינו נחתך בשקט; מתקבלת שגיאת validation מפורשת.
- Modern XMP:
  - `exposure` → `Exposure2012`
  - `blacks` → `Blacks2012`
- Legacy XMP:
  - `exposure` → `Exposure`
  - legacy `blacks` → `Shadows`
  - `recovery` → `HighlightRecovery`
  - `fill_light` → `FillLight`
  - `brightness` → `Brightness`

## למה לא מאחדים Legacy ו-Modern

Legacy Blacks ו-Modern Shadows אינם אותו פרמטר. לכן אין המרה אוטומטית בין
`blacks` legacy לבין `shadows` modern.

## התנהגות Validation

המערכת אינה עושה clamp שקט לחוזי Recipe.
אם ערך אינו נתמך, הבקשה נכשלת במפורש.

זה חשוב במיוחד ל-Exposure: חוזה של ±5 אינו יכול להיחתך בפועל ל-±3 בלי דיווח.

## מה עדיין דורש Lightroom אמיתי

מיפוי ה-XMP נבדק כרגע ברמת חוזה וקוד. Round-trip אמיתי מול Lightroom נשאר
לכלי 23A ול-Phase 23 לפי ה-Master Plan.
