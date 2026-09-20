"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { getRuntimeInfo } from "@/features/dashboard/dashboard.api";
import { getEngineInfo } from "@/lib/runtime";
import {
  detectDesktopPlatform,
  primaryShortcutLabel,
  type DesktopPlatform,
} from "@/lib/platform";
import type { EngineInfo, RuntimeInfo } from "@/types/engine";
import styles from "./DashboardScreen.module.css";

type ConnectionState = "checking" | "connected" | "error";

export default function DashboardScreen() {
  const [state, setState] = useState<ConnectionState>("checking");
  const [engine, setEngine] = useState<EngineInfo | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [platform, setPlatform] = useState<DesktopPlatform>("unknown");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      setPlatform(detectDesktopPlatform());

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
    <AppShell>
      <section className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>PHASE 1 FOUNDATION</span>
          <h2>ProGrapher Desktop</h2>
          <p>
            Frontend modules, runtime bridge and API client are now separated.
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
          {state === "checking" && "Connecting…"}
          {state === "connected" && "Engine connected"}
          {state === "error" && "Engine unavailable"}
        </div>
      </section>

      <section className={styles.grid}>
        <article className={styles.card}>
          <span>Engine</span>
          <strong>{runtime?.service ?? "—"}</strong>
          <small>Version {runtime?.version ?? "—"}</small>
        </article>

        <article className={styles.card}>
          <span>Runtime</span>
          <strong>{engine ? `127.0.0.1:${engine.port}` : "—"}</strong>
          <small>Authenticated local session</small>
        </article>

        <article className={styles.card}>
          <span>Platform</span>
          <strong>{platform}</strong>
          <small>{primaryShortcutLabel(platform)} shortcut profile</small>
        </article>
      </section>

      {state === "error" && <pre className={styles.error}>{error}</pre>}
    </AppShell>
  );
}
