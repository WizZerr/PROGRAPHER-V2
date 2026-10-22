"use client";

import { useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  createTestingProfile,
  getReviewSheet,
  type ReviewSheet,
  type TestingProfile,
} from "@/features/testing/testing.api";
import { getEventScanProgress, startEventScan } from "@/features/events/events.api";
import styles from "./BrainStudioScreen.module.css";

function normalized(path: string): string {
  return path.trim().replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
}

function separateFolders(left: string, right: string): boolean {
  const a = normalized(left);
  const b = normalized(right);
  return Boolean(a && b && a !== b && !a.startsWith(b + "/") && !b.startsWith(a + "/"));
}

function fmt(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
}

export default function BrainStudioScreen() {
  const [trainRoot, setTrainRoot] = useState("");
  const [editsRoot, setEditsRoot] = useState("");
  const [testRoot, setTestRoot] = useState("");
  const [profile, setProfile] = useState<TestingProfile | null>(null);
  const [report, setReport] = useState<ReviewSheet | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");

  const ready = Boolean(profile?.baseline && profile.usable_pairs > 0);
  const scores = useMemo(() => {
    if (!report) return null;
    const rows = report.files.filter(
      (row) =>
        row.photographer?.exposure != null &&
        row.photographer?.temperature != null &&
        row.photographer?.tint != null &&
        row.suggested?.exposure != null &&
        row.suggested?.temperature != null &&
        row.suggested?.tint != null,
    );
    if (!rows.length) return null;
    return {
      count: rows.length,
      exposure: rows.reduce((sum, r) => sum + Math.abs(r.suggested!.exposure! - r.photographer!.exposure!), 0) / rows.length,
      temperature: rows.reduce((sum, r) => sum + Math.abs(r.suggested!.temperature! - r.photographer!.temperature!), 0) / rows.length,
      tint: rows.reduce((sum, r) => sum + Math.abs(r.suggested!.tint! - r.photographer!.tint!), 0) / rows.length,
    };
  }, [report]);

  async function choose(which: "training" | "edits" | "testing") {
    const selected = await open({
      directory: true,
      multiple: false,
      title: which === "training" ? "בחר תיקיית RAW שלמדנו ממנה" : which === "edits" ? "בחר תיקיית XMP סופיים" : "בחר תיקיית RAW חדשה למבחן",
    });
    if (!selected || Array.isArray(selected)) return;
    setError("");
    setReport(null);
    if (which === "testing") setTestRoot(selected);
    else {
      setProfile(null);
      if (which === "training") setTrainRoot(selected);
      else setEditsRoot(selected);
    }
  }

  async function prepare() {
    if (!trainRoot || !editsRoot || busy) return;
    setBusy(true);
    setError("");
    setReport(null);
    try {
      const result = await createTestingProfile({
        raw_root: trainRoot,
        edits_root: editsRoot,
        photographer_id: "local-photographer",
        event_label: "brain-studio-training",
        learning_source: "raw",
      });
      setProfile(result);
      if (!result.baseline || !result.usable_pairs) {
        setError("לא נמצאו זוגות RAW/XMP שמישים לחישוב בסיס. בדוק התאמה בין קובצי המקור לעריכות.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הכנת החומר נכשלה.");
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    if (!ready || !testRoot || busy) return;
    if (!separateFolders(trainRoot, testRoot)) {
      setError("תיקיות האימון והמבחן חייבות להיות נפרדות, בלי חפיפה או תיקיית-בת.");
      return;
    }
    setBusy(true);
    setError("");
    setReport(null);
    setProgress(0);
    try {
      const started = await startEventScan(testRoot);
      let eventId = "";
      for (let attempt = 0; attempt < 2400; attempt += 1) {
        const job = await getEventScanProgress(started.job_id);
        setProgress(job.percent);
        if (job.status === "failed") throw new Error(job.error || "סריקת תיקיית המבחן נכשלה.");
        if (job.status === "completed") {
          if (!job.result) throw new Error("סריקת האירוע הסתיימה ללא תוצאה.");
          eventId = job.result.event.id;
          break;
        }
        await new Promise<void>((resolve) => window.setTimeout(resolve, 250));
      }
      if (!eventId) throw new Error("סריקת אירוע המבחן לא הסתיימה. ניתן לנסות שוב.");
      const nextReport = await getReviewSheet(eventId, "raw");
      if (!nextReport.files.length) throw new Error("לא נמצאו תמונות RAW בתיקיית המבחן.");
      setReport(nextReport);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "בדיקת תיקיית המבחן נכשלה.");
    } finally {
      setProgress(null);
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen} dir="rtl">
      <header className={styles.header}>
        <span className={styles.eyebrow}>PROGRAPHER / BRAIN STUDIO</span>
        <h1>מהאימון למבחן — דרך ProGrapher</h1>
        <p>מסך עבודה ראשוני שמחבר תיקיית RAW + XMP לתיקיית RAW נפרדת, באמצעות מנגנוני הפרופיל והאירועים הקיימים.</p>
        <div className={styles.researchTag}>מצב מחקר · Baseline בלבד · לא AUTO-D</div>
      </header>

      <section className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.stageNum}>01 / מקור הלמידה</div>
          <h2>תיקיית אימון A</h2>
          <p>בחר RAW מקוריים ותיקיית XMP עם העריכות הסופיות של אותו צלם. בגרסה זו אין עדיין אימון מתוך LRCAT.</p>
          <button className={styles.pick} type="button" onClick={() => void choose("training")} disabled={busy}>
            <span>RAW מקוריים</span><strong>{trainRoot || "בחר תיקייה"}</strong>
          </button>
          <button className={styles.pick} type="button" onClick={() => void choose("edits")} disabled={busy}>
            <span>עריכות Lightroom · XMP</span><strong>{editsRoot || "בחר תיקייה"}</strong>
          </button>
          <button className={styles.primary} type="button" disabled={busy || !trainRoot || !editsRoot} onClick={() => void prepare()}>
            {busy && !progress ? "מכין נתונים…" : "בדוק זוגות וצור Baseline"}
          </button>
          {profile && (
            <div className={styles.result}>
              <strong>{profile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים</strong>
              <span>RAW: {profile.raw_files} · XMP: {profile.xmp_files} · זוגות מותאמים: {profile.matched_pairs}</span>
              <span>{profile.baseline ? "חציון Exposure / Temperature / Tint נשמר בפרופיל הבדיקה המקומי." : "אין עדיין Baseline תקף."}</span>
              {profile.warnings.map((warning, index) => <small key={index}>{warning}</small>)}
            </div>
          )}
        </article>

        <article className={styles.card}>
          <div className={styles.stageNum}>02 / אירוע שלא השתתף באימון</div>
          <h2>תיקיית מבחן B</h2>
          <p>התיקייה חייבת להיות נפרדת מאימון A ולכלול תמונות שונות. הסריקה משתמשת בשירות האירועים הקיים ואינה עורכת קובצי מקור.</p>
          <button className={styles.pick} type="button" onClick={() => void choose("testing")} disabled={busy}>
            <span>RAW למבחן</span><strong>{testRoot || "בחר תיקייה"}</strong>
          </button>
          <button className={styles.primary} type="button" onClick={() => void test()}
            disabled={busy || !ready || !testRoot || !separateFolders(trainRoot, testRoot)}>
            {progress != null ? "סורק… " + progress + "%" : "הפק תחזיות Baseline"}
          </button>
          <div className={styles.result}>
            <strong>מה נבדק כעת?</strong>
            <span>אותו חציון נשלח לכל תמונת RAW. כך אנחנו בודקים את החיבור בין בחירת תיקיות, יצירת פרופיל ומערכת הסקירה — לפני שילוב מודל החיזוי.</span>
            <small>זה אינו אימון AI ואינו מוכיח חיזוי אישי לפי תוכן התמונה. אין עדיין בדיקת hash לזיהוי תמונות שהועתקו בין A ו־B.</small>
          </div>
        </article>
      </section>

      {error && <div className={styles.error} role="alert">{error}</div>}

      {report && (
        <section className={styles.report}>
          <div className={styles.stageNum}>03 / תוצאות על תיקייה B</div>
          <h2>{report.files.length.toLocaleString("he-IL")} תמונות RAW נקלטו</h2>
          <p>מודל בדיקה: median baseline. חיזויי AUTO-D והפעלה אוטומטית ב־Lightroom יחוברו בהמשך, לאחר בדיקות בטיחות.</p>
          {scores ? (
            <div className={styles.stats}>
              <div><small>תמונות עם אמת השוואתית</small><strong>{scores.count}</strong></div>
              <div><small>Exposure MAE (stops)</small><strong>{fmt(scores.exposure, 3)}</strong></div>
              <div><small>Temperature MAE (K)</small><strong>{fmt(scores.temperature, 1)}</strong></div>
              <div><small>Tint MAE</small><strong>{fmt(scores.tint, 2)}</strong></div>
            </div>
          ) : <p className={styles.truth}>לא נמצאו עריכות אמת תואמות בתיקיית B; ניתן להציג תחזיות, אך לא לטעון לדיוק בלי תוצאות הצלם.</p>}
          <div className={styles.tableWrap}>
            <table>
              <thead><tr><th>תמונה</th><th>Exposure</th><th>Temperature</th><th>Tint</th></tr></thead>
              <tbody>{report.files.slice(0, 30).map((file) => (
                <tr key={file.fingerprint}>
                  <td>{file.filename}</td>
                  <td>{fmt(file.suggested?.exposure)}</td>
                  <td>{fmt(file.suggested?.temperature, 0)}</td>
                  <td>{fmt(file.suggested?.tint, 0)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <small className={styles.muted}>מוצגות 30 תמונות ראשונות; קובצי RAW נשארים ללא שינוי. אין עדיין ייצוא batch.</small>
        </section>
      )}
    </main>
  );
}
