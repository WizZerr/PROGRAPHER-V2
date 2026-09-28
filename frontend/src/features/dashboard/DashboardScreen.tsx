"use client";

import { useEffect, useState } from "react";
import StatusBadge from "@/components/common/StatusBadge";
import { getRuntimeInfo } from "@/features/dashboard/dashboard.api";
import { listEvents, type EventSummary } from "@/features/events/events.api";
import { getTestingProfile, type TestingProfile } from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import { getEngineInfo } from "@/lib/runtime";
import { detectDesktopPlatform } from "@/lib/platform";
import type { EngineInfo, RuntimeInfo } from "@/types/engine";
import styles from "./DashboardScreen.module.css";

type ConnectionState = "checking" | "connected" | "error";

export default function DashboardScreen() {
  const openView = useWorkspaceNav();
  const { setGalleryEventId, openGallery } = useTestingNav();
  const [state, setState] = useState<ConnectionState>("checking");
  const [engine, setEngine] = useState<EngineInfo | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [platform, setPlatform] = useState("לא ידוע");
  const [error, setError] = useState("");
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [profile, setProfile] = useState<TestingProfile | null>(null);

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
        const [engineInfo, runtimeInfo, eventList, testingProfile] = await Promise.all([
          getEngineInfo(),
          getRuntimeInfo(),
          listEvents().catch(() => [] as EventSummary[]),
          getTestingProfile().catch(() => null),
        ]);

        if (cancelled) return;

        setEngine(engineInfo);
        setRuntime(runtimeInfo);
        setEvents(eventList);
        setProfile(testingProfile);
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

  const latest = events[0] ?? null;

  function openLatest() {
    if (!latest) {
      openView("events");
      return;
    }
    setGalleryEventId(latest.id);
    openGallery();
  }

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.kicker}>סביבת העבודה</span>
          <h2>מוכנים להתחיל.</h2>
          <p>
            סורקים אירוע, בונים פרופיל RAW או JPEG, וסוקרים בגלריה. רק פרופיל RAW מייצא XMP.
            קובצי המקור נשארים במקומם.
          </p>
        </div>
        <div className={styles.heroStatus}>
          {state === "checking" && <StatusBadge tone="warning">מתחבר למנוע…</StatusBadge>}
          {state === "connected" && <StatusBadge tone="success">המנוע מחובר</StatusBadge>}
          {state === "error" && <StatusBadge tone="danger">המנוע אינו זמין</StatusBadge>}
        </div>
      </section>

      <div className={styles.actions}>
        <button className={styles.primary} type="button" onClick={() => openView("events")}>
          אירוע חדש
        </button>
        <button className={styles.secondary} type="button" onClick={openLatest}>
          פתח אירוע אחרון
        </button>
        <button className={styles.secondary} type="button" onClick={() => openView("gallery")}>
          עבור לגלריה
        </button>
      </div>

      <section className={styles.split}>
        <div>
          <div className={styles.sectionHeader}>
            <h3>אירועים אחרונים</h3>
            <button className={styles.textButton} type="button" onClick={() => openView("events")}>
              כל האירועים
            </button>
          </div>
          {events.length === 0 ? (
            <p className={styles.empty}>עדיין אין אירועים בספרייה.</p>
          ) : (
            <div className={styles.eventList}>
              {events.slice(0, 4).map((event) => (
                <button
                  key={event.id}
                  type="button"
                  className={styles.eventRow}
                  onClick={() => {
                    setGalleryEventId(event.id);
                    openGallery();
                  }}
                >
                  <strong>{event.name}</strong>
                  <span>
                    <bdi>{event.total_files}</bdi> תמונות · RAW <bdi>{event.raw_files}</bdi> · JPEG <bdi>{event.jpeg_files}</bdi>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className={styles.sectionHeader}>
            <h3>פרופיל</h3>
          </div>
          <article className={styles.card}>
            <span className={styles.cardLabel}>מסלול פעיל</span>
            <strong>{profile ? (profile.learning_source === "jpeg" ? "JPEG" : "RAW") : "לא הוגדר"}</strong>
            <small>{profile ? profile.event_label : "הלמידה מחכה לחומר של הצלם"}</small>
          </article>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="system-title">
        <div className={styles.sectionHeader}>
          <h3 id="system-title">מצב מקומי</h3>
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
            <small>עיבוד מקומי</small>
          </article>
          <article className={styles.card}>
            <span className={styles.cardLabel}>מחשב</span>
            <strong>{platform}</strong>
            <small>Windows / macOS</small>
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
