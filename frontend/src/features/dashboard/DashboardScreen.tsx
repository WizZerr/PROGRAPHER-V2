"use client";

import { useEffect, useState } from "react";
import StatusBadge from "@/components/common/StatusBadge";
import { getRuntimeInfo } from "@/features/dashboard/dashboard.api";
import EventCover from "@/features/events/EventCover";
import { listEvents, type EventSummary } from "@/features/events/events.api";
import { getTestingProfile, type TestingProfile } from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import { getEngineInfo } from "@/lib/runtime";
import { detectDesktopPlatform } from "@/lib/platform";
import type { EngineInfo, RuntimeInfo } from "@/types/engine";
import styles from "./DashboardScreen.module.css";

type ConnectionState = "checking" | "connected" | "error";

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

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
        detected === "windows" ? "Windows" : detected === "macos" ? "macOS" : detected,
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
  const hero = latest;

  function openEvent(eventId: string) {
    setGalleryEventId(eventId);
    openGallery();
  }

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroVisual}>
          {hero ? <EventCover eventId={hero.id} label={hero.name} /> : <div className={styles.heroFallback} />}
        </div>
        <div className={styles.heroCopy}>
          <div className={styles.heroStatus}>
            {state === "checking" && <StatusBadge tone="warning">מתחבר למנוע…</StatusBadge>}
            {state === "connected" && <StatusBadge tone="success">המנוע מחובר</StatusBadge>}
            {state === "error" && <StatusBadge tone="danger">המנוע אינו זמין</StatusBadge>}
          </div>
          <span className={styles.kicker}>סביבת העבודה</span>
          <h2>מוכנים להתחיל.</h2>
          <p>
            {hero
              ? `${hero.name} · ${hero.total_files.toLocaleString("he-IL")} תמונות במחשב שלך.`
              : "סורקים אירוע, בונים פרופיל RAW או JPEG, וסוקרים בגלריה. המקור נשאר במקומו."}
          </p>
          <div className={styles.actions}>
            <button className={styles.primary} type="button" onClick={() => openView("events")}>
              + אירוע חדש
            </button>
            <button className={styles.secondary} type="button" onClick={() => (latest ? openEvent(latest.id) : openView("events"))}>
              פתח אירוע אחרון
            </button>
            <button className={styles.secondary} type="button" onClick={() => openView("gallery")}>
              עבור לגלריה
            </button>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionHeader}>
          <h3>אירועים אחרונים</h3>
          <button className={styles.textButton} type="button" onClick={() => openView("events")}>
            כל האירועים
          </button>
        </div>
        {events.length === 0 ? (
          <p className={styles.empty}>עדיין אין אירועים. האירוע הראשון נוצר מתיקייה מקומית.</p>
        ) : (
          <div className={styles.eventStrip}>
            {events.slice(0, 4).map((event) => (
              <button key={event.id} type="button" className={styles.eventCard} onClick={() => openEvent(event.id)}>
                <div className={styles.eventCover}>
                  <EventCover eventId={event.id} label={event.name} />
                </div>
                <strong>{event.name}</strong>
                <span>{formatDate(event.updated_at || event.created_at)}</span>
                <span>
                  <bdi>{event.total_files.toLocaleString("he-IL")}</bdi> תמונות · RAW <bdi>{event.raw_files}</bdi>
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className={styles.system}>
        <article className={styles.card}>
          <span>הפרופיל הפעיל</span>
          <strong>{profile ? (profile.learning_source === "jpeg" ? "JPEG" : "RAW") : "לא הוגדר"}</strong>
          <small>{profile ? `${profile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים` : "הלמידה מחכה לחומר"}</small>
        </article>
        <article className={styles.card}>
          <span>עיבוד מקומי</span>
          <strong>{engine ? `127.0.0.1:${engine.port}` : "—"}</strong>
          <small>{runtime?.service ?? "המנוע עדיין לא זמין"}</small>
        </article>
        <article className={styles.card}>
          <span>מערכת</span>
          <strong>{platform}</strong>
          <small>גרסה {runtime?.version ?? "—"}</small>
        </article>
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
