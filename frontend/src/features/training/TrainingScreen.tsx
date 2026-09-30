"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  activateTestingProfile,
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

  const applyProfile = useCallback((value: TestingProfile | null) => {
    setProfile(value);
    if (!value) return;
    setRawRoot(value.raw_root);
    setEditsRoot(value.edits_root);
    setPhotographerId(value.photographer_id);
    setEventLabel(value.event_label);
    setLearningSource(value.learning_source);
  }, []);

  useEffect(() => {
    void getTestingProfile()
      .then(applyProfile)
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת הפרופיל נכשלה.");
      });
  }, [applyProfile]);

  async function switchLearningSource(source: LearningSource) {
    setLearningSource(source);
    setError("");
    try {
      applyProfile(await activateTestingProfile(source));
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "";
      if (message.includes("עדיין אין")) {
        setProfile(null);
        setRawRoot("");
        setEditsRoot("");
        return;
      }
      setError(message || "טעינת המסלול נכשלה.");
    }
  }

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
      if (learningSource === "raw" && !editsRoot) setEditsRoot(selected);
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
          edits_root:
            learningSource === "jpeg" ? editsRoot : editsRoot || rawRoot,
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
      <header className={styles.labHead}>
        <div>
          <span className={styles.sectionEyebrow}>מעבדת בדיקה</span>
          <h2>למידה</h2>
        </div>
        <ol className={styles.steps}>
          <li className={rawRoot ? styles.stepOn : undefined}>בחירת תיקיות</li>
          <li className={profile && profile.matched_pairs > 0 ? styles.stepOn : undefined}>זיהוי זוגות</li>
          <li className={profile && profile.usable_pairs > 0 ? styles.stepOn : undefined}>בסיס לבדיקה</li>
        </ol>
      </header>
      <div className={styles.lab}>
        <button
          type="button"
          className={learningSource === "raw" ? styles.labCardActive : styles.labCard}
          onClick={() => void switchLearningSource("raw")}
        >
          <strong>RAW</strong>
          <span>RAW + XMP. בסיס חשיפה, טמפרטורה וגוון.</span>
        </button>
        <button
          type="button"
          className={learningSource === "jpeg" ? styles.labCardActive : styles.labCard}
          onClick={() => void switchLearningSource("jpeg")}
        >
          <strong>JPEG</strong>
          <span>JPEG מקור + JPEG ערוך. בלי מתכון Lightroom.</span>
        </button>
      </div>

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
          <button className={styles.secondary} type="button" onClick={() => void chooseFolder("raw")}>
            {learningSource === "jpeg" ? "תיקיית JPEG מקור" : "תיקיית RAW"}
          </button>
          <button className={styles.secondary} type="button" onClick={() => void chooseFolder("edits")}>
            {learningSource === "jpeg" ? "תיקיית JPEG ערוך" : "תיקיית XMP"}
          </button>
          <button
            className={styles.primary}
            type="button"
            disabled={busy || !rawRoot || (learningSource === "jpeg" && !editsRoot)}
            onClick={() => void build()}
          >
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
        <section className={styles.profilePanel}>
          <div className={styles.profileHeader}>
            <div>
              <span className={styles.sectionEyebrow}>תוצאות הבדיקה</span>
              <h3>
                {profile.learning_source === "jpeg"
                  ? "מאגר ה-JPEG הנוכחי"
                  : "בסיס ה-RAW הנוכחי"}
              </h3>
            </div>
            <span
              className={
                profile.learning_source === "jpeg"
                  ? `${styles.sourceBadge} ${styles.sourceJpeg}`
                  : `${styles.sourceBadge} ${styles.sourceRaw}`
              }
            >
              {profile.learning_source === "jpeg" ? "JPEG" : "RAW"}
            </span>
          </div>

          <div className={styles.profileInfo}>
            <div className={styles.infoBlock}>
              <span>מצב המסלול</span>
              <p>{profile.note}</p>
            </div>

            {profile.dataset_manifest_path && (
              <div className={styles.infoBlock}>
                <span>קובץ Manifest</span>
                <bdi className={styles.pathValue}>
                  {profile.dataset_manifest_path}
                </bdi>
              </div>
            )}
          </div>

          <div
            className={
              profile.learning_source === "jpeg"
                ? `${styles.metrics} ${styles.metricsJpeg}`
                : styles.metrics
            }
          >
            <div className={styles.metric}>
              <span>
                {profile.learning_source === "jpeg" ? "קובצי JPEG" : "קובצי RAW"}
              </span>
              <strong>
                <bdi>{profile.raw_files.toLocaleString("he-IL")}</bdi>
              </strong>
            </div>

            <div className={styles.metric}>
              <span>זוגות שנמצאו</span>
              <strong>
                <bdi>{profile.matched_pairs.toLocaleString("he-IL")}</bdi>
              </strong>
            </div>

            <div className={styles.metric}>
              <span>זוגות שמישים</span>
              <strong>
                <bdi>{profile.usable_pairs.toLocaleString("he-IL")}</bdi>
              </strong>
            </div>

            {profile.learning_source === "raw" && (
              <>
                <div className={styles.metric}>
                  <span>חשיפה בסיסית</span>
                  <strong>
                    <bdi>
                      {profile.baseline
                        ? profile.baseline.exposure.toFixed(2)
                        : "לא זמין"}
                    </bdi>
                  </strong>
                </div>

                <div className={styles.metric}>
                  <span>טמפרטורה בסיסית</span>
                  <strong>
                    <bdi>
                      {profile.baseline
                        ? `${profile.baseline.temperature} K`
                        : "לא זמין"}
                    </bdi>
                  </strong>
                </div>

                <div className={styles.metric}>
                  <span>גוון בסיסי</span>
                  <strong>
                    <bdi>
                      {profile.baseline
                        ? profile.baseline.tint
                        : "לא זמין"}
                    </bdi>
                  </strong>
                </div>
              </>
            )}
          </div>

          {profile.warnings.length > 0 && (
            <div className={styles.warningStack}>
              <div className={styles.warningHeader}>
                <strong>מה צריך לדעת על המדגם הזה</strong>
                <span>{profile.warnings.length}</span>
              </div>
              {profile.warnings.map((warning) => (
                <div className={styles.warning} key={warning}>
                  <span className={styles.warningDot} aria-hidden="true" />
                  <p>{warning}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
