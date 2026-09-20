"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";
import {
  getEngineInfo,
  getRuntimeInfo,
  type EngineInfo,
  type RuntimeInfo,
} from "@/lib/engine";

type ConnectionState = "checking" | "connected" | "error";

export default function Home() {
  const [state, setState] = useState<ConnectionState>("checking");
  const [engine, setEngine] = useState<EngineInfo | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      try {
        const engineInfo = await getEngineInfo();
        const runtimeInfo = await getRuntimeInfo();

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
    <main className={styles.page}>
      <section className={styles.card}>
        <div className={styles.eyebrow}>PROGRAPHER V2</div>
        <h1>Desktop Engine Bridge</h1>

        <div className={styles.statusRow}>
          <span
            className={`${styles.dot} ${
              state === "connected"
                ? styles.connected
                : state === "error"
                  ? styles.failed
                  : styles.checking
            }`}
          />
          <span>
            {state === "checking" && "Connecting to ProGrapher Engine…"}
            {state === "connected" && "ProGrapher Engine connected"}
            {state === "error" && "Engine connection failed"}
          </span>
        </div>

        {state === "connected" && engine && runtime && (
          <div className={styles.details}>
            <div>
              <span>Service</span>
              <strong>{runtime.service}</strong>
            </div>
            <div>
              <span>Version</span>
              <strong>{runtime.version}</strong>
            </div>
            <div>
              <span>Runtime port</span>
              <strong>{engine.port}</strong>
            </div>
            <div>
              <span>Security</span>
              <strong>Authenticated local session</strong>
            </div>
          </div>
        )}

        {state === "error" && (
          <pre className={styles.error}>{error}</pre>
        )}
      </section>
    </main>
  );
}
