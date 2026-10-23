"use client";

import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  runSamplePreflight,
  probeSmartPreviewContents,
  linkSmartPreviews,
  buildEditPairs,
  reviewSmartPreviewSdkLinks,
  type SmartPreviewContentReport,
  type SmartPreviewLinkReport,
  type EditPairsReport,
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

const linkStatusLabel: Record<string, string> = {
  linked_name_verified: "קושרו ואומתו לפי שם הקובץ",
  linked_name_mismatch: "קושרו, אך שם הקובץ בתוך ה־DNG שונה מהקטלוג",
  linked_name_unreadable: "קושרו, אך לא נמצא שם קובץ בתוך ה־DNG",
  no_smart_preview: "אין Smart Preview",
  ambiguous_smart_preview: "יותר מ־DNG אחד באותו מזהה",
};

const targetLabel: Record<string, string> = {
  Exposure2012: "חשיפה", Contrast2012: "ניגודיות", Highlights2012: "הבהרות", Shadows2012: "צללים",
  Whites2012: "לבנים", Blacks2012: "שחורים", Texture: "טקסטורה", Clarity2012: "בהירות (Clarity)",
  Dehaze: "Dehaze", Vibrance: "חיוניות", Saturation: "רוויה", Temperature: "טמפרטורה (K)", Tint: "גוון (Tint)",
};

const exclusionLabel: Record<string, string> = {
  link_not_verified: "שיוך ל־Smart Preview לא אומת",
  virtual_copy_shares_master_preview: "עותק וירטואלי (חולק תמונת לפני עם המקור)",
  rejected_in_lightroom: "מסומנת Reject ב־Lightroom",
  no_global_develop_values: "אין ערכי עריכה גלובליים",
  missing_develop: "אין רשומת Develop",
  develop_parse_failed: "רשומת Develop לא פוענחה",
  ambiguous_develop_rows: "כמה רשומות Develop לאותה תמונה",
  missing_source_catalog_link: "חסר קישור לקובץ בקטלוג",
  unsupported_raw_extension: "סוג RAW לא נתמך",
};

const otherEditLabel: Record<string, string> = {
  tone_curve: "עקומת טון", color_adjustments: "HSL / Color Grading", local_or_opaque_edits: "מסכות / תיקונים מקומיים",
  black_and_white: "שחור־לבן",
};

function formatValue(key: string, value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  if (key === "Exposure2012") return value.toFixed(2);
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

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
  const [linkReport, setLinkReport] = useState<SmartPreviewLinkReport | null>(null);
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkError, setLinkError] = useState("");
  const [pairsReport, setPairsReport] = useState<EditPairsReport | null>(null);
  const [pairsBusy, setPairsBusy] = useState(false);
  const [pairsError, setPairsError] = useState("");
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

  async function linkSmartPreviewsToCatalog() {
    if (!catalogPath || linkBusy || busy) return;
    setLinkBusy(true);
    setLinkError("");
    setLinkReport(null);
    try {
      setLinkReport(await linkSmartPreviews(profile.profile_id, catalogPath));
    } catch (cause) {
      setLinkError(cause instanceof Error ? cause.message : "קישור Smart Previews לקטלוג נכשל.");
    } finally {
      setLinkBusy(false);
    }
  }

  async function buildBeforeAfterPairs() {
    if (!catalogPath || pairsBusy || busy) return;
    setPairsBusy(true);
    setPairsError("");
    setPairsReport(null);
    try {
      setPairsReport(await buildEditPairs(profile.profile_id, catalogPath));
    } catch (cause) {
      setPairsError(cause instanceof Error ? cause.message : "בניית זוגות לפני/אחרי נכשלה.");
    } finally {
      setPairsBusy(false);
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
    if (!catalogPath || busy || previewBusy) return;
    setBusy(true);
    setError("");
    setPreviewError("");
    setReport(null);
    setPreviewReport(null);
    try {
      const result = await runSamplePreflight(profile.profile_id, {
        catalog_path: catalogPath,
        raw_folder: rawFolder.trim() || null,
        sample_size: 16,
      });
      setReport(result);
      // The normal flow automatically checks actual DNG contents when the
      // profile has a Smart Preview source. Decoder failures are visible but
      // must NOT turn a valid catalog metadata sample into an error.
      if (smartPreviewsPath) {
        try {
          setPreviewReport(await probeSmartPreviewContents(profile.profile_id, catalogPath));
        } catch (cause) {
          setPreviewError(cause instanceof Error ? cause.message : "בדיקת Smart Previews נכשלה.");
        }
      }
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
            setLinkReport(null);
            setLinkError("");
            setPairsReport(null);
            setPairsError("");
            setRawFolder("");
          }}>
          {profile.catalogs.map((item) => <option key={item.catalog_path} value={item.catalog_path}>{item.catalog_path}</option>)}
        </select>
      </label>
      <button className={styles.run} type="button" disabled={!catalogPath || busy} onClick={() => void run()}>
        {busy ? "קורא עותק קטלוג ובודק מדגם…" : rawFolder ? "בדוק מדגם + מועמדי RAW (מחקר)" : "בדוק מדגם + Smart Previews אוטומטית"}
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
      <p className={styles.sourceCaveat}>הנתיב נשמר בזמן קליטת הקטלוג, ואינו בדיקת קיום עדכנית. בדיקת המדגם תנסה לקרוא אוטומטית את קובצי ה־DNG בפועל, אבל פענוח מוצלח עדיין אינו מאמת התאמה לרשומת Lightroom או נקודת התחלה ניטרלית.</p>
      <button className={styles.previewProbe} type="button" onClick={() => void inspectSmartPreviewContents()}
        disabled={!smartPreviewsPath || previewBusy || busy}>
        {previewBusy ? "סורק ומנסה לפענח קובצי DNG…" : "בדוק תוכן Smart Previews"}
      </button>
      {previewError && <p role="alert" className={styles.error}>{previewError}</p>}
      <button className={styles.previewProbe} type="button" onClick={() => void linkSmartPreviewsToCatalog()}
        disabled={!smartPreviewsPath || linkBusy || busy || previewBusy}>
        {linkBusy ? "קורא עותק קטלוג ומקשר קובצי DNG…" : "קשר Smart Previews לתמונות בקטלוג"}
      </button>
      {linkError && <p role="alert" className={styles.error}>{linkError}</p>}
      {linkReport && <div className={styles.previewResults} role="status">
        <span>תמונות RAW בקטלוג: <strong>{linkReport.catalog_raw_records}</strong></span>
        <span>קובצי Smart Preview: <strong>{linkReport.smart_preview_files}</strong></span>
        {Object.entries(linkReport.status_counts).map(([status, count]) =>
          <span key={status}>{linkStatusLabel[status] || status}: <strong>{count}</strong></span>)}
        <span>עותקים וירטואליים: <strong>{linkReport.virtual_copy_records}</strong></span>
        <span>תמונות שחולקות Smart Preview: <strong>{linkReport.records_sharing_a_preview}</strong></span>
        <span>Smart Previews בלי תמונה בקטלוג: <strong>{linkReport.orphan_smart_previews}</strong></span>
        {linkReport.samples.length > 0 && <div className={styles.beforeImages}>
          {linkReport.samples.map((sample, index) => <figure key={index}>
            {sample.reset_render?.thumbnail_jpeg_base64
              ? <img src={`data:image/jpeg;base64,${sample.reset_render.thumbnail_jpeg_base64}`}
                  width={sample.reset_render.width} height={sample.reset_render.height}
                  alt={`תמונת לפני של ${sample.file_name}`} draggable={false}/>
              : <p>לא נוצרה תמונת לפני ({sample.decode_state || "לא פוענח"})</p>}
            <figcaption dir="ltr">{sample.file_name}{sample.capture_day ? ` · ${sample.capture_day}` : ""}</figcaption>
          </figure>)}
        </div>}
        <p>השוו את התמונות לפי שם הקובץ מול Lightroom (במודול Develop, מקש \ מציג את מצב ה&quot;לפני&quot; בלי לשנות דבר). שיוך מאומת = המזהה בקטלוג הוא שם קובץ ה־DNG, ושם קובץ ה־RAW שנשמר בתוכו זהה לקטלוג. העריכות של הצלם לא נקראות כאן; שום דבר לא נשמר ואינו מאושר לאימון.</p>
      </div>}
      <button className={styles.previewProbe} type="button" onClick={() => void buildBeforeAfterPairs()}
        disabled={!smartPreviewsPath || pairsBusy || linkBusy || busy || previewBusy}>
        {pairsBusy ? "בונה זוגות לפני/אחרי…" : "בנה זוגות לפני / אחרי (שלב 4)"}
      </button>
      {pairsError && <p role="alert" className={styles.error}>{pairsError}</p>}
      {pairsReport && <div className={styles.previewResults} role="status">
        <span>תמונות RAW בקטלוג: <strong>{pairsReport.catalog_raw_records}</strong></span>
        <span>זוגות לפני/אחרי לבדיקה: <strong>{pairsReport.pairs_for_review}</strong></span>
        {Object.entries(pairsReport.excluded_counts).map(([reason, count]) =>
          <span key={reason}>הוצאו · {exclusionLabel[reason] || reason}: <strong>{count}</strong></span>)}
        {Object.entries(pairsReport.other_edit_counts).map(([kind, count]) =>
          <span key={kind}>זוגות עם {otherEditLabel[kind] || kind}: <strong>{count}</strong></span>)}
        <table className={styles.pairsTable}>
          <thead><tr><th>ערך</th><th>קיים ב־</th><th>חציון</th><th>10%–90%</th></tr></thead>
          <tbody>{pairsReport.targets.map((key) => {
            const c = pairsReport.target_coverage[key];
            return <tr key={key}><td>{targetLabel[key] || key}</td><td>{c?.present ?? 0}</td>
              <td dir="ltr">{formatValue(key, c?.median)}</td>
              <td dir="ltr">{c?.p10 !== undefined ? `${formatValue(key, c.p10)} … ${formatValue(key, c.p90)}` : "—"}</td></tr>;
          })}</tbody>
        </table>
        <table className={styles.pairsTable}>
          <thead><tr><th>קבוצת תיקייה</th><th>זוגות</th><th>חשיפה (חציון)</th><th>טמפ׳ mired (חציון)</th><th>Tint (חציון)</th></tr></thead>
          <tbody>{pairsReport.folder_groups.map((group) => <tr key={group.folder_group}>
            <td dir="ltr">{group.folder_group}</td><td>{group.pairs}</td>
            <td dir="ltr">{formatValue("Exposure2012", group.exposure_median)}</td>
            <td dir="ltr">{formatValue("mired", group.temperature_mired_median)}</td>
            <td dir="ltr">{formatValue("Tint", group.tint_median)}</td></tr>)}</tbody>
        </table>
        {pairsReport.samples.length > 0 && <div className={styles.beforeImages}>
          {pairsReport.samples.map((sample, index) => <figure key={index}>
            {sample.reset_render?.thumbnail_jpeg_base64
              ? <img src={`data:image/jpeg;base64,${sample.reset_render.thumbnail_jpeg_base64}`}
                  width={sample.reset_render.width} height={sample.reset_render.height}
                  alt={`לפני: ${sample.file_name}`} draggable={false}/>
              : <p>לא נוצרה תמונת לפני ({sample.decode_state || "לא פוענח"})</p>}
            <figcaption><span dir="ltr">{sample.file_name} · {sample.folder_group}</span>
              <span>אחרי (מה שהצלם קבע): {Object.entries(sample.targets).map(([key, value]) =>
                `${targetLabel[key] || key} ${formatValue(key, value)}`).join(" · ")}</span>
            </figcaption>
          </figure>)}
        </div>}
        <p>כל זוג = תמונת ה&quot;לפני&quot; מה־Smart Preview + ערכי העריכה של הצלם מהקטלוג. ערך שחסר בקטלוג מוצג כחסר ולא כאפס. קבוצות התיקיות מסומנות F01, F02… בלי שמות; הבדלים ביניהן מרמזים על צלמים או פריסטים שונים. לא נבדק אם העריכה סופית; שום דבר לא נשמר ואינו מאושר לאימון.</p>
      </div>}
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
        <span>פוענחו בהצלחה ברמת DNG: <strong>{(previewReport.decode_status_counts.jpegxl_dng_decoded_unverified ?? 0) + (previewReport.decode_status_counts.decoded_unverified ?? 0)}</strong></span>
        <span>לא פוענחו / דורשים טיפול: <strong>{previewReport.decode_attempts - (previewReport.decode_status_counts.jpegxl_dng_decoded_unverified ?? 0) - (previewReport.decode_status_counts.decoded_unverified ?? 0)}</strong></span>
        {(previewReport.decode_compression_counts?.["52546"] ?? 0) > 0 && <span>JPEG XL (דחיסה 52546) במדגם: <strong>{previewReport.decode_compression_counts?.["52546"]}</strong></span>}
        {(previewReport.decode_status_counts.jpegxl_decoder_dependency_missing ?? 0) > 0 && <p className={styles.decoderWarning}>חסרות ספריות Python לפענוח JPEG XL. עדכן את סביבת ה־Backend באמצעות requirements-lock.txt; קוד המפענח כבר נמצא ב־Git.</p>}
        {(previewReport.decode_status_counts.jpegxl_decoder_bundle_error ?? 0) > 0 && <p className={styles.decoderWarning}>ארכיון המפענח שנמצא ב־Git אינו נטען או אינו תואם את בדיקת התקינות. בדוק את הקבצים שעודכנו ואת תיקיית המטמון המקומית; אין צורך ב־ZIP חיצוני.</p>}
        {(previewReport.decode_status_counts.jpegxl_codec_unavailable ?? 0) > 0 && <p className={styles.decoderWarning}>ספריית imagecodecs קיימת אך תמיכת JPEG XL אינה זמינה. יש צורך בגרסה הכוללת את ה־codec.</p>}
        {(previewReport.decode_status_counts.jpegxl_dng_decode_error ?? 0) > 0 && <p className={styles.decoderWarning}>מפענח JPEG XL הופעל אך נכשל. נדרשת בדיקה על קובצי המחקר; לא הוכח שקובצי ה־DNG פגומים.</p>}
        {(previewReport.decode_status_counts.jpegxl_dng_unhandled_opcodes ?? 0) > 0 && <p className={styles.decoderWarning}>פוענחו פיקסלים אך נמצאו Opcode שאינם מטופלים. התמונה אינה מועמדת ללמידה.</p>}
        {previewReport.decoded_samples.some((sample) => sample.reset_render?.look_source === "smart_preview_profile") && <p className={styles.decoderWarning}>הקובץ Adobe Color.xmp של Lightroom לא נמצא במחשב, ולכן תמונות ה&quot;לפני&quot; רונדרו עם טבלת המראה שבתוך ה־Smart Preview (קרוב מאוד, אך לא ההגדרה שנבדקה). אפשר להעתיק את הקובץ לתיקייה adobe_profiles בתוך תיקיית הנתונים של ProGrapher.</p>}
        {(previewReport.reset_render_counts?.reset_render_error ?? 0) > 0 && <p className={styles.decoderWarning}>הפענוח הצליח אך הרינדור לתמונת &quot;לפני&quot; נכשל באחד הקבצים.</p>}
        {previewReport.decoded_samples.some((sample) => sample.reset_render?.thumbnail_jpeg_base64) && <div className={styles.beforeImages}>
          {previewReport.decoded_samples.map((sample, index) => sample.reset_render?.thumbnail_jpeg_base64 &&
            <figure key={index}>
              <img src={`data:image/jpeg;base64,${sample.reset_render.thumbnail_jpeg_base64}`}
                width={sample.reset_render.width} height={sample.reset_render.height}
                alt={`תמונת לפני ${index + 1} מתוך המדגם`} draggable={false}/>
              <figcaption>לפני עריכה · Reset (Adobe Color, As Shot){sample.reset_render.lens_vignetting === "applied" ? " · כולל תיקון וינייט של העדשה" : " · בלי תיקון עדשה"}</figcaption>
            </figure>)}
        </div>}
        <p>תמונות ה&quot;לפני&quot; מרונדרות מה־Smart Preview הלא ערוך כמו Lightroom אחרי Reset, עם תיקון וינייט כשקיים פרופיל עדשה של Adobe. ההתאמה ל־Lightroom נמדדה במחקר ולא על הקטלוג הזה; התמונות מוצגות מהזיכרון בלבד, לא נשמרות, ואינן מאושרות לאימון.</p>
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
      <p className={styles.notice}>זהו מדגם מטא־דאטה של רשומות קטלוג; גם אם בדיקת ה־DNG נפרדת הצליחה, הפיקסלים שלה עדיין לא קושרו למדגם. {rawFolder ? "גם מועמד RAW לפי שם ו־SHA-256 אינו מוכיח זהות מול Lightroom." : "לא נדרשה בחירת RAW."} עריכה סופית ונקודת Import/Reset טרם אומתו.</p>
      <div className={styles.rows}>
        {report.records.length > 0 ? report.records.map((item, index) =>
          <SampleRow key={`${item.catalog_image_id}-${index}`} sample={item}/>) :
          <p>אין רשומות RAW שניתן להציג בקטלוג זה.</p>}
      </div>
      <p className={styles.private}>כל פרטי המדגם מוצגים מתוך המנוע המקומי בלבד ולא נשמרים בדוח הציבורי או נשלחים ל־GitHub.</p>
    </div>}
  </section>;
}
