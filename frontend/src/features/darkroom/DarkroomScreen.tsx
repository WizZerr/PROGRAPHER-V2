"use client";

import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  exportRecipes,
  getReviewSheet,
  type ReviewFile,
} from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import styles from "@/features/testing/testing.module.css";

function formatRecipe(
  exposure: number | null | undefined,
  temperature: number | null | undefined,
  tint: number | null | undefined,
) {
  if (exposure == null || temperature == null || tint == null) return "חסר";
  return `${exposure} / ${temperature} K / ${tint}`;
}

export default function DarkroomScreen() {
  const { selection, outputDir, setOutputDir } = useTestingNav();
  const [file, setFile] = useState<ReviewFile | null>(null);
  const [exposure, setExposure] = useState(0);
  const [temperature, setTemperature] = useState(5500);
  const [tint, setTint] = useState(0);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!selection) {
      setFile(null);
      setReady(false);
      return;
    }

    void getReviewSheet(selection.eventId)
      .then((sheet) => {
        const match = sheet.files.find(
          (item) => item.fingerprint === selection.fingerprint,
        );
        setFile(match ?? null);
        const source = match?.saved_review ?? match?.suggested;
        if (
          source?.exposure != null &&
          source.temperature != null &&
          source.tint != null
        ) {
          setExposure(source.exposure);
          setTemperature(source.temperature);
          setTint(source.tint);
          setReady(true);
        } else {
          setReady(false);
        }
        setError("");
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת התמונה נכשלה.");
      });
  }, [selection]);

  async function chooseOutput() {
    const selected = await open({
      directory: true,
      multiple: false,
      title: "בחר תיקיית ייצוא XMP",
    });
    if (!selected || Array.isArray(selected)) return;
    setOutputDir(selected);
  }

  async function save(decision: "approved" | "corrected") {
    if (!selection || !file || !outputDir) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await exportRecipes({
        event_id: selection.eventId,
        output_dir: outputDir,
        items: [
          {
            fingerprint: file.fingerprint,
            exposure,
            temperature,
            tint,
            decision,
          },
        ],
      });
      const item = result.files[0];
      if (item?.status === "written") {
        setMessage(result.note);
      } else {
        setError(item?.reason || "הייצוא לא נכתב.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הייצוא נכשל.");
    } finally {
      setBusy(false);
    }
  }

  if (!selection || !file) {
    return (
      <div className={styles.screen}>
        <section className={styles.hero}>
          <h2>חדר עריכה</h2>
          <p>פותחים תמונה מהגלריה. כאן מאשרים או מתקנים את המתכון, ואז מייצאים XMP ל-Lightroom.</p>
        </section>
      </div>
    );
  }

  const photographer = file.photographer;
  const changed =
    photographer?.exposure !== exposure ||
    photographer?.temperature !== temperature ||
    photographer?.tint !== tint;

  return (
    <div className={styles.screen}>
      <section className={styles.workspace}>
        <div className={styles.stage}>
          <p className={styles.note}>בדיקה מול Lightroom</p>
          <h2 className={styles.ltr}>{file.filename}</h2>
          <p className={styles.note}>
            אין כאן רינדור RAW. המספרים הם המתכון שייכתב ל-XMP. את הצבע הסופי
            בודקים אחרי פתיחה ב-Lightroom Classic.
          </p>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <span>עריכת הצלם</span>
              <strong className={styles.ltr}>
                {formatRecipe(
                  photographer?.exposure,
                  photographer?.temperature,
                  photographer?.tint,
                )}
              </strong>
            </div>
            <div className={styles.metric}>
              <span>בסיס הבדיקה</span>
              <strong className={styles.ltr}>
                {formatRecipe(
                  file.baseline?.exposure,
                  file.baseline?.temperature,
                  file.baseline?.tint,
                )}
              </strong>
            </div>
          </div>
          {message && <p className={styles.ok}>{message}</p>}
          {error && <p className={styles.error}>{error}</p>}
        </div>

        <aside className={styles.controls}>
          <label className={styles.sliderBlock}>
            <span className={styles.sliderLabel}>
              חשיפה <bdi className={styles.ltr}>{exposure.toFixed(2)}</bdi>
            </span>
            <input
              type="range"
              min={-5}
              max={5}
              step={0.01}
              value={exposure}
              disabled={!ready}
              onChange={(event) => setExposure(Number(event.target.value))}
            />
          </label>
          <label className={styles.sliderBlock}>
            <span className={styles.sliderLabel}>
              טמפרטורה <bdi className={styles.ltr}>{temperature} K</bdi>
            </span>
            <input
              type="range"
              min={2000}
              max={50000}
              step={50}
              value={temperature}
              disabled={!ready}
              onChange={(event) => setTemperature(Number(event.target.value))}
            />
          </label>
          <label className={styles.sliderBlock}>
            <span className={styles.sliderLabel}>
              גוון <bdi className={styles.ltr}>{tint}</bdi>
            </span>
            <input
              type="range"
              min={-150}
              max={150}
              step={1}
              value={tint}
              disabled={!ready}
              onChange={(event) => setTint(Number(event.target.value))}
            />
          </label>

          <div className={styles.footerActions}>
            <button className={styles.secondary} type="button" onClick={() => void chooseOutput()}>
              תיקיית ייצוא
            </button>
            <p className={styles.note}>
              <bdi className={styles.ltr}>{outputDir || "עדיין לא נבחרה תיקייה"}</bdi>
            </p>
            <button
              className={styles.primary}
              type="button"
              disabled={!ready || busy || !outputDir}
              onClick={() => void save(changed ? "corrected" : "approved")}
            >
              {busy ? "כותב XMP…" : "ייצא XMP לבדיקה"}
            </button>
          </div>
        </aside>
      </section>
    </div>
  );
}
