"use client";

import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  runSamplePreflight,
  probeSmartPreviewContents,
  reviewSmartPreviewSdkLinks,
  type SmartPreviewContentReport,
  type SmartPreviewSdkLinkReview,
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
  const [previewReport, setPreviewReport] = useState<SmartPreviewContentReport | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [sdkReport, setSdkReport] = useState<SmartPreviewSdkLinkReview | null>(null);
  const [sdkBusy, setSdkBusy] = useState(false);
  const [sdkError, setSdkError] = useState("");
  const selectedCatalog = profile.catalogs.find((item) => item.catalog_path === catalogPath);
  const smartPreviewsPath = selectedCatalog?.smart_previews_path ?? null;

  async function inspectSmartPreviewContents() {
    if (!catalogPath || previewBusy || busy) return;
    setPreviewBusy(true);
    setPreviewError("");
    setPreviewReport(null);
    try {
      const result = await probeSmartPreviewContents(profile.profile_id, catalogPath);
      setPreviewReport(result);
    } catch (cause) {
      setPreviewError(cause instanceof Error ? cause.message : "בדיקת Smart Previews נכשלה.");
    } finally {
      setPreviewBusy(false);
    }
  }

  async function chooseAndReviewSdkEvidence() {
    if (!catalogPath || sdkBusy || busy || previewBusy) return;
    const selected = await open({
      directory: false,
      multiple: false,
      title: "בחר קובץ JSON שנוצר ב־Lightroom SDK (מחקר בלבד)",
      filters: [{ name: "JSON Evidence", extensions: ["json"] }],
    });
    if (typeof selected !== "string") return;
    setSdkBusy(true);
    setSdkError("");
    setSdkReport(null);
    try {
      setSdkReport(await reviewSmartPreviewSdkLinks(profile.profile_id, catalogPath, selected));
    } catch (cause) {
      setSdkError(cause instanceof Error ? cause.message : "בדיקת שיוך SDK נכשלה.");
    } finally {
      setSdkBusy(false);
    }
  }

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
          onChange={(event) => {
            setCatalogPath(event.target.value);
            setReport(null);
            setPreviewReport(null);
            setPreviewError("");
            setSdkReport(null);
            setSdkError("");
            setRawFolder("");
          }}>
          {profile.catalogs.map((item) => <option key={item.catalog_path} value={item.catalog_path}>{item.catalog_path}</option>)}
        </select>
      </label>
      <button className={styles.run} type="button" disabled={!catalogPath || busy} onClick={() => void run()}>
        {busy ? "קורא עותק קטלוג ובודק מדגם…" : rawFolder ? "בדוק מדגם + מועמדי RAW (מחקר)" : "בדוק מדגם של 16 רשומות"}
      </button>
    </div>
    <div className={styles.automaticSource} aria-live="polite">
      <div className={styles.sourceTopline}>
        <strong>Smart Previews · מצב המקור בפרופיל</strong>
        <span className={smartPreviewsPath ? styles.detected : styles.notDetected}>
          {smartPreviewsPath ? "תיקייה שמורה בפרופיל" : "לא אותרה תיקייה"}
        </span>
      </div>
      {smartPreviewsPath ? (
        <p dir="ltr" title={smartPreviewsPath} className={styles.sourcePath}>{smartPreviewsPath}</p>
      ) : (
        <p>לא שמורה בפרופיל תיקיית Smart Previews לקטלוג הזה. אפשר לבדוק מחדש את קליטת הקטלוג לאיתור תיקייה סמוכה.</p>
      )}
      <p className={styles.sourceCaveat}>הנתיב נשמר בזמן קליטת הקטלוג, ואינו בדיקת קיום עדכנית. אפשר לבדוק את קובצי ה־DNG בפועל, אבל פענוח מוצלח עדיין אינו מאמת התאמה לרשומת Lightroom או נקודת התחלה ניטרלית.</p>
      <button className={styles.previewProbe} type="button" onClick={() => void inspectSmartPreviewContents()}
        disabled={!smartPreviewsPath || previewBusy || busy}>
        {previewBusy ? "סורק ומנסה לפענח קובצי DNG…" : "בדוק תוכן Smart Previews"}
      </button>
      {previewError && <p role="alert" className={styles.error}>{previewError}</p>}
      <details className={styles.advanced}>
        <summary>אימות שיוך תמונות באמצעות Lightroom SDK · מחקר מתקדם</summary>
        <p>ב־Lightroom Classic בחר עד 16 תמונות מקטלוג המחקר והפעל Library → Plug-in Extras → ProGrapher Smart Preview Link Readback. שמור את קובץ ה־JSON מחוץ לתיקיות Lightroom, ואז בחר אותו כאן. אין שינוי בקטלוג או בעריכות.</p>
        <button className={styles.previewProbe} type="button"
          disabled={sdkBusy || busy || previewBusy || !smartPreviewsPath}
          onClick={() => void chooseAndReviewSdkEvidence()}>
          {sdkBusy ? "מאמת נתיבי SDK…" : "בחר דוח שיוך SDK מקומי"}
        </button>
        {sdkError && <p className={styles.error} role="alert">{sdkError}</p>}
        {sdkReport && <div className={styles.previewResults} role="status">
          <span>תמונות שנבחרו ב־Lightroom: <strong>{sdkReport.selected_count}</strong></span>
          <span>נתיבי DNG עם UUID תואם בקטלוג: <strong>{sdkReport.sdk_path_catalog_uuid_correlated}</strong></span>
          <span>קישורים שחולקים Preview: <strong>{sdkReport.shared_preview_extra_links}</strong></span>
          <span>מאומתות ללמידה: <strong>{sdkReport.training_ready_samples}</strong></span>
          <p>אלו קישורים שנבדקו מול דוח SDK מקומי, לא אישור זהות RAW, עריכה סופית או נקודת Import/Reset. המידע אינו נשמר בפרופיל.</p>
        </div>}
      </details>
      {previewReport && <div className={styles.previewResults} role="status">
        <span>קובצי DNG בעלי חתימת TIFF: <strong>{previewReport.counts.dng_tiff_signature_candidates ?? 0}</strong></span>
        <span>ניסיונות פענוח: <strong>{previewReport.decode_attempts}</strong></span>
        <span>פוענחו באמצעות LibRaw: <strong>{previewReport.decode_status_counts.decoded_unverified ?? 0}</strong></span>
        <span>קובצי DNG שלא פוענחו או אינם נתמכים: <strong>{(previewReport.decode_status_counts.unsupported_or_corrupt_dng ?? 0) + (previewReport.decode_status_counts.decoder_unavailable ?? 0)}</strong></span>
        <p>הבדיקה מפענחת לכל היותר ארבעה קובצי DNG ומחשבת מדד בהירות זמני. היא אינה מציגה תמונות ערוכות, אינה משווה אותן ל־Lightroom ואינה מוסיפה אף דוגמה לאימון.</p>
      </div>}
    </div>
    <details className={styles.advanced}>
      <summary>{rawFolder ? "אפשרויות מתקדמות · בדיקת RAW ידנית פעילה" : "אפשרויות מתקדמות · בדיקת מועמד RAW ידנית"}</summary>
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
