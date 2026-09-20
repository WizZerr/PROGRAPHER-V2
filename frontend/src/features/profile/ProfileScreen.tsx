"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  continueWithoutEditSource,
  getPhotographerSetup,
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

  const refresh = useCallback(async () => {
    setError("");
    try {
      setOverview(await getPhotographerSetup());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לטעון את הגדרת הצלם.",
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function chooseCatalog() {
    setError("");

    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר קטלוג Lightroom",
      filters: [
        {
          name: "Lightroom Catalog",
          extensions: ["lrcat"],
        },
      ],
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      setOverview(await selectLightroomCatalog(selected));
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

    const selected = await open({
      multiple: false,
      directory: true,
      title: "בחר תיקיית עריכות / XMP",
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      setOverview(await selectEditsFolder(selected));
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
    try {
      setOverview(await continueWithoutEditSource());
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
          אינך אמור להגיע עם קובץ פרופיל מוכן.
        </p>
      </div>

      {error ? <div className={styles.error}>{error}</div> : null}

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
            אם עדיין אין לך עריכות היסטוריות מתאימות, אפשר להמשיך בלי
            פרופיל אישי. בהמשך ProGrapher יבקש חומר מספיק לפני אימון אישי.
          </p>
        </article>
      </div>

      <article className={styles.sourceCard}>
        <span className={styles.label}>EDIT SOURCE</span>
        <h3>מאיפה נלמד את הסגנון שלך?</h3>
        <p className={styles.sourceIntro}>
          בחר רק אפשרות שקיימת אצלך. שום אפשרות אינה חובה כדי להמשיך
          בפיתוח ובבדיקות הטכניות.
        </p>

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
            <div className={styles.stats}>
              <div>
                <strong>
                  {catalog.catalog_photo_records?.toLocaleString() ?? "—"}
                </strong>
                <span>רשומות צילום בקטלוג</span>
              </div>
              <div>
                <strong>טרם נבדק</strong>
                <span>עריכות סופיות שניתן להתאים</span>
              </div>
            </div>
            <div className={styles.info}>{catalog.note}</div>
          </div>
        ) : null}

        {editsFolder ? (
          <div className={styles.details}>
            <div className={styles.pathBox}>{editsFolder.path}</div>
            <div className={styles.stats}>
              <div>
                <strong>{editsFolder.xmp_files.toLocaleString()}</strong>
                <span>קובצי XMP שנמצאו</span>
              </div>
              <div>
                <strong>טרם נבדק</strong>
                <span>זוגות RAW ↔ עריכה תקינים</span>
              </div>
            </div>
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
    </section>
  );
}
