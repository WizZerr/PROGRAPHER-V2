# ProGrapher — LB-01 Bridge | בדיקת מחקר בלבד

**סטטוס:** אינטגרציה למחקר בלבד. התוסף המשולב עבר בדיקת Lightroom Classic אמיתית ב-Windows על עותק RAW יחיד ב-12.10.2026: עשר התאמות Develop, פרופיל Adobe Standard, קובץ JPEG בגודל 9,154,074 bytes, ו-SHA-256 של RAW המקור ללא שינוי. בוצעו 14 בדיקות Python ממוקדות בגרסה הראשונית; תיקוני ביקורת קוד נוספים דורשים בדיקות רגרסיה. אין בכך הוכחת batch, אוטומציה ללא מגע, Mac או מוכנות מסחרית.

## לפני כל פעולה

1. גבה את **קטלוג המחקר** `ProGrapher_RAW_Test.lrcat` כאשר Lightroom סגורה. אסור לפתוח את קטלוג הצלם המקורי לניסוי.
2. ודא ש־Lightroom Classic מותקנת ושמסמך `docs/LB_01_LIGHTROOM_BRIDGE_INTEGRATION.md` נקרא.
3. השתמש רק בקובץ CR3 שהוא **העתק של תמונת מחקר מורשית** ישירות בתוך `Documents\ProGrapher_Research_Private\RAW_Parity_Test\`.
4. הבדיקה **תשנה הגדרות Develop בקטלוג המחקר** וייווצר JPEG חדש. היא לא אמורה לשנות RAW מקורי; ההאש יאומת לאחר הבדיקה.
5. השבת זמנית את תוספי POC הקודמים כדי להימנע מבחירת פריט תפריט לא נכון.

## התקנת תוסף מחקר — באופן ידני

Lightroom Classic → `File > Plug-in Manager > Add` → בחר את תיקיית `integrations\lightroom_classic\lb01\ProGrapherBridge.lrdevplugin` שבפרויקט.

אל תתקין את התוסף לתיקיות מוצר מסחרי ואל תעביר אותו לאחרים. אין עדיין מתקין או מנגנון עדכונים.

## הכנת job מקומי

פתח PowerShell בתיקיית הפרויקט:

```powershell
cd .\backend
.\.venv\Scripts\python.exe -m app.lightroom_bridge.lb01_poc prepare --raw "<ABSOLUTE_PATH_TO_YOUR_AUTHORIZED_RESEARCH_COPY.CR3>"
```

השדה `--raw` לא מוכנס לקוד או ל־GitHub; הוא נרשם רק ב־`job.txt` המקומי. אין לשלוח את `job.txt` או `result.txt` לצ'אט או למאגר כי הם מכילים נתיבי מחקר פרטיים.

## הפעלה ב־Lightroom

פתח רק את קטלוג המחקר:

`Documents\ProGrapher_Research_Private\ProGrapher_RAW_Test\ProGrapher_RAW_Test.lrcat`

לחץ `Library` בסרגל המודולים (או `G`), ואז `Library > Plug-in Extras > ProGrapher LB-01 Full Recipe Test (Research ONLY)`.

גם אם אינך רואה את התפריט במצב Develop — הפקודה מוגדרת ב־Library, ולא דורשת בחירת מסכה.

## אימות בדיקת ה־POC

אחרי הודעת Lightroom, חזור לחלון PowerShell (בתוך `backend`):

```powershell
.\.venv\Scripts\python.exe -m app.lightroom_bridge.lb01_poc verify
```

**PASS אמיתי** דורש גם profile, עשר התאמות, job_id, hash מקורי unchanged וקובץ JPEG בעל חתימה וגודל תקינים. בדיקה מקומית במחשב הפיתוח בלבד אינה מוכיחה את הרצת SDK.

אם מתקבלת עצירה, **אל תריץ את אותו job שוב ואל תמחק אוטומטית נתוני ניסוי**. אם התקלה התרחשה לאחר אימות משימה, קובץ התוצאה מכיל job_id ומצב error; אם היא התרחשה במהלך בדיקות הכניסה, התוסף לא דורס את תוצאת prepared הקיימת והודעת העצירה מוצגת ב-Lightroom. שמור את הדוח המקומי ודווח רק על stage/error ללא נתיבים רגישים. המערכת בכוונה חוסמת ניסיון שני עד לפתיחת job חדש באופן מבוקר.

## מה לא נבדק

אין עדיין Masking נתמך, Batch, לימוד צלם, עבודה ללא Lightroom, התקנה מסחרית, Mac smoke או אוטומציה שקטה ברקע. כל אלה דורשים ניסויים נפרדים.
