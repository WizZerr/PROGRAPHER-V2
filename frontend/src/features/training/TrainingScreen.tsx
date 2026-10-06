"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  activateTestingProfile,
  createTestingProfile,
  getTestingProfile,
  type LearningSource,
  type TestingProfile,
} from "@/features/testing/testing.api";
import styles from "@/features/testing/testing.module.css";

export default function TrainingScreen() {
  const openView = useWorkspaceNav();
  const [profile, setProfile] = useState<TestingProfile | null>(null);
  const [sourceRoot, setSourceRoot] = useState("");
  const [editsRoot, setEditsRoot] = useState("");
  const [learningSource, setLearningSource] = useState<LearningSource>("raw");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const applyProfile = useCallback((value: TestingProfile | null) => {
    setProfile(value);
    if (!value) return;
    setSourceRoot(value.raw_root);
    setEditsRoot(value.edits_root);
    setLearningSource(value.learning_source);
  }, []);

  useEffect(() => {
    void getTestingProfile()
      .then(applyProfile)
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "לא ניתן לטעון את מצב הלמידה.");
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
        setSourceRoot("");
        setEditsRoot("");
        return;
      }
      setError(message || "לא ניתן לפתוח את מסלול הלמידה.");
    }
  }

  async function chooseFolder(target: "source" | "edits") {
    const selected = await open({
      directory: true,
      multiple: false,
      title:
        target === "source"
          ? learningSource === "jpeg"
            ? "בחר תיקיית JPEG מקור"
            : "בחר תיקיית RAW"
          : learningSource === "jpeg"
            ? "בחר תיקיית JPEG ערוך"
            : "בחר תיקיית XMP",
    });

    if (!selected || Array.isArray(selected)) return;

    if (target === "source") {
      setSourceRoot(selected);
      if (learningSource === "raw" && !editsRoot) setEditsRoot(selected);
    } else {
      setEditsRoot(selected);
    }
  }

  async function build() {
    setBusy(true);
    setError("");
    try {
      setProfile(
        await createTestingProfile({
          raw_root: sourceRoot,
          edits_root: learningSource === "jpeg" ? editsRoot : editsRoot || sourceRoot,
          photographer_id: "local-photographer",
          event_label: "profile-learning",
          learning_source: learningSource,
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לבדוק את החומר.");
    } finally {
      setBusy(false);
    }
  }

  const hasRequiredMaterial =
    Boolean(sourceRoot) && (learningSource === "raw" || Boolean(editsRoot));

  return (
    <main className={styles.screen}>
      <header className={styles.wizardHeader}>
        <button className={styles.backButton} type="button" onClick={() => openView("profile")}>
          → חזרה לפרופיל
        </button>
        <div>
          <span className={styles.eyebrow}>בניית הפרופיל</span>
          <h2>בוא נלמד איך אתה עורך.</h2>
          <p>שלושה צעדים קצרים. בחר סוג חומר, הוסף אותו, ו-ProGrapher יבדוק אם הוא מתאים ללמידה.</p>
        </div>
      </header>

      <section className={styles.steps} aria-label="שלבי בניית הפרופיל">
        <div className={styles.stepActive}><span>1</span><strong>סוג החומר</strong></div>
        <div className={sourceRoot ? styles.stepActive : styles.step}><span>2</span><strong>בחירת חומר</strong></div>
        <div className={profile ? styles.stepActive : styles.step}><span>3</span><strong>בדיקה</strong></div>
      </section>

      <section className={styles.block}>
        <div className={styles.blockHead}>
          <span className={styles.blockIndex}>01</span>
          <div>
            <h3>איזה חומר יש לך?</h3>
            <p>בחר את הדרך שמתאימה למה שכבר קיים אצלך.</p>
          </div>
        </div>

        <div className={styles.modeGrid}>
          <button
            type="button"
            className={learningSource === "raw" ? styles.modeActive : styles.mode}
            onClick={() => void switchLearningSource("raw")}
          >
            <span className={styles.modeTag}>RAW</span>
            <strong>RAW + Lightroom/XMP</strong>
            <small>קבצי RAW והעריכות ששמרת עבורם.</small>
          </button>

          <button
            type="button"
            className={learningSource === "jpeg" ? styles.modeActive : styles.mode}
            onClick={() => void switchLearningSource("jpeg")}
          >
            <span className={styles.modeTag}>JPEG</span>
            <strong>JPEG לפני + אחרי</strong>
            <small>תמונות המקור מול הקבצים הסופיים שכבר ערכת.</small>
          </button>

          <button type="button" className={styles.modeDisabled} disabled>
            <span className={styles.modeTag}>JPEG + LR</span>
            <strong>JPEG + Lightroom Catalog</strong>
            <small>מסלול נפרד שנחבר בהמשך.</small>
          </button>
        </div>
      </section>

      <section className={styles.block}>
        <div className={styles.blockHead}>
          <span className={styles.blockIndex}>02</span>
          <div>
            <h3>בחר את החומר</h3>
            <p>
              {learningSource === "jpeg"
                ? "צריך תיקיית מקור ותיקיית JPEG ערוך."
                : "צריך RAW ואת עריכות ה-XMP המתאימות."}
            </p>
          </div>
        </div>

        <div className={styles.folderGrid}>
          <button type="button" className={styles.folderCard} onClick={() => void chooseFolder("source")}>
            <span className={styles.folderIcon} aria-hidden="true">＋</span>
            <div>
              <strong>{learningSource === "jpeg" ? "JPEG מקור" : "RAW מקור"}</strong>
              <small>{sourceRoot || "בחר תיקייה"}</small>
            </div>
          </button>

          <button type="button" className={styles.folderCard} onClick={() => void chooseFolder("edits")}>
            <span className={styles.folderIcon} aria-hidden="true">＋</span>
            <div>
              <strong>{learningSource === "jpeg" ? "JPEG ערוך" : "עריכות XMP"}</strong>
              <small>{editsRoot || (learningSource === "raw" && sourceRoot ? sourceRoot : "בחר תיקייה")}</small>
            </div>
          </button>
        </div>

        <button
          className={styles.checkButton}
          type="button"
          disabled={busy || !hasRequiredMaterial}
          onClick={() => void build()}
        >
          {busy ? "בודק את החומר…" : "בדוק את החומר"}
        </button>
      </section>

      {error ? <div className={styles.error}>{error}</div> : null}

      {profile ? (
        <section className={styles.result}>
          <div className={styles.resultHero}>
            <span className={styles.resultDot} aria-hidden="true" />
            <div>
              <span>תוצאת הבדיקה</span>
              <h3>
                {profile.usable_pairs.toLocaleString("he-IL")} זוגות מוכנים ללמידה
              </h3>
              <p>{profile.note}</p>
            </div>
          </div>

          <div className={styles.resultStats}>
            <div><span>קבצים</span><strong>{profile.raw_files.toLocaleString("he-IL")}</strong></div>
            <div><span>התאמות</span><strong>{profile.matched_pairs.toLocaleString("he-IL")}</strong></div>
            <div><span>שמישים</span><strong>{profile.usable_pairs.toLocaleString("he-IL")}</strong></div>
          </div>

          {profile.warnings.length > 0 ? (
            <div className={styles.warnings}>
              <strong>יש כמה דברים שצריך לבדוק</strong>
              {profile.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}

          <details className={styles.technical}>
            <summary>פרטים טכניים</summary>
            <dl>
              <div><dt>מסלול</dt><dd>{profile.learning_source === "jpeg" ? "JPEG PAIRS" : "RAW + XMP"}</dd></div>
              <div><dt>Manifest</dt><dd>{profile.dataset_manifest_path || "לא נוצר"}</dd></div>
              <div><dt>מקור</dt><dd>{profile.raw_root}</dd></div>
              <div><dt>עריכות</dt><dd>{profile.edits_root}</dd></div>
            </dl>
          </details>

          <button className={styles.finishButton} type="button" onClick={() => openView("profile")}>
            חזרה לפרופיל
          </button>
        </section>
      ) : null}
    </main>
  );
}
