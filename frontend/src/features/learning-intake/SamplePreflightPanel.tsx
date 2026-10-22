"use client";

import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  runSamplePreflight,
  type LearningProfile,
  type PreflightSampleReport,
  type SourceSample,
} from "./learningIntake.api";
import styles from "./SamplePreflightPanel.module.css";

const statusLabel: Record<string, string> = {
  raw_folder_not_selected: "נבדקה רשומת הקטלוג בלבד · מקור חזותי טרם אומת",
  no_filename_candidate: "לא נמצא מועמד בשם תואם",
  missing_catalog_filename: "חסר שם קובץ בקטלוג",
  ambiguous_filename: "יותר מקובץ RAW מועמד אחד",
  unique_filename_candidate: "מועמד יחיד לפי שם · זהות לא אומתה",
  source_changed_during_read: "הקובץ השתנה בזמן הקריאה",
  source_unreadable: "אין הרשאת קריאה לקובץ",
  file_too_large_to_hash: "הקובץ גדול מדי לבדיקה הזו",
};

function SampleRow({ sample }: { sample: SourceSample }) {
  return <div className={styles.sampleRow}>
    <div className={styles.sampleTitle}>
      <strong dir="ltr" title={sample.filename}>{sample.filename}</strong>
      <span>{sample.candidate_group} · {sample.capture_day || "תאריך לא ידוע"}</span>
    </div>
    <div className={styles.status}>{statusLabel[sample.source_match_status] || sample.source_match_status}</div>
    <div className={styles.details}>
      <span>{sample.develop_parse_ok ? `${sample.develop_fields.length} שדות Develop מפוענחים` : "Develop לא מפוענח"}</span>
      {sample.virtual_copy_candidate && <span>Virtual Copy — דורש בחירה</span>}
      {sample.issues.length > 0 && <span title={sample.issues.join(", ")}>חריגות: {sample.issues.length}</span>}
      {sample.source_sha256 && <span dir="ltr" title={sample.source_sha256}>SHA-256: {sample.source_sha256.slice(0, 12)}…</span>}
      {sample.source_candidate_path && <span className={styles.path} title={sample.source_candidate_path} dir="ltr">{sample.source_candidate_path}</span>}
    </div>
  </div>;
}

export default function SamplePreflightPanel({ profile }: { profile: LearningProfile }) {
  const [catalogPath, setCatalogPath] = useState(profile.catalogs[0]?.catalog_path ?? "");
  const [rawFolder, setRawFolder] = useState("");
  const [report, setReport] = useState<PreflightSampleReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedCatalog = profile.catalogs.find((item) => item.catalog_path === catalogPath);
  const smartPreviewsPath = selectedCatalog?.smart_previews_path ?? null;

  async function chooseRaw() {
    if (busy) return;
    const selected = await open({
      directory: true, multiple: false,
      title: "בחר תיקיית RAW מקורית למדגם — לא תבוצע עריכה",
    });
    if (typeof selected !== "string") return;
    setRawFolder(selected);
    setReport(null);
  }

  async function run() {
    if (!catalogPath || busy) return;
    setBusy(true);
    setError("");
    setReport(null);
    try {
      const result = await runSamplePreflight(profile.profile_id, {
        catalog_path: catalogPath,
        raw_folder: rawFolder.trim() || null,
        sample_size: 16,
      });
      setReport(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לבצע בדיקת מדגם.");
    } finally {
      setBusy(false);
    }
  }

  return <section className={styles.panel} dir="rtl">
    <div className={styles.heading}>
      <div>
        <span className={styles.kicker}>PG-LI-02A · DATA-01 / LOCAL PREFLIGHT</span>
        <h2>אימות מדגם תמונות</h2>
        <p>בחר קטלוג מתוך הפרופיל. ProGrapher מציגה אוטומטית את מצב Smart Previews שנמצאו במהלך קליטתו ומפיקה מדגם של עד 16 רשומות. בשלב זה מדובר בבדיקת נתוני Lightroom בלבד — פענוח התמונות ואימות הקשר אליהן טרם הושלמו.</p>
      </div>
      <span className={styles.notReady}>אימון חסום עד אימות</span>
    </div>
    <div className={styles.selectors}>
      <label>קטלוג לבדיקה
        <select value={catalogPath} disabled={busy}
          onChange={(event) => { setCatalogPath(event.target.value); setReport(null); setRawFolder(""); }}>
          {profile.catalogs.map((item) => <option key={item.catalog_path} value={item.catalog_path}>{item.catalog_path}</option>)}
        </select>
      </label>
      <button className={styles.run} type="button" disabled={!catalogPath || busy} onClick={() => void run()}>
        {busy ? "קורא עותק קטלוג ובודק מדגם…" : "בדוק מדגם של 16 רשומות"}
      </button>
    </div>
    <div className={styles.automaticSource} aria-live="polite">
      <div className={styles.sourceTopline}>
        <strong>Smart Previews · איתור אוטומטי</strong>
        <span className={smartPreviewsPath ? styles.detected : styles.notDetected}>
          {smartPreviewsPath ? "התיקייה אותרה" : "לא אותרה תיקייה"}
        </span>
      </div>
      {smartPreviewsPath ? (
        <p dir="ltr" title={smartPreviewsPath} className={styles.sourcePath}>{smartPreviewsPath}</p>
      ) : (
        <p>לא שמורה בפרופיל תיקיית Smart Previews לקטלוג הזה. אפשר לבדוק מחדש את קליטת הקטלוג לאיתור תיקייה סמוכה.</p>
      )}
      <p className={styles.sourceCaveat}>איתור תיקייה בלבד: עדיין לא פענחנו את תמונות Smart Previews, לא קישרנו אותן למזהי Lightroom ולא השתמשנו בפיקסלים שלהן במדגם.</p>
    </div>
    <details className={styles.advanced}>
      <summary>אפשרויות מתקדמות · בדיקת מועמד RAW ידנית</summary>
      <p>למחקר בלבד, כשצריך לבדוק קובץ מקור בנפרד: אפשר לבחור תיקיית RAW לחיפוש לפי שם ולחישוב SHA-256. פעולה זו אינה נדרשת לבדיקה הראשית ולא מוכיחה התאמת תמונה ל־Lightroom.</p>
      <div className={styles.sourceControl}>
        <button type="button" disabled={busy} onClick={() => void chooseRaw()}>{rawFolder ? "החלף תיקיית RAW" : "בחר תיקיית RAW למחקר"}</button>
        {rawFolder && <button className={styles.clear} type="button" disabled={busy} onClick={() => { setRawFolder(""); setReport(null); }}>נקה בחירה</button>}
        <small dir="ltr" title={rawFolder}>{rawFolder || "לא נבחר RAW — מדגם הקטלוג אינו דורש אותו"}</small>
      </div>
    </details>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {report && <div className={styles.results}>
      <div className={styles.stats}>
        <div><small>רשומות במדגם</small><strong>{report.sample_count}</strong></div>
        <div><small>קבוצות מועמדות</small><strong>{report.group_count_in_sample}</strong></div>
        <div><small>זהות מאומתת</small><strong>{report.source_identity_verified_count}</strong></div>
        <div><small>מוכנות לאימון</small><strong>{report.training_ready_samples}</strong></div>
      </div>
      <p className={styles.notice}>זהו מדגם של רשומות קטלוג. Smart Previews טרם פוענחו. {rawFolder ? "גם מועמד RAW לפי שם ו־SHA-256 אינו מוכיח זהות מול Lightroom." : "לא נדרשה בחירת RAW."} עריכה סופית ונקודת Import/Reset טרם אומתו.</p>
      <div className={styles.rows}>
        {report.records.length > 0 ? report.records.map((item, index) =>
          <SampleRow key={`${item.catalog_image_id}-${index}`} sample={item}/>) :
          <p>אין רשומות RAW שניתן להציג בקטלוג זה.</p>}
      </div>
      <p className={styles.private}>כל פרטי המדגם מוצגים מתוך המנוע המקומי בלבד ולא נשמרים בדוח הציבורי או נשלחים ל־GitHub.</p>
    </div>}
  </section>;
}
