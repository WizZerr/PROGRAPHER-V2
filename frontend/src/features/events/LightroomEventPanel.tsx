"use client";

import { useState } from "react";
import {
  chooseAnchors,
  completeEvent,
  undoEventStep,
  type AnchorPlan,
  type AutomaticExposure,
  type CompleteResult,
} from "./eventEdit.api";
import styles from "./LightroomEventPanel.module.css";

const STORAGE_KEY = "pg.lightroomEvent";

type Saved = {
  catalogPath: string;
  plan: AnchorPlan | null;
  result: CompleteResult | null;
};

export function loadSavedLightroomEvent(): Saved | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

function save(state: Saved | null) {
  try {
    if (state) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // per-viewer convenience only
  }
}

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

function automaticText(auto: AutomaticExposure): string {
  if (auto.state === "on") return `חשיפה אוטומטית: פעילה (${auto.photos ?? 0} תמונות).`;
  switch (auto.reason) {
    case "face_model_missing":
      return "חשיפה אוטומטית כבויה: קובץ זיהוי הפנים לא מותקן. תמונות בלי עוגן קיבלו את החשיפה הממוצעת של העוגנים.";
    case "no_smart_previews":
      return "חשיפה אוטומטית כבויה: אין Smart Previews ליד הקטלוג. תמונות בלי עוגן קיבלו את החשיפה הממוצעת של העוגנים.";
    case "too_few_anchor_faces":
      return "חשיפה אוטומטית כבויה: פחות מ-20 עוגנים ערוכים עם פנים. תמונות בלי עוגן קיבלו את החשיפה הממוצעת של העוגנים.";
    case "decoder_unavailable":
      return "חשיפה אוטומטית כבויה: פענוח ה-Smart Previews לא זמין. תמונות בלי עוגן קיבלו את החשיפה הממוצעת של העוגנים.";
    default:
      return "חשיפה אוטומטית כבויה.";
  }
}

const n = (value: number) => value.toLocaleString("he-IL");

export default function LightroomEventPanel({
  catalogPath,
  initial,
  onClose,
}: {
  catalogPath: string;
  initial: Saved | null;
  onClose: () => void;
}) {
  const [plan, setPlan] = useState<AnchorPlan | null>(initial?.plan ?? null);
  const [result, setResult] = useState<CompleteResult | null>(initial?.result ?? null);
  const [busy, setBusy] = useState<"" | "anchors" | "complete" | "undo">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function remember(nextPlan: AnchorPlan | null, nextResult: CompleteResult | null) {
    setPlan(nextPlan);
    setResult(nextResult);
    save({ catalogPath, plan: nextPlan, result: nextResult });
  }

  async function run(kind: "anchors" | "complete" | "undo") {
    setBusy(kind);
    setError("");
    setMessage("");
    try {
      if (kind === "anchors") {
        remember(await chooseAnchors(catalogPath), null);
      } else if (kind === "complete") {
        remember(plan, await completeEvent(catalogPath));
      } else if (result?.backup) {
        await undoEventStep(catalogPath, result.backup);
        remember(plan, null);
        setMessage("הקטלוג הוחזר בדיוק למצב שלפני ההשלמה.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הפעולה נכשלה.");
    } finally {
      setBusy("");
    }
  }

  function close() {
    save(null);
    onClose();
  }

  return (
    <section className={styles.panel} aria-label="אירוע מ-Lightroom">
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>אירוע מקטלוג Lightroom</span>
          <h3 title={catalogPath}>{fileName(catalogPath)}</h3>
        </div>
        <button type="button" className={styles.close} onClick={close} disabled={!!busy}>
          סגור
        </button>
      </header>

      <p className={styles.note}>
        בכל שלב Lightroom צריך להיות סגור. לפני כל שינוי ProGrapher שומר גיבוי של הקטלוג.
      </p>

      <ol className={styles.steps}>
        <li className={plan ? styles.done : styles.current}>
          <div>
            <strong>1. בחירת תמונות לעריכה</strong>
            {plan ? (
              <span>
                סומנו {n(plan.anchors)} תמונות מתוך {n(plan.photos)} ({n(plan.moments)} רגעים). ב-Lightroom הן
                ב-Collection בשם &quot;{plan.collection}&quot; ועם תווית סגולה.
              </span>
            ) : (
              <span>ProGrapher מחלק את האירוע לרגעים ובוחר תמונה אחת מכל רגע מרכזי.</span>
            )}
          </div>
          <button
            type="button"
            className={plan ? styles.secondary : styles.primary}
            onClick={() => void run("anchors")}
            disabled={!!busy}
          >
            {busy === "anchors" ? "בוחר…" : plan ? "בחר מחדש" : "בחר תמונות לעריכה"}
          </button>
        </li>

        <li className={!plan ? styles.waiting : result ? styles.done : styles.current}>
          <div>
            <strong>2. עריכה ב-Lightroom</strong>
            <span>
              פתח את הקטלוג ב-Lightroom, ערוך את התמונות ב-Collection &quot;ProGrapher - Edit these&quot; כמו
              שאתה עורך תמיד, וסגור את Lightroom.
            </span>
          </div>
        </li>

        <li className={!plan ? styles.waiting : result ? styles.done : styles.current}>
          <div>
            <strong>3. השלמת האירוע</strong>
            {busy === "complete" ? (
              <span>ProGrapher משלים את האירוע. עם חשיפה אוטומטית זה יכול לקחת כמה דקות.</span>
            ) : result ? (
              <span>
                נכתבו {n(result.written)} תמונות: {n(result.from_anchor)} לפי העוגן של הרגע שלהן,{" "}
                {n(result.automatic)} בחשיפה אוטומטית, {n(result.event_level)} לפי ממוצע העוגנים. תמונות שערכת
                בעצמך ({n(result.skipped_edited)}) לא שונו. בכל תמונה מופיע ב-History שלב &quot;ProGrapher&quot;.
                <br />
                {automaticText(result.automatic_exposure)}
              </span>
            ) : (
              <span>ProGrapher קורא את העוגנים שערכת וכותב את שאר התמונות ישר לקטלוג.</span>
            )}
          </div>
          {result ? (
            <button
              type="button"
              className={styles.undo}
              onClick={() => void run("undo")}
              disabled={!!busy || !result.backup}
            >
              {busy === "undo" ? "מחזיר…" : "בטל"}
            </button>
          ) : (
            <button
              type="button"
              className={styles.primary}
              onClick={() => void run("complete")}
              disabled={!!busy || !plan}
            >
              {busy === "complete" ? "משלים…" : "השלם את האירוע"}
            </button>
          )}
        </li>
      </ol>

      {message ? <div className={styles.info}>{message}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}
    </section>
  );
}
