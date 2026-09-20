# ProGrapher V2 — Phase 2 CSS Audit

## מטרת השלב
לרכז את שפת העיצוב, להסיר כפילויות ולשמור על RTL ועבודה תקינה בחלון Desktop משתנה.

## כפילויות שזוהו לפני השינוי
- אותו מבנה Hero/Placeholder שוכפל במסכי Events, Gallery, Darkroom, Profile ו-Training.
- צבעי רקע, גבולות, Radius וטקסט משני הוגדרו ידנית במספר CSS Modules.
- מצבי סטטוס (תקין / ממתין / שגיאה) הוגדרו מקומית במקום כרכיב משותף.
- מרווחי Header / Content / Cards הוגדרו במספר מקומות ללא Tokens משותפים.

## החלטות
- מקור יחיד ל-Tokens: `frontend/src/styles/tokens.css`.
- Reset וכללי בסיס: `frontend/src/app/globals.css`.
- מבנה מסך משותף: `frontend/src/components/common/FeatureScreen.*`.
- Badge משותף למצבי מערכת: `frontend/src/components/common/StatusBadge.*`.
- CSS Modules נשארים רק עבור Layout ייחודי לרכיב.
- כל UI למשתמש: עברית + RTL.
- שמות קוד וקבצים: אנגלית.

## בדיקות Phase 2
- Build production.
- Tauri dev.
- שינוי גודל חלון.
- בדיקת Sidebar במידות צרות.
- Zoom בדפדפן/WebView: 100%, 125%, 150%.
- Windows scaling: לבצע ידנית 125% ו-150% כשנגיע ל-regression checklist.
- macOS Retina: NOT TESTED עד שתהיה סביבת Mac.
