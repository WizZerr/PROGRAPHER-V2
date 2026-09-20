# ProGrapher Frontend V18.0.2 — Style Setup Hotfix

Fresh-start smoke test bug fixed.

## Bug
On a brand-new account, "בנה את פרופיל ה-AI שלי" looked clickable but did not
begin the Lightroom connection flow.

That is incorrect: this button IS the entry point for connecting Lightroom.

## Fix
The first-time CTA now:
1. Clears stale setup state.
2. Opens `style-setup`.
3. Scrolls to the setup.
4. Immediately runs Lightroom catalog discovery.

Expected behavior after one click:
- If one Lightroom catalog is found -> ProGrapher analyzes it automatically.
- If multiple catalogs are found -> the setup screen lets the photographer choose.
- If none are found -> the setup screen remains open and offers manual `.lrcat` path entry.

No backend or database change is required.
