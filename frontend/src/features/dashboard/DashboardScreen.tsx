"use client";

import { useEffect, useState } from "react";
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
    <>
      <section className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>PROGRAPHER V2</span>
          <h2>סביבת העבודה שלך</h2>
          <p>
            הממשק והמנוע המקומי מחוברים ומוכנים להמשך בניית תהליך העבודה.
          </p>
        </div>

        <div
          className={`${styles.status} ${
            state === "connected"
              ? styles.ok
              : state === "error"
                ? styles.bad
                : styles.wait
          }`}
        >
          {state === "checking" && "מתחבר למנוע…"}
          {state === "connected" && "המנוע מחובר"}
          {state === "error" && "המנוע אינו זמין"}
        </div>
      </section>

      <section className={styles.grid}>
        <article className={styles.card}>
          <span>מנוע</span>
          <strong>{runtime?.service ?? "—"}</strong>
          <small>גרסה {runtime?.version ?? "—"}</small>
        </article>

        <article className={styles.card}>
          <span>חיבור מקומי</span>
          <strong>{engine ? `127.0.0.1:${engine.port}` : "—"}</strong>
          <small>חיבור מאובטח לאותה הפעלה</small>
        </article>

        <article className={styles.card}>
          <span>מערכת הפעלה</span>
          <strong>{platform}</strong>
          <small>זוהתה אוטומטית</small>
        </article>
      </section>

      {state === "error" && <pre className={styles.error}>{error}</pre>}
    </>
  );
}
