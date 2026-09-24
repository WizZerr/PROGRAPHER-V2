"use client";

import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  createTestingProfile,
  getTestingProfile,
  type LearningSource,
  type TestingProfile,
} from "@/features/testing/testing.api";
import styles from "@/features/testing/testing.module.css";

export default function TrainingScreen() {
  const [profile, setProfile] = useState<TestingProfile | null>(null);
  const [rawRoot, setRawRoot] = useState("");
  const [editsRoot, setEditsRoot] = useState("");
  const [photographerId, setPhotographerId] = useState("local-photographer");
  const [eventLabel, setEventLabel] = useState("reference");
  const [learningSource, setLearningSource] = useState<LearningSource>("raw");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void getTestingProfile()
      .then((value) => {
        setProfile(value);
        if (!value) return;
        setRawRoot(value.raw_root);
        setEditsRoot(value.edits_root);
        setPhotographerId(value.photographer_id);
        setEventLabel(value.event_label);
        setLearningSource(value.learning_source ?? "raw");
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת הפרופיל נכשלה.");
      });
  }, []);

  async function chooseFolder(target: "raw" | "edits") {
    setError("");
    const selected = await open({
      directory: true,
      multiple: false,
      title:
        target === "raw"
          ? learningSource === "jpeg"
            ? "בחר תיקיית JPEG מקור"
            : "בחר תיקיית RAW"
          : learningSource === "jpeg"
            ? "בחר תיקיית JPEG ערוך"
            : "בחר תיקיית XMP",
    });
    if (!selected || Array.isArray(selected)) return;
    if (target === "raw") {
      setRawRoot(selected);
      if (!editsRoot) setEditsRoot(selected);
      return;
    }
    setEditsRoot(selected);
  }

  async function build() {
    setBusy(true);
    setError("");
    try {
      setProfile(
        await createTestingProfile({
          raw_root: rawRoot,
          edits_root: editsRoot || rawRoot,
          photographer_id: photographerId,
          event_label: eventLabel,
          learning_source: learningSource,
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "בניית הפרופיל נכשלה.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.screen}>
      <section className={styles.hero}>
        <h2>מעבדת בדיקה</h2>
        <p>
          {learningSource === "jpeg"
            ? "פרופיל JPEG לומד רק מזוגות JPEG מקורי ו-JPEG ערוך. אין בו מתכון Lightroom, והוא לא מתערבב עם פרופיל RAW."
            : "פרופיל RAW לומד מ-RAW ומ-XMP של Lightroom. בונים ממנו בסיס חציון לחשיפה, טמפרטורה וגוון. הוא לא מתערבב עם פרופיל JPEG."}
        </p>
      </section>

      <section className={styles.panel}>
        <div className={styles.row}>
          <label className={styles.field}>
            <span>צלם</span>
            <input
              value={photographerId}
              onChange={(event) => setPhotographerId(event.target.value)}
            />
          </label>
          <label className={styles.field}>
            <span>שם המדגם</span>
            <input
              value={eventLabel}
              onChange={(event) => setEventLabel(event.target.value)}
            />
          </label>
        </div>
        <div className={styles.actions}>
          <button
            className={learningSource === "raw" ? styles.primary : styles.secondary}
            type="button"
            onClick={() => setLearningSource("raw")}
          >
            למידה מ-RAW
          </button>
          <button
            className={learningSource === "jpeg" ? styles.primary : styles.secondary}
            type="button"
            onClick={() => setLearningSource("jpeg")}
          >
            למידה מ-JPEG
          </button>
        </div>
        <div className={styles.actions}>
          <button className={styles.secondary} type="button" onClick={() => void chooseFolder("raw")}>
            {learningSource === "jpeg" ? "תיקיית JPEG מקור" : "תיקיית RAW"}
          </button>
          <button className={styles.secondary} type="button" onClick={() => void chooseFolder("edits")}>
            {learningSource === "jpeg" ? "תיקיית JPEG ערוך" : "תיקיית XMP"}
          </button>
          <button className={styles.primary} type="button" disabled={busy || !rawRoot} onClick={() => void build()}>
            {busy ? "קורא קבצים…" : "בנה בסיס בדיקה"}
          </button>
        </div>
        <p className={styles.note}>
          {learningSource === "jpeg" ? "JPEG מקור" : "RAW"}:{" "}
          <bdi className={styles.ltr}>{rawRoot || "עדיין לא נבחר"}</bdi>
        </p>
        <p className={styles.note}>
          {learningSource === "jpeg" ? "JPEG ערוך" : "XMP"}:{" "}
          <bdi className={styles.ltr}>{editsRoot || rawRoot || "אותה תיקייה"}</bdi>
        </p>
      </section>

      {error && <p className={styles.error}>{error}</p>}

      {profile && (
        <section className={styles.panel}>
          <h3>הבסיס הנוכחי</h3>
          <p className={styles.note}>
            מסלול: {profile.learning_source === "jpeg" ? "JPEG" : "RAW"}
          </p>
          <p className={styles.note}>{profile.note}</p>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <span>{profile.learning_source === "jpeg" ? "JPEG" : "RAW"}</span>
              <strong className={styles.ltr}>{profile.raw_files}</strong>
            </div>
            <div className={styles.metric}>
              <span>זוגות</span>
              <strong className={styles.ltr}>{profile.matched_pairs}</strong>
            </div>
            <div className={styles.metric}>
              <span>שמישים</span>
              <strong className={styles.ltr}>{profile.usable_pairs}</strong>
            </div>
            <div className={styles.metric}>
              <span>חשיפה</span>
              <strong className={styles.ltr}>{profile.baseline ? profile.baseline.exposure : "—"}</strong>
            </div>
            <div className={styles.metric}>
              <span>טמפרטורה</span>
              <strong className={styles.ltr}>{profile.baseline ? `${profile.baseline.temperature} K` : "—"}</strong>
            </div>
            <div className={styles.metric}>
              <span>גוון</span>
              <strong className={styles.ltr}>{profile.baseline ? profile.baseline.tint : "—"}</strong>
            </div>
          </div>
          {profile.warnings.map((warning) => (
            <p className={styles.warning} key={warning}>{warning}</p>
          ))}
        </section>
      )}
    </div>
  );
}
