# ProGrapher V2 — Phase 5 — Local / Cloud Responsibility

## החלטת בסיס

ProGrapher V2 הוא Local-First עבור מסלול העריכה.

נשארים מקומיים:
- גישה ל-RAW.
- אינדקס האירוע.
- Cache.
- החלטות הצלם.
- Recipe / Metadata processing.
- Export.

פעולות עתידיות שיכולות להיות מרוחקות, אך אינן נדרשות לפיילוט המקומי:
- חשבון.
- רישיון.
- הורדת מודלים.
- אימון מרוחק.

הרשמה ותשלום אינם תנאי למסלול המקומי הראשון.

## Compute backend

נוסף Probe מקומי שבודק:
- OS.
- Architecture.
- CPU.
- CUDA אם PyTorch מותקן ותומך בחומרה.
- MPS אם PyTorch מותקן על macOS ותומך ב-Apple Silicon.

CPU הוא fallback בטוח.

ה-Probe אינו טוען שאיכות מודל זהה בין CPU/CUDA/MPS. לפני שימוש ב-backend
מואץ עם מודל אמיתי תידרש בדיקת תאימות ודיוק על אותו model artifact.

## Network

`GET /api/system/capabilities` אינו דורש גישה לרשת.

בשלב הזה:
`remote_services_enabled = false`

כלומר ניתוק אינטרנט אינו אמור לחסום את ה-engine המקומי.

## סטטוס מול Master Plan

P05-01 — foundation implemented.
P05-03 — responsibility boundary documented and represented in code.
P05-04 — local capability path tested without network access.
P05-05 — registration/payment explicitly outside local pilot.

P05-02 — PARTIAL.
בחירת backend קיימת, אבל חיזוי מקומי אמיתי ייסגר רק כאשר model runtime אמיתי
ייכנס ל-V2 ונבדוק CPU / CUDA / MPS מול אותו מודל.

macOS — NOT TESTED.
