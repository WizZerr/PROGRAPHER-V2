"use client";

import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  analyzeCatalog,
  attachLearningCatalog,
  createLearningProfile,
  deleteLearningProfile,
  discoverCatalogLocation,
  listLearningProfiles,
  type AnalysisSample,
  type CatalogAnalysisSummary,
  type CatalogDiscoveryCandidate,
  type CatalogIntake,
  type ColorMode,
  type LearningProfile,
  type StyleSlider,
} from "./learningIntake.api";
import styles from "./LearningIntakeScreen.module.css";

const sliderName: Record<string, string> = {
  Exposure2012: "חשיפה", Contrast2012: "ניגודיות", Highlights2012: "הבהרות", Shadows2012: "צללים",
  Whites2012: "לבנים", Blacks2012: "שחורים", Texture: "טקסטורה", Clarity2012: "Clarity", Dehaze: "Dehaze",
  Vibrance: "Vibrance", Saturation: "רוויה", Temperature: "טמפרטורה", Tint: "Tint",
};

type Phase = "idle" | "reading" | "analyzing";

function fileName(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function sliderValue(key: string, value: number) {
  if (key === "Exposure2012") return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
  if (key === "Temperature") return `${Math.round(value).toLocaleString("he-IL")}K`;
  const rounded = Math.round(value);
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

function Value({ k, v }: { k: string; v: number }) {
  return <bdi dir="ltr">{sliderValue(k, v)}</bdi>;
}

function StyleLine({ title, sliders, range }: { title: string; sliders: StyleSlider[]; range?: boolean }) {
  if (!sliders.length) return null;
  return <div className={styles.styleLine}>
    <span>{title}</span>
    <div className={styles.chips}>{sliders.map((s) => <span key={s.key} className={styles.chip}>
      {sliderName[s.key] ?? s.key}{" "}
      {range ? <>(<Value k={s.key} v={s.p10}/> עד <Value k={s.key} v={s.p90}/>)</> : <Value k={s.key} v={s.median}/>}
    </span>)}</div>
  </div>;
}

function CatalogSummary({ catalog, summary, samples, busy, onReanalyze }: {
  catalog: CatalogIntake;
  summary: CatalogAnalysisSummary;
  samples: AnalysisSample[];
  busy: boolean;
  onReanalyze: () => void;
}) {
  const fixed = summary.style.filter((s) => s.kind === "fixed");
  const perPhoto = summary.style.filter((s) => s.kind === "per_photo");
  const untouched = summary.style.filter((s) => s.kind === "untouched");
  const rare = summary.style.filter((s) => s.kind === "rare");
  const savings = summary.savings;
  const missing = summary.photos - summary.linked;
  return <section className={styles.summary}>
    <div className={styles.summaryHead}>
      <div>
        <span className={styles.kicker} dir="ltr">{fileName(catalog.catalog_path)}</span>
        <h2>למדנו את הסגנון שלך מ־{summary.pairs.toLocaleString("he-IL")} תמונות</h2>
      </div>
      <button className={styles.link} type="button" disabled={busy} onClick={onReanalyze}>נתח מחדש</button>
    </div>
    <ul className={styles.checklist}>
      <li className={styles.done}>{summary.photos.toLocaleString("he-IL")} תמונות בקטלוג</li>
      <li className={missing ? styles.partial : styles.done}>
        {summary.linked.toLocaleString("he-IL")} תמונות מקוריות נמצאו{missing ? ` · ל־${missing.toLocaleString("he-IL")} אין Smart Preview` : ""}
      </li>
      <li className={styles.done}>{summary.pairs.toLocaleString("he-IL")} עריכות שלך נקראו</li>
    </ul>

    {savings.untouched_pct !== undefined && savings.proposed_photos !== undefined && <div className={styles.savings}>
      <strong>{Math.round(savings.untouched_pct)}%</strong>
      <p>אם תערוך {savings.anchors} תמונות, ProGrapher תציע עריכה ל־{savings.proposed_photos.toLocaleString("he-IL")} האחרות,
        ובערך {Math.round(savings.untouched_pct)}% מהן לא תצטרך לגעת.
        {savings.no_correction_untouched_pct !== undefined &&
          <> לשם השוואה, בלי שום הצעה רק {Math.round(savings.no_correction_untouched_pct)}% מהתמונות לא דורשות שינוי.</>}</p>
      {savings.curve && savings.curve.length > 1 && <small>
        {savings.curve.map((c) => `${c.anchors} תמונות ערוכות: ${Math.round(c.untouched_pct)}%`).join(" · ")}
      </small>}
    </div>}

    <div className={styles.style}>
      <h3>הסגנון שלך</h3>
      <StyleLine title="קבוע בכל תמונה" sliders={fixed}/>
      <StyleLine title="אתה מתאים מתמונה לתמונה" sliders={perPhoto} range/>
      {untouched.length > 0 && <p className={styles.muted}>לא נוגע: {untouched.map((s) => sliderName[s.key] ?? s.key).join(", ")}</p>}
      {rare.length > 0 && <p className={styles.muted}>לפעמים: {rare.map((s) =>
        `${sliderName[s.key] ?? s.key} (${s.present === 1 ? "בתמונה אחת" : `ב־${s.present.toLocaleString("he-IL")} תמונות`})`).join(", ")}</p>}
    </div>

    {samples.length > 0 && <div className={styles.samples}>
      {samples.map((sample, index) => <figure key={index}>
        {sample.thumbnail_jpeg_base64 && <img src={`data:image/jpeg;base64,${sample.thumbnail_jpeg_base64}`}
          width={sample.width ?? undefined} height={sample.height ?? undefined} alt={`לפני עריכה: ${sample.file_name}`}
          draggable={false}/>}
        <figcaption>
          <span dir="ltr">{sample.file_name}</span>
          <span>שלך: <Value k="Exposure2012" v={sample.photographer.exposure}/> · <Value k="Temperature" v={sample.photographer.temperature_k}/></span>
          <span>מוצע: <Value k="Exposure2012" v={sample.proposed.exposure}/> · <Value k="Temperature" v={sample.proposed.temperature_k}/>
            {sample.untouched ? " ✓" : ""}</span>
        </figcaption>
      </figure>)}
    </div>}
  </section>;
}

export default function LearningIntakeScreen() {
  const openView = useWorkspaceNav();
  const [profiles, setProfiles] = useState<LearningProfile[]>([]);
  const [profile, setProfile] = useState<LearningProfile | null>(null);
  const [name, setName] = useState("");
  const [photographyType, setPhotographyType] = useState("חתונה");
  const [colorMode, setColorMode] = useState<ColorMode>("color");
  const [consent, setConsent] = useState(false);
  const [found, setFound] = useState<CatalogDiscoveryCandidate[]>([]);
  const [picked, setPicked] = useState<CatalogDiscoveryCandidate | null>(null);
  const [adding, setAdding] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [samples, setSamples] = useState<Record<string, AnalysisSample[]>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletePending, setDeletePending] = useState<LearningProfile | null>(null);
  const working = busy || phase !== "idle";

  useEffect(() => {
    let alive = true;
    void listLearningProfiles()
      .then((all) => { if (alive) setProfiles(all); })
      .catch((cause) => { if (alive) setError(cause instanceof Error ? cause.message : "לא ניתן לטעון פרופילים."); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  function show(next: LearningProfile) {
    setProfile(next);
    setProfiles((old) => old.some((p) => p.profile_id === next.profile_id)
      ? old.map((p) => p.profile_id === next.profile_id ? next : p) : [next, ...old]);
  }

  function resetCatalogChoice() {
    setFound([]);
    setPicked(null);
  }

  async function create() {
    if (!name.trim() || !photographyType.trim() || !consent || working) return;
    setError("");
    setBusy(true);
    try {
      show(await createLearningProfile({
        name: name.trim(), photography_type: photographyType.trim(), color_mode: colorMode, consent,
      }));
      setAdding(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "יצירת הפרופיל נכשלה.");
    } finally { setBusy(false); }
  }

  async function chooseFolder() {
    if (working) return;
    const selected = await open({ directory: true, multiple: false, title: "בחר את התיקייה של קטלוג Lightroom" });
    if (!selected || Array.isArray(selected)) return;
    setError("");
    resetCatalogChoice();
    setBusy(true);
    try {
      const result = await discoverCatalogLocation(selected);
      setFound(result.catalogs);
      if (result.catalogs.length === 1) setPicked(result.catalogs[0]);
      if (!result.catalogs.length) setError("לא נמצא קטלוג Lightroom (.lrcat) בתיקייה הזו.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לסרוק את התיקייה.");
    } finally { setBusy(false); }
  }

  async function choosePreviews() {
    if (working || !picked) return;
    const selected = await open({ directory: true, multiple: false, title: "בחר את תיקיית Smart Previews.lrdata" });
    if (!selected || Array.isArray(selected)) return;
    setPicked({ ...picked, smart_previews_path: selected });
  }

  async function analyze(target: LearningProfile, catalogPath: string) {
    setPhase("analyzing");
    const result = await analyzeCatalog(target.profile_id, catalogPath);
    setSamples((old) => ({ ...old, [catalogPath]: result.samples }));
    show(result.profile);
  }

  async function addCatalog() {
    if (!profile || !picked || working) return;
    setError("");
    setPhase("reading");
    try {
      const next = await attachLearningCatalog(profile.profile_id, {
        catalog_path: picked.catalog_path,
        smart_previews_path: picked.smart_previews_path,
        raw_fallback_path: null,
      });
      show(next);
      if (picked.smart_previews_path) await analyze(next, picked.catalog_path);
      setAdding(false);
      resetCatalogChoice();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "קריאת הקטלוג נכשלה.");
    } finally { setPhase("idle"); }
  }

  async function reanalyze(catalog: CatalogIntake) {
    if (!profile || working) return;
    setError("");
    try {
      await analyze(profile, catalog.catalog_path);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הניתוח נכשל.");
    } finally { setPhase("idle"); }
  }

  function selectProfile(item: LearningProfile) {
    setProfile(item);
    setAdding(item.catalogs.length === 0);
    resetCatalogChoice();
    setError("");
  }

  async function confirmDelete() {
    if (!deletePending || working) return;
    const toDelete = deletePending;
    setBusy(true);
    setError("");
    try {
      await deleteLearningProfile(toDelete.profile_id);
      setProfiles((old) => old.filter((item) => item.profile_id !== toDelete.profile_id));
      if (profile?.profile_id === toDelete.profile_id) setProfile(null);
      setDeletePending(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן למחוק את הפרופיל.");
      setDeletePending(null);
    } finally { setBusy(false); }
  }

  const progress = phase !== "idle" && <ul className={styles.checklist} aria-live="polite">
    <li className={phase === "reading" ? styles.running : styles.done}>קורא את הקטלוג</li>
    <li className={phase === "analyzing" ? styles.running : styles.waiting}>
      מוצא את התמונות המקוריות, קורא את העריכות שלך ומחשב כמה זמן אפשר לחסוך
    </li>
    {phase === "analyzing" && <li className={styles.hint}>בקטלוג גדול זה לוקח דקה־שתיים.</li>}
  </ul>;

  return <main className={styles.screen} dir="rtl">
    <header className={styles.header}>
      <button className={styles.back} type="button" onClick={() => openView("profile")}>חזרה לפרופיל ←</button>
      <h1>פרופיל הלמידה</h1>
      <p>ProGrapher לומדת את הסגנון שלך מהעריכות שכבר עשית ב־Lightroom. הכול נשאר במחשב שלך, ושום דבר לא משתנה בקטלוג.</p>
    </header>
    {error && <div role="alert" className={styles.error}>{error}</div>}
    {deletePending && <div className={styles.modalBackdrop} role="presentation">
      <section className={styles.modal} role="alertdialog" aria-modal="true" aria-labelledby="delete-heading">
        <h2 id="delete-heading">למחוק את הפרופיל ״{deletePending.name}״?</h2>
        <p>הפרופיל יימחק מ־ProGrapher בלבד. הקטלוג, קובצי ה־RAW וה־Smart Previews לא משתנים.</p>
        <div className={styles.modalActions}>
          <button className={styles.ghost} type="button" disabled={busy} onClick={() => setDeletePending(null)}>ביטול</button>
          <button className={styles.danger} type="button" disabled={busy} onClick={() => void confirmDelete()}>{busy ? "מוחק…" : "מחק פרופיל"}</button>
        </div>
      </section>
    </div>}

    {!profile ? <div className={styles.layout}>
      <section className={styles.panel}>
        <h2>פרופיל חדש</h2>
        <label>שם הפרופיל
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="לדוגמה: סגנון חתונות"/>
        </label>
        <label>סוג צילום
          <input value={photographyType} maxLength={80} onChange={(e) => setPhotographyType(e.target.value)}/>
        </label>
        <label>סגנון צבע
          <select value={colorMode} onChange={(e) => setColorMode(e.target.value as ColorMode)}>
            <option value="color">צבע</option>
            <option value="black_white">שחור־לבן</option>
          </select>
        </label>
        <label className={styles.consent}><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}/>
          <span>יש לי אישור להשתמש בקטלוגים ובתמונות לצורך למידת הפרופיל במחשב זה.</span>
        </label>
        <button className={styles.primary} type="button" disabled={!name.trim() || !photographyType.trim() || !consent || working}
          onClick={() => void create()}>{busy ? "שומר…" : "צור פרופיל והמשך"}</button>
      </section>
      <section className={styles.panel}>
        <h2>פרופילים קיימים</h2>
        {loading ? <p>טוען…</p> : profiles.length === 0 ? <p>עדיין אין פרופילים.</p> : profiles.map((item) =>
          <div key={item.profile_id} className={styles.profileEntry}>
            <button className={styles.existing} onClick={() => selectProfile(item)} type="button" disabled={working}>
              <strong>{item.name}</strong>
              <span>{item.photography_type} · {item.catalogs.length === 1 ? "קטלוג אחד" : `${item.catalogs.length} קטלוגים`}</span>
            </button>
            <button className={styles.deleteLink} type="button" disabled={working} onClick={() => setDeletePending(item)}>מחק</button>
          </div>)}
      </section>
    </div> : <>
      <div className={styles.profileBar}>
        <h2>{profile.name}</h2>
        <div className={styles.profileActions}>
          {!adding && <button className={styles.link} type="button" disabled={working} onClick={() => setAdding(true)}>הוסף קטלוג</button>}
          <button className={styles.link} type="button" disabled={working} onClick={() => { setProfile(null); setError(""); }}>החלף פרופיל</button>
          <button className={styles.deleteLink} type="button" disabled={working} onClick={() => setDeletePending(profile)}>מחק פרופיל</button>
        </div>
      </div>

      {adding && <section className={styles.panel}>
        <h2>{profile.catalogs.length ? "קטלוג נוסף" : "הוספת קטלוג"}</h2>
        <p>בחר את התיקייה שבה נמצא קטלוג ה־Lightroom שלך. ProGrapher תמצא לבד את הקטלוג ואת ה־Smart Previews.</p>
        {phase === "idle" && <button className={styles.source} disabled={working} type="button" onClick={() => void chooseFolder()}>
          <strong>{busy ? "מחפש קטלוג…" : picked ? "בחר תיקייה אחרת" : "בחר תיקיית קטלוג"}</strong>
        </button>}
        {found.length > 1 && phase === "idle" && <label className={styles.catalogChooser}>נמצאו כמה קטלוגים, באיזה להשתמש?
          <select value={picked?.catalog_path ?? ""} onChange={(event) =>
            setPicked(found.find((item) => item.catalog_path === event.target.value) ?? null)}>
            <option value="">בחר קטלוג</option>
            {found.map((item) => <option key={item.catalog_path} value={item.catalog_path}>{fileName(item.catalog_path)}</option>)}
          </select>
        </label>}
        {picked && <ul className={styles.checklist}>
          <li className={styles.done}><span>קטלוג: </span><bdi dir="ltr">{fileName(picked.catalog_path)}</bdi></li>
          <li className={picked.smart_previews_path ? styles.done : styles.partial}>
            {picked.smart_previews_path ? "Smart Previews נמצאו" : "לא נמצאו Smart Previews ליד הקטלוג"}
            {!picked.smart_previews_path && phase === "idle" &&
              <button className={styles.link} type="button" onClick={() => void choosePreviews()}>בחר אותם ידנית</button>}
          </li>
        </ul>}
        {progress}
        {picked && phase === "idle" && <button className={styles.primary} type="button" disabled={working}
          onClick={() => void addCatalog()}>הוסף ונתח</button>}
        {profile.catalogs.length > 0 && phase === "idle" &&
          <button className={styles.link} type="button" onClick={() => { setAdding(false); resetCatalogChoice(); }}>ביטול</button>}
      </section>}

      {!adding && phase !== "idle" && <section className={styles.panel}>{progress}</section>}

      {profile.catalogs.map((catalog) => catalog.analysis
        ? <CatalogSummary key={catalog.catalog_path} catalog={catalog} summary={catalog.analysis}
            samples={samples[catalog.catalog_path] ?? []} busy={working} onReanalyze={() => void reanalyze(catalog)}/>
        : <section key={catalog.catalog_path} className={styles.panel}>
            <span className={styles.kicker} dir="ltr">{fileName(catalog.catalog_path)}</span>
            <p>{catalog.smart_previews_path
              ? "הקטלוג נוסף אבל עוד לא נותח."
              : "לא נמצאו Smart Previews לקטלוג הזה. ב־Lightroom: Library ← Previews ← Build Smart Previews, ואז הוסף את הקטלוג שוב."}</p>
            {catalog.smart_previews_path && <button className={styles.primary} type="button" disabled={working}
              onClick={() => void reanalyze(catalog)}>נתח עכשיו</button>}
          </section>)}
    </>}
  </main>;
}
