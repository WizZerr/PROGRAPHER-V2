# ProGrapher V2 — Phase 4B Part 2 — Tauri Sidecar

## מטרה
להפסיק להפעיל את ה-backend דרך `.venv` מתוך Tauri ולהפעיל binary ארוז כ-sidecar.

## מבנה
PyInstaller יוצר binary עצמאי אחד.
הסקריפט `backend/packaging/prepare_tauri_sidecar.py`:
1. בונה `--onefile`.
2. שואל את Rust מהו target triple של המחשב.
3. מעתיק את הקובץ אל:
   `frontend/src-tauri/binaries/prographer-engine-<target-triple>.exe`

Tauri מוגדר עם:
`bundle.externalBin = ["binaries/prographer-engine"]`

## בדיקת Windows
לאחר הכנת sidecar:
- `npm.cmd run tauri dev`
- צריך להופיע בלוג:
  `ProGrapher packaged sidecar ready: http://127.0.0.1:XXXXX`
- הממשק צריך להציג `המנוע מחובר`.
- סגירת ProGrapher צריכה לסיים את sidecar.

## הוכחה שה-.venv כבר לא משמש את Tauri
אחרי שה-sidecar נבנה אפשר, לבדיקה בלבד, לשנות זמנית את שם:
`backend/.venv` → `backend/.venv-disabled`
ולהריץ שוב `npm.cmd run tauri dev`.

אם ProGrapher עולה והמנוע מחובר, Tauri אינו תלוי ב-Python/venv בזמן הריצה.
לאחר הבדיקה מחזירים את השם ל-`.venv`.

## עדיין לא DONE
זה עדיין סביבת פיתוח. Part 3 יבנה bundle/installer של Tauri ויבדוק אותו.
macOS נשאר NOT TESTED עד שנבנה sidecar arm64 על Mac.
