"use client";

import { useEffect, useState } from "react";
import { useAccountIdentity } from "@/features/account/AccountIdentity";
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

type SystemGlyphKind = "profile" | "local" | "system";

function SystemGlyph({ kind }: { kind: SystemGlyphKind }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (kind === "local") {
    return (
      <svg {...common}>
        <rect x="5" y="5" width="14" height="14" rx="2.5" />
        <rect x="9" y="9" width="6" height="6" rx="1" />
        <path d="M9 2.8v2.1M15 2.8v2.1M9 19.1v2.1M15 19.1v2.1M2.8 9h2.1M2.8 15h2.1M19.1 9h2.1M19.1 15h2.1" />
      </svg>
    );
  }

  if (kind === "system") {
    return (
      <svg {...common}>
        <rect x="3.5" y="4.5" width="17" height="12" rx="2.5" />
        <path d="M8.5 20h7M12 16.5V20" />
      </svg>
    );
  }

  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 4.5v2M19.5 12h-2M12 19.5v-2M4.5 12h2" />
    </svg>
  );
}

export default function DashboardScreen() {
  const { firstNameLabel, profileOwnerLabel } = useAccountIdentity();
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
        <div className={styles.heroShade} aria-hidden="true" />

        <div className={styles.heroCopy}>
          <span className={styles.heroGreeting}>שלום, {firstNameLabel}</span>
          <h2>
            <span>סביבת העבודה</span>
            <span className={styles.heroAccent}>מוכנים להתחיל.</span>
          </h2>
          <p>כל מה שצריך לעריכה חכמה ומדויקת — כאן, במחשב שלך.</p>

          <div className={styles.actions}>
            <button className={styles.primary} type="button" onClick={() => openView("events")}>
              <span className={styles.actionIcon} aria-hidden="true">＋</span>
              אירוע חדש
            </button>
            <button className={styles.secondary} type="button" onClick={() => (latest ? openEvent(latest.id) : openView("events"))}>
              <span className={styles.actionIcon} aria-hidden="true">◷</span>
              פתח אירוע אחרון
            </button>
            <button className={styles.secondary} type="button" onClick={() => openView("gallery")}>
              <span className={styles.actionIcon} aria-hidden="true">▧</span>
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
                <div className={styles.eventBody}>
                  <strong>{event.name}</strong>
                  <div className={styles.eventMeta}>
                    <span>
                      <span className={styles.metaIcon} aria-hidden="true">□</span>
                      {formatDate(event.updated_at || event.created_at)}
                    </span>
                    <span>
                      <span className={styles.metaIcon} aria-hidden="true">▧</span>
                      <bdi>{event.total_files.toLocaleString("he-IL")}</bdi> תמונות
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className={styles.system}>
        <article className={styles.card}>
          <div className={styles.cardTopline}>
            <span className={styles.systemIcon}><SystemGlyph kind="profile" /></span>
            <span>הפרופיל של {profileOwnerLabel}</span>
          </div>
          <strong>{profile ? (profile.learning_source === "jpeg" ? "JPEG" : "RAW") : "לא הוגדר"}</strong>
          <small>{profile ? `${profile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים` : "הלמידה מחכה לחומר"}</small>
        </article>
        <article className={styles.card}>
          <div className={styles.cardTopline}>
            <span className={styles.systemIcon}><SystemGlyph kind="local" /></span>
            <span>עיבוד מקומי</span>
            <span
              className={`${styles.engineStatusDot} ${
                state === "error"
                  ? styles.engineStatusError
                  : state === "checking"
                    ? styles.engineStatusChecking
                    : ""
              }`}
              role="status"
              aria-label={
                state === "checking"
                  ? "המנוע המקומי מתחבר"
                  : state === "connected"
                    ? "המנוע המקומי מחובר"
                    : "המנוע המקומי אינו זמין"
              }
              title={
                state === "checking"
                  ? "מתחבר"
                  : state === "connected"
                    ? "מחובר"
                    : "לא זמין"
              }
            />
          </div>
          <strong>{engine ? `127.0.0.1:${engine.port}` : "—"}</strong>
          <small>{runtime?.service ?? "המנוע עדיין לא זמין"}</small>
        </article>
        <article className={styles.card}>
          <div className={styles.cardTopline}>
            <span className={styles.systemIcon}><SystemGlyph kind="system" /></span>
            <span>מערכת</span>
          </div>
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
