"use client";

import { useEffect, useState } from "react";
import StatusBadge from "@/components/common/StatusBadge";
import { getRuntimeInfo } from "@/features/dashboard/dashboard.api";
import { getEngineInfo } from "@/lib/runtime";
import { detectDesktopPlatform } from "@/lib/platform";
import type { EngineInfo, RuntimeInfo } from "@/types/engine";
import styles from "./DashboardScreen.module.css";

type ConnectionState = "checking" | "connected" | "error";

export default function DashboardScreen() {
  const [state, setState] = useState<ConnectionState>("checking");
  const [engine, setEngine] = useState<EngineInfo | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [platform, setPlatform] = useState("לא ידוע");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      const detected = detectDesktopPlatform();
      setPlatform(
        detected === "windows"
          ? "Windows"
          : detected === "macos"
            ? "macOS"
            : detected,
      );

      try {
        const [engineInfo, runtimeInfo] = await Promise.all([
          getEngineInfo(),
          getRuntimeInfo(),
        ]);

        if (cancelled) return;

        setEngine(engineInfo);
        setRuntime(runtimeInfo);
        setState("connected");
      } catch (err) {
        if (cancelled) return;

        setError(err instanceof Error ? err.message : String(err));
        setState("error");
      }
    }

    void connect();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.kicker}>סביבת העבודה</span>
          <h2>מוכנים להתחיל.</h2>
          <p>
            סדר הבדיקה: סורקים תיקיית אירוע, בונים פרופיל RAW או פרופיל JPEG במעבדה,
            סוקרים בגלריה. רק פרופיל RAW מייצא XMP ל-Lightroom. המקור נשאר ללא שינוי.
          </p>
        </div>

        <div className={styles.heroStatus}>
          {state === "checking" && (
            <StatusBadge tone="warning">מתחבר למנוע…</StatusBadge>
          )}
          {state === "connected" && (
            <StatusBadge tone="success">המנוע מחובר</StatusBadge>
          )}
          {state === "error" && (
            <StatusBadge tone="danger">המנוע אינו זמין</StatusBadge>
          )}
        </div>
      </section>

      <section className={styles.section} aria-labelledby="system-title">
        <div className={styles.sectionHeader}>
          <div>
            <span className={styles.sectionEyebrow}>מערכת</span>
            <h3 id="system-title">מצב ProGrapher</h3>
          </div>
          <span className={styles.sectionHint}>מידע מקומי</span>
        </div>

        <div className={styles.grid}>
          <article className={styles.card}>
            <span className={styles.cardLabel}>מנוע</span>
            <strong>{runtime?.service ?? "—"}</strong>
            <small>גרסה {runtime?.version ?? "—"}</small>
          </article>

          <article className={styles.card}>
            <span className={styles.cardLabel}>חיבור</span>
            <strong>{engine ? `127.0.0.1:${engine.port}` : "—"}</strong>
            <small>Loopback מקומי לאותה הפעלה</small>
          </article>

          <article className={styles.card}>
            <span className={styles.cardLabel}>מחשב</span>
            <strong>{platform}</strong>
            <small>זוהה אוטומטית</small>
          </article>
        </div>
      </section>

      {state === "error" && (
        <section className={styles.errorPanel}>
          <span>פרטי חיבור</span>
          <pre>{error}</pre>
        </section>
      )}
    </div>
  );
}
