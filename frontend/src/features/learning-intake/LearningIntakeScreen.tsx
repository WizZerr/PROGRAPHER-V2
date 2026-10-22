"use client";

import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  attachLearningCatalog,
  createLearningProfile,
  discoverCatalogLocation,
  listLearningProfiles,
  type CatalogDiscoveryCandidate,
  type ColorMode,
  type LearningProfile,
} from "./learningIntake.api";
import styles from "./LearningIntakeScreen.module.css";

const sourceLabels = {
  smart_previews_unverified: "Smart Previews נבחרו · התאמה לתמונות עדיין לא אומתה",
  raw_fallback_unverified: "תיקיית RAW נבחרה · התאמה לקטלוג עדיין לא אומתה",
  catalog_only_limited: "קטלוג בלבד · ניתוח חזותי אינו זמין כרגע",
};

export default function LearningIntakeScreen() {
  const openView = useWorkspaceNav();
  const [profiles, setProfiles] = useState<LearningProfile[]>([]);
  const [profile, setProfile] = useState<LearningProfile | null>(null);
  const [name, setName] = useState("");
  const [photographyType, setPhotographyType] = useState("חתונה");
  const [colorMode, setColorMode] = useState<ColorMode>("color");
  const [consent, setConsent] = useState(false);
  const [catalogPath, setCatalogPath] = useState("");
  const [previewsPath, setPreviewsPath] = useState("");
  const [rawPath, setRawPath] = useState("");
  const [foundCatalogs, setFoundCatalogs] = useState<CatalogDiscoveryCandidate[]>([]);
  const [discoveryNotice, setDiscoveryNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    void listLearningProfiles()
      .then((all) => { if (alive) setProfiles(all); })
      .catch((cause) => { if (alive) setError(cause instanceof Error ? cause.message : "לא ניתן לטעון פרופילים."); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  async function create() {
    if (!name.trim() || !photographyType.trim() || !consent || busy) return;
    setError("");
    setBusy(true);
    try {
      const next = await createLearningProfile({
        name: name.trim(),
        photography_type: photographyType.trim(),
        color_mode: colorMode,
        consent,
      });
      setProfiles((old) => [next, ...old]);
      setProfile(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "יצירת פרופיל הלמידה נכשלה.");
    } finally { setBusy(false); }
  }

  function pickCatalog(candidate: CatalogDiscoveryCandidate) {
    setCatalogPath(candidate.catalog_path);
    setPreviewsPath(candidate.smart_previews_path ?? "");
    setDiscoveryNotice(candidate.smart_previews_path
      ? "Smart Previews אותרו ליד הקטלוג לפי שם התיקייה. ההתאמה לתמונות עדיין לא אומתה."
      : "לא נמצאו Smart Previews תואמים ליד הקטלוג. אפשר להמשיך בסקירת קטלוג או לבחור מקור ידנית.");
  }

  async function choose(which: "folder" | "catalog" | "previews" | "raw") {
    if (busy) return;
    const selected = await open(which === "catalog" ? {
      directory: false,
      multiple: false,
      title: "בחר קובץ Lightroom Catalog (.lrcat)",
      filters: [{ name: "Lightroom Catalog", extensions: ["lrcat"] }],
    } : {
      directory: true,
      multiple: false,
      title: which === "folder" ? "בחר תיקייה שמכילה קטלוג Lightroom"
        : which === "previews" ? "בחר Smart Previews.lrdata במיקום אחר"
        : "בחר תיקיית RAW מקורית (חלופה)",
    });
    if (!selected || Array.isArray(selected)) return;
    setError("");

    if (which === "folder" || which === "catalog") {
      setBusy(true);
      setFoundCatalogs([]);
      setCatalogPath("");
      setPreviewsPath("");
      setRawPath("");
      setDiscoveryNotice("");
      try {
        const result = await discoverCatalogLocation(selected);
        setFoundCatalogs(result.catalogs);
        if (result.catalogs.length === 1) {
          pickCatalog(result.catalogs[0]);
        } else {
          setDiscoveryNotice(`נמצאו ${result.catalogs.length} קטלוגים. בחר את הקטלוג הרצוי — לא נבחר אחד אוטומטית.`);
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "לא ניתן לסרוק את תיקיית הקטלוג.");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (which === "previews") {
      setPreviewsPath(selected);
      setDiscoveryNotice("Smart Previews נבחרו ידנית; טרם אומתה התאמה לתמונות הקטלוג.");
    }
    if (which === "raw") setRawPath(selected);
  }

  async function audit() {
    if (!profile || !catalogPath || busy) return;
    setError("");
    setBusy(true);
    try {
      const next = await attachLearningCatalog(profile.profile_id, {
        catalog_path: catalogPath,
        smart_previews_path: previewsPath || null,
        raw_fallback_path: rawPath || null,
      });
      setProfile(next);
      setProfiles((old) => old.map((p) => p.profile_id === next.profile_id ? next : p));
      setCatalogPath("");
      setPreviewsPath("");
      setRawPath("");
      setFoundCatalogs([]);
      setDiscoveryNotice("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "קריאת הקטלוג נכשלה.");
    } finally { setBusy(false); }
  }

  return <main className={styles.screen} dir="rtl">
    <header className={styles.header}>
      <span className={styles.eyebrow}>PROGRAPHER / LEARNING · 00—02</span>
      <button className={styles.back} type="button" onClick={() => openView("profile")}>חזרה לפרופיל ←</button>
      <h1>בניית פרופיל הלמידה</h1>
      <p>מתחילים מהצלם והקטלוג, לא מסקריפטים. המידע נשמר במחשב שלך; בשלב הזה אין אימון AI או שינוי בעריכות.</p>
    </header>
    <div className={styles.steps}>
      <span className={styles.stepActive}>00 · פרופיל</span>
      <span className={profile ? styles.stepActive : styles.step}>01 · קטלוג ועריכות</span>
      <span className={styles.step}>02 · נקודת התחלה — טרם אומתה</span>
    </div>
    {error && <div role="alert" className={styles.error}>{error}</div>}

    {!profile ? <div className={styles.layout}>
      <section className={styles.panel}>
        <span className={styles.kicker}>STEP 00</span>
        <h2>פרופיל אישי חדש</h2>
        <label>שם הפרופיל
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="לדוגמה: סגנון חתונות" />
        </label>
        <label>סוג צילום
          <input value={photographyType} maxLength={80} onChange={(e) => setPhotographyType(e.target.value)} placeholder="חתונה, אירועים, פורטרטים..." />
        </label>
        <label>סגנון צבע
          <select value={colorMode} onChange={(e) => setColorMode(e.target.value as ColorMode)}>
            <option value="color">צבע</option>
            <option value="black_white">שחור־לבן</option>
          </select>
        </label>
        <label className={styles.consent}><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>יש לי אישור להשתמש בקטלוגים ובתמונות לצורך למידת הפרופיל במחשב זה.</span>
        </label>
        <button className={styles.primary} type="button" disabled={!name.trim() || !photographyType.trim() || !consent || busy}
          onClick={() => void create()}>{busy ? "שומר…" : "צור פרופיל והמשך"}</button>
      </section>
      <section className={styles.panel}>
        <span className={styles.kicker}>פרופילים קיימים</span>
        <h2>המשך עבודה</h2>
        {loading ? <p>טוען פרופילים…</p> : profiles.length === 0 ? <p>עדיין אין פרופילים שמורים.</p> : profiles.map((item) =>
          <button key={item.profile_id} className={styles.existing} onClick={() => setProfile(item)} type="button">
            <strong>{item.name}</strong>
            <span>{item.photography_type} · {item.color_mode === "color" ? "צבע" : "שחור־לבן"} · {item.catalogs.length} קטלוגים</span>
          </button>,
        )}
        <p className={styles.note}>פרופיל חדש אינו Brain מאומן. כרגע אנחנו מסדרים את נתוני הלמידה.</p>
      </section>
    </div> : <div className={styles.layout}>
      <section className={styles.panel}>
        <span className={styles.kicker}>STEP 01 / CATALOG</span>
        <div className={styles.headline}>
          <h2>{profile.name}</h2>
          <button className={styles.link} type="button" onClick={() => setProfile(null)}>החלף פרופיל</button>
        </div>
        <p>בחר את התיקייה שבה נמצא קטלוג Lightroom. המערכת תאתר קובצי .lrcat ואת תיקיית Smart Previews המתאימה לצד הקטלוג, אם היא קיימת. אין צורך לבחור את שניהם בנפרד.</p>
        <button className={styles.source} disabled={busy} type="button" onClick={() => void choose("folder")}>
          <span>בחירה מומלצת · תיקיית Lightroom</span><strong>{busy ? "סורק את התיקייה…" : "בחר תיקיית קטלוג"}</strong>
        </button>
        <button className={styles.link} disabled={busy} type="button" onClick={() => void choose("catalog")}>
          או בחר קובץ ‎.lrcat ישירות
        </button>
        {foundCatalogs.length > 1 && <label className={styles.catalogChooser}>בתיקייה יש כמה קטלוגים — בחר את הנכון
          <select value={catalogPath} disabled={busy}
            onChange={(event) => {
              const selectedCatalog = foundCatalogs.find((item) => item.catalog_path === event.target.value);
              if (selectedCatalog) pickCatalog(selectedCatalog);
            }}>
            <option value="">בחר קטלוג מהרשימה</option>
            {foundCatalogs.map((item) => <option key={item.catalog_path} value={item.catalog_path}>
              {item.catalog_path.split(/[\\/]/).pop()}
            </option>)}
          </select>
        </label>}
        {catalogPath && <div className={styles.discovery}>
          <strong>קטלוג שנבחר</strong><span dir="ltr">{catalogPath}</span>
          <strong>Smart Previews</strong>
          <span dir="ltr">{previewsPath || "לא אותרו לצד הקטלוג"}</span>
          <small>{discoveryNotice}</small>
        </div>}
        <details className={styles.advanced}>
          <summary>אפשרויות מתקדמות — מיקומים אחרים</summary>
          <p>אם Smart Previews לא נמצאים ליד הקטלוג, אפשר לבחור אותם ידנית. RAW הוא חלופה כשאין Smart Previews מתאימים.</p>
          <button className={styles.source} disabled={busy} type="button" onClick={() => void choose("previews")}>
            <span>Smart Previews במיקום אחר</span><strong dir="ltr">{previewsPath || "בחר ידנית (אופציונלי)"}</strong>
          </button>
          <button className={styles.source} disabled={busy} type="button" onClick={() => void choose("raw")}>
            <span>RAW מקורי</span><strong dir="ltr">{rawPath || "בחר תיקיית RAW (אופציונלי)"}</strong>
          </button>
        </details>
        <button className={styles.primary} disabled={!catalogPath || busy} type="button" onClick={() => void audit()}>
          {busy ? "יוצר עותק זמני ובודק קטלוג…" : "בדוק ושמור קטלוג"}
        </button>
        <p className={styles.note}>הבדיקה משתמשת בעותק SQLite זמני שנמחק בסיומה. אף קובץ RAW או קטלוג מקורי לא נערך. קטלוג גדול עשוי להצריך מקום פנוי בדיסק.</p>
      </section>
      <section className={styles.panel}>
        <span className={styles.kicker}>INTAKE REPORT</span>
        <h2>מצב חומר הלמידה</h2>
        {!profile.catalogs.length ? <p>לא נבדק קטלוג עדיין. אפשר להוסיף כמה קטלוגים לאותו פרופיל.</p> :
          profile.catalogs.map((item) => <article key={item.catalog_path} className={styles.catalog}>
            <strong dir="ltr" className={styles.catalogPath}>{item.catalog_path}</strong>
            <span>{sourceLabels[item.source_status]}</span>
            <div className={styles.metrics}>
              <div><small>רשומות RAW</small><b>{item.aggregate.catalog_raw_records.toLocaleString("he-IL")}</b></div>
              <div><small>רשומות Develop מפוענחות (לא מאומתות)</small><b>{item.aggregate.parsed_raw_records.toLocaleString("he-IL")}</b></div>
              <div><small>קבוצות מועמדות</small><b>{item.aggregate.candidate_folder_day_groups.toLocaleString("he-IL")}</b></div>
              <div><small>מאומתות לאימון</small><b>0</b></div>
            </div>
            {Object.keys(item.aggregate.exclusions).length > 0 && <small>חריגות: {Object.entries(item.aggregate.exclusions).map(([key,value]) => `${key}: ${value}`).join(" · ")}</small>}
          </article>)}
        <div className={styles.warning}>
          <strong>שלב 02 — בדיקת Import מול Reset</strong>
          <p>עוד לא הוכחנו מה הייתה נקודת ההתחלה לכל צלם. לא מאמנים מודל לפני אימות זהות RAW/Smart Preview, האירועים והעריכות הסופיות.</p>
        </div>
      </section>
    </div>}
  </main>;
}
