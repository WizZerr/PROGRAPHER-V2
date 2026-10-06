"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  getPhotographerSetup,
  saveStylePreferences,
  selectEditsFolder,
  selectLightroomCatalog,
  type PhotographerSetupOverview,
  type PhotographerSetupStatus,
} from "./profile.api";
import styles from "./ProfileScreen.module.css";

const STATUS_LABELS: Record<PhotographerSetupStatus, string> = {
  no_profile: "עדיין אין פרופיל",
  data_review: "בודק את החומר",
  training: "הפרופיל באימון",
  needs_more_data: "צריך עוד חומר",
  experimental: "פרופיל ניסויי",
  evaluated: "הפרופיל מוכן",
};

type TrackProps = {
  eyebrow: string;
  title: string;
  copy: string;
  badge: string;
  disabled?: boolean;
  onClick?: () => void;
};

function LearningTrack({
  eyebrow,
  title,
  copy,
  badge,
  disabled = false,
  onClick,
}: TrackProps) {
  return (
    <article className={disabled ? `${styles.track} ${styles.trackDisabled}` : styles.track}>
      <div className={styles.trackTop}>
        <span className={styles.trackEyebrow}>{eyebrow}</span>
        <span className={disabled ? styles.trackBadgeMuted : styles.trackBadge}>{badge}</span>
      </div>
      <h3>{title}</h3>
      <p>{copy}</p>
      <button type="button" disabled={disabled} onClick={onClick}>
        {disabled ? "עדיין לא זמין" : "התחל למידה"}
        <span aria-hidden="true">←</span>
      </button>
    </article>
  );
}

export default function ProfileScreen() {
  const openView = useWorkspaceNav();
  const [overview, setOverview] = useState<PhotographerSetupOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [styleName, setStyleName] = useState("");
  const [presetPath, setPresetPath] = useState<string | null>(null);
  const [profileMode, setProfileMode] = useState<"from_source" | "explicit">("from_source");
  const [cameraProfile, setCameraProfile] = useState("");

  const applyOverview = useCallback((value: PhotographerSetupOverview) => {
    setOverview(value);
    setStyleName(value.setup.style_name ?? "");
    setPresetPath(value.setup.preset_path);
    setProfileMode(value.setup.color_profile_mode);
    setCameraProfile(value.setup.camera_profile ?? "");
  }, []);

  const refresh = useCallback(async () => {
    setError("");
    try {
      applyOverview(await getPhotographerSetup());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לטעון את הפרופיל.");
    }
  }, [applyOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function chooseCatalog() {
    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר קטלוג Lightroom",
      filters: [{ name: "Lightroom Catalog", extensions: ["lrcat"] }],
    });
    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    setError("");
    try {
      applyOverview(await selectLightroomCatalog(selected));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לקרוא את קטלוג Lightroom.");
    } finally {
      setBusy(false);
    }
  }

  async function chooseEditsFolder() {
    const selected = await open({
      multiple: false,
      directory: true,
      title: "בחר תיקיית עריכות / XMP",
    });
    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    setError("");
    try {
      applyOverview(await selectEditsFolder(selected));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לקרוא את תיקיית העריכות.");
    } finally {
      setBusy(false);
    }
  }

  async function choosePreset() {
    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר פריסט Lightroom",
      filters: [{ name: "Lightroom Preset", extensions: ["xmp"] }],
    });
    if (!selected || Array.isArray(selected)) return;
    setPresetPath(selected);
  }

  async function saveStyle() {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      const result = await saveStylePreferences({
        style_name: styleName.trim() || null,
        preset_path: presetPath,
        color_profile_mode: profileMode,
        camera_profile: profileMode === "explicit" ? cameraProfile.trim() || null : null,
      });
      applyOverview(result);
      setSaved("ההגדרות נשמרו.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "לא ניתן לשמור את ההגדרות.");
    } finally {
      setBusy(false);
    }
  }

  const setup = overview?.setup;
  const reasons = overview?.readiness_reasons ?? [];
  const profileReady = setup?.status === "evaluated";
  const statusLabel = setup ? STATUS_LABELS[setup.status] : "טוען…";

  return (
    <section className={styles.screen}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>הפרופיל שלי</span>
          <h2>{profileReady ? "הסגנון שלך מוכן לעבודה." : "מלמדים את ProGrapher לערוך כמוך."}</h2>
          <p>
            הפרופיל שלך שומר את הדרך שבה אתה עורך. בחר איך ללמד אותו,
            ו-ProGrapher ינחה אותך רק במה שצריך.
          </p>
        </div>
        <div className={styles.heroStatus}>
          <span className={profileReady ? styles.readyDot : styles.pendingDot} aria-hidden="true" />
          <div>
            <small>מצב הפרופיל</small>
            <strong>{statusLabel}</strong>
          </div>
        </div>
      </header>

      {error ? <div className={styles.error}>{error}</div> : null}
      {saved ? <div className={styles.success}>{saved}</div> : null}

      {!profileReady && (
        <section className={styles.nextStep}>
          <div>
            <span className={styles.sectionLabel}>השלב הבא</span>
            <h3>{reasons.length > 0 ? "צריך חומר כדי להתחיל ללמוד." : "הפרופיל מוכן לשלב הבא."}</h3>
            <p>
              בחר את סוג החומר שיש לך. אין צורך להבין קטלוגים, manifests או הגדרות מודל.
            </p>
          </div>
          <button type="button" onClick={() => openView("training")}>
            התחל לבנות פרופיל
          </button>
        </section>
      )}

      <section className={styles.learningSection}>
        <div className={styles.sectionHead}>
          <div>
            <span className={styles.sectionLabel}>דרכי למידה</span>
            <h2>איך אפשר ללמד את הפרופיל?</h2>
          </div>
          <p>כל מסלול נשמר ונמדד בנפרד. אפשר להוסיף מסלול נוסף בהמשך.</p>
        </div>

        <div className={styles.tracks}>
          <LearningTrack
            eyebrow="RAW"
            title="RAW + עריכות Lightroom"
            copy="מתאים לצלם שעובד RAW ושומר את העריכות שלו ב-Lightroom/XMP."
            badge="זמין לניסוי"
            onClick={() => openView("training")}
          />
          <LearningTrack
            eyebrow="JPEG"
            title="JPEG לפני + אחרי"
            copy="מקור JPEG מול JPEG סופי שכבר ערכת. ProGrapher לומד מההבדל ביניהם."
            badge="זמין לניסוי"
            onClick={() => openView("training")}
          />
          <LearningTrack
            eyebrow="JPEG + LR"
            title="JPEG + Lightroom Catalog"
            copy="למידה ישירה מה-JPEG ומהחלטות העריכה שנשמרו ב-Lightroom."
            badge="בתכנון"
            disabled
          />
        </div>
      </section>

      <details className={styles.advanced}>
        <summary>
          <span>
            <strong>הגדרות מתקדמות</strong>
            <small>Lightroom, מקור עריכות והעדפות סגנון</small>
          </span>
          <span className={styles.chevron} aria-hidden="true">⌄</span>
        </summary>

        <div className={styles.advancedBody}>
          <section className={styles.advancedCard}>
            <div className={styles.advancedHead}>
              <div>
                <span className={styles.sectionLabel}>Lightroom</span>
                <h3>{overview?.lightroom.detected ? "Lightroom Classic זוהה" : "Lightroom Classic לא זוהה"}</h3>
              </div>
              <span className={overview?.lightroom.detected ? styles.goodBadge : styles.neutralBadge}>
                {overview?.lightroom.detected ? "מחובר" : "לא זוהה"}
              </span>
            </div>
            <p className={styles.techPath}>
              {overview?.lightroom.application_path ?? "לא נמצא נתיב התקנה."}
            </p>
            <div className={styles.advancedActions}>
              <button type="button" onClick={() => void chooseCatalog()} disabled={busy}>
                {overview?.selected_catalog ? "החלף קטלוג Lightroom" : "בחר קטלוג Lightroom"}
              </button>
              <button type="button" onClick={() => void chooseEditsFolder()} disabled={busy}>
                {overview?.selected_edits_folder ? "החלף תיקיית עריכות" : "בחר תיקיית עריכות / XMP"}
              </button>
            </div>
          </section>

          <section className={styles.advancedCard}>
            <div className={styles.advancedHead}>
              <div>
                <span className={styles.sectionLabel}>סגנון</span>
                <h3>פרטים אופציונליים</h3>
              </div>
            </div>

            <div className={styles.formGrid}>
              <label>
                <span>שם הסגנון</span>
                <input
                  value={styleName}
                  onChange={(event) => setStyleName(event.target.value)}
                  placeholder="לדוגמה: טבעי וחם"
                />
              </label>

              <div className={styles.fieldButton}>
                <span>פריסט Lightroom</span>
                <button type="button" onClick={() => void choosePreset()} disabled={busy}>
                  {presetPath ? "החלף פריסט" : "בחר פריסט"}
                </button>
              </div>
            </div>

            <div className={styles.profileModes}>
              <label>
                <input
                  type="radio"
                  name="profile-mode"
                  checked={profileMode === "from_source"}
                  onChange={() => setProfileMode("from_source")}
                />
                <span>קבע פרופיל צבע מתוך החומר</span>
              </label>
              <label>
                <input
                  type="radio"
                  name="profile-mode"
                  checked={profileMode === "explicit"}
                  onChange={() => setProfileMode("explicit")}
                />
                <span>הגדר פרופיל צבע ידנית</span>
              </label>
              {profileMode === "explicit" ? (
                <input
                  value={cameraProfile}
                  onChange={(event) => setCameraProfile(event.target.value)}
                  placeholder="לדוגמה: Adobe Color"
                />
              ) : null}
            </div>

            <button className={styles.saveAdvanced} type="button" onClick={() => void saveStyle()} disabled={busy}>
              {busy ? "שומר…" : "שמור הגדרות"}
            </button>
          </section>
        </div>
      </details>
    </section>
  );
}
