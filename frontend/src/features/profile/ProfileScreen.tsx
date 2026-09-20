"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  continueWithoutEditSource,
  getPhotographerSetup,
  saveStylePreferences,
  selectEditsFolder,
  selectLightroomCatalog,
  type PhotographerSetupOverview,
  type PhotographerSetupStatus,
} from "./profile.api";
import styles from "./ProfileScreen.module.css";

const STATUS_LABELS: Record<PhotographerSetupStatus, string> = {
  no_profile: "אין פרופיל",
  data_review: "הנתונים בבדיקה",
  training: "באימון",
  needs_more_data: "נדרש חומר נוסף",
  experimental: "פרופיל ניסויי",
  evaluated: "פרופיל שעבר הערכה",
};

export default function ProfileScreen() {
  const [overview, setOverview] =
    useState<PhotographerSetupOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [styleName, setStyleName] = useState("");
  const [presetPath, setPresetPath] = useState<string | null>(null);
  const [profileMode, setProfileMode] =
    useState<"from_source" | "explicit">("from_source");
  const [cameraProfile, setCameraProfile] = useState("");

  const applyOverview = useCallback(
    (value: PhotographerSetupOverview) => {
      setOverview(value);
      setStyleName(value.setup.style_name ?? "");
      setPresetPath(value.setup.preset_path);
      setProfileMode(value.setup.color_profile_mode);
      setCameraProfile(value.setup.camera_profile ?? "");
    },
    [],
  );

  const refresh = useCallback(async () => {
    setError("");
    try {
      applyOverview(await getPhotographerSetup());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לטעון את הגדרת הצלם.",
      );
    }
  }, [applyOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function chooseCatalog() {
    setError("");
    setSaved("");

    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר קטלוג Lightroom",
      filters: [{ name: "Lightroom Catalog", extensions: ["lrcat"] }],
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      applyOverview(await selectLightroomCatalog(selected));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקרוא את קטלוג Lightroom.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function chooseEditsFolder() {
    setError("");
    setSaved("");

    const selected = await open({
      multiple: false,
      directory: true,
      title: "בחר תיקיית עריכות / XMP",
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      applyOverview(await selectEditsFolder(selected));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקרוא את תיקיית העריכות.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function noExistingSource() {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      applyOverview(await continueWithoutEditSource());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לעדכן את מצב הפרופיל.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function choosePreset() {
    setError("");
    setSaved("");

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
        camera_profile:
          profileMode === "explicit"
            ? cameraProfile.trim() || null
            : null,
      });

      applyOverview(result);
      setSaved("הגדרות הסגנון נשמרו.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לשמור את הגדרות הסגנון.",
      );
    } finally {
      setBusy(false);
    }
  }

  const setup = overview?.setup;
  const catalog = overview?.selected_catalog;
  const editsFolder = overview?.selected_edits_folder;

  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>PHOTOGRAPHER SETUP</span>
        <h2>הפרופיל שלי</h2>
        <p>
          הפרופיל האישי ייווצר בתוך ProGrapher מנתוני עריכה אמיתיים שלך.
          בחירת סגנון כאן מתארת את היעד — היא אינה יוצרת מודל מוכן.
        </p>
      </div>

      {error ? <div className={styles.error}>{error}</div> : null}
      {saved ? <div className={styles.success}>{saved}</div> : null}

      <div className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.cardHeader}>
            <div>
              <span className={styles.label}>LIGHTROOM CLASSIC</span>
              <h3>זיהוי Lightroom</h3>
            </div>
            <span
              className={
                overview?.lightroom.detected
                  ? styles.okBadge
                  : styles.warningBadge
              }
            >
              {overview?.lightroom.detected ? "זוהה" : "לא זוהה"}
            </span>
          </div>

          <p className={styles.path}>
            {overview?.lightroom.application_path ??
              "ProGrapher לא מצא התקנת Lightroom Classic אוטומטית."}
          </p>
        </article>

        <article className={styles.card}>
          <div className={styles.cardHeader}>
            <div>
              <span className={styles.label}>PROFILE STATUS</span>
              <h3>מצב הפרופיל</h3>
            </div>
            <span className={styles.statusBadge}>
              {setup ? STATUS_LABELS[setup.status] : "טוען..."}
            </span>
          </div>

          <p>
            מצב Ready לא יינתן רק בגלל בחירת פריסט או סיום אימון. קודם
            נצטרך נתונים תקינים והערכת איכות.
          </p>
        </article>
      </div>

      <article className={styles.sourceCard}>
        <span className={styles.label}>EDIT SOURCE</span>
        <h3>מאיפה נלמד את הסגנון שלך?</h3>

        <div className={styles.sourceOptions}>
          <button
            type="button"
            className={styles.sourceOption}
            onClick={() => void chooseCatalog()}
            disabled={busy}
          >
            <strong>יש לי קטלוג Lightroom</strong>
            <span>בחירת קובץ .lrcat קיים</span>
          </button>

          <button
            type="button"
            className={styles.sourceOption}
            onClick={() => void chooseEditsFolder()}
            disabled={busy}
          >
            <strong>יש לי תיקיית עריכות / XMP</strong>
            <span>נשתמש רק בחומר שתבחר במפורש</span>
          </button>

          <button
            type="button"
            className={styles.sourceOption}
            onClick={() => void noExistingSource()}
            disabled={busy}
          >
            <strong>אין לי חומר ערוך כרגע</strong>
            <span>ממשיכים בלי פרופיל אישי בשלב הזה</span>
          </button>
        </div>

        {catalog ? (
          <div className={styles.details}>
            <div className={styles.pathBox}>{catalog.path}</div>
            <div className={styles.info}>{catalog.note}</div>
          </div>
        ) : null}

        {editsFolder ? (
          <div className={styles.details}>
            <div className={styles.pathBox}>{editsFolder.path}</div>
            <div className={styles.info}>{editsFolder.note}</div>
          </div>
        ) : null}

        {setup?.source_type === "none" ? (
          <div className={styles.warning}>
            אין כרגע מקור לעריכות אישיות. זה לא חוסם את התוכנה — רק אומר
            שעדיין אי אפשר לאמן פרופיל אישי מהסגנון שלך.
          </div>
        ) : null}
      </article>

      <article className={styles.styleCard}>
        <span className={styles.label}>STYLE TARGET</span>
        <h3>איך נזהה את הסגנון שלך?</h3>
        <p className={styles.sourceIntro}>
          השדות כאן אופציונליים. הם מתעדים את כיוון העבודה ולא מחליפים
          נתוני עריכה אמיתיים.
        </p>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>שם הסגנון</span>
            <input
              value={styleName}
              onChange={(event) => setStyleName(event.target.value)}
              placeholder="לדוגמה: טבעי, חם, נקי"
            />
          </label>

          <div className={styles.field}>
            <span>פריסט Lightroom</span>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => void choosePreset()}
              disabled={busy}
            >
              {presetPath ? "החלפת פריסט" : "בחירת פריסט XMP"}
            </button>
            <small className={styles.pathHint}>
              {presetPath ??
                `${overview?.discovered_presets.length ?? 0} פריסטים אותרו אוטומטית`}
            </small>
          </div>
        </div>

        <div className={styles.profileChoice}>
          <strong>פרופיל צבע</strong>

          <label>
            <input
              type="radio"
              name="profile-mode"
              checked={profileMode === "from_source"}
              onChange={() => setProfileMode("from_source")}
            />
            <span>
              ייקבע מתוך חומר העריכה המאומת
              <small>ברירת המחדל הבטוחה כשאין פרופיל ידוע מראש</small>
            </span>
          </label>

          <label>
            <input
              type="radio"
              name="profile-mode"
              checked={profileMode === "explicit"}
              onChange={() => setProfileMode("explicit")}
            />
            <span>
              יש לי דרישת פרופיל צבע מפורשת
              <small>נשמור את השם, אך נבדוק התאמה למצלמה לפני שימוש</small>
            </span>
          </label>

          {profileMode === "explicit" ? (
            <input
              className={styles.profileInput}
              value={cameraProfile}
              onChange={(event) => setCameraProfile(event.target.value)}
              placeholder="לדוגמה: Adobe Color"
            />
          ) : null}
        </div>

        <button
          type="button"
          className={styles.primaryButton}
          onClick={() => void saveStyle()}
          disabled={busy}
        >
          שמירת הגדרות הסגנון
        </button>
      </article>

      <article className={styles.readinessCard}>
        <span className={styles.label}>READINESS</span>
        <h3>מה עדיין חסר לפרופיל אישי?</h3>

        <ul>
          {(overview?.readiness_reasons ?? []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </article>
    </section>
  );
}
