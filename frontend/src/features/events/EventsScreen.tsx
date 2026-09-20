"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  getEventAvailability,
  listEvents,
  openEventFolder,
  relinkEvent,
  type EventAvailability,
  type EventOpenResponse,
  type EventSummary,
} from "./events.api";
import styles from "./EventsScreen.module.css";

export default function EventsScreen() {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [availability, setAvailability] = useState<
    Record<string, EventAvailability>
  >({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<EventOpenResponse | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  const refreshAvailability = useCallback(async (items: EventSummary[]) => {
    const pairs = await Promise.all(
      items.map(async (event) => {
        try {
          const result = await getEventAvailability(event.id);
          return [event.id, result] as const;
        } catch {
          return [event.id, null] as const;
        }
      }),
    );

    const next: Record<string, EventAvailability> = {};
    for (const [id, result] of pairs) {
      if (result) next[id] = result;
    }
    setAvailability(next);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const result = await listEvents();
      setEvents(result);
      await refreshAvailability(result);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לטעון את רשימת האירועים.",
      );
    }
  }, [refreshAvailability]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function chooseFolder() {
    setError("");
    setMessage("");
    setNotice(null);

    const selected = await open({
      directory: true,
      multiple: false,
      title: "בחר תיקיית אירוע",
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      const result = await openEventFolder(selected);
      setNotice(result);
      await refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "קליטת תיקיית האירוע נכשלה.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function relink(event: EventSummary) {
    setError("");
    setMessage("");
    setNotice(null);

    const selected = await open({
      directory: true,
      multiple: false,
      title: `אתר מחדש את תיקיית האירוע ${event.name}`,
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    try {
      const result = await relinkEvent(event.id, selected);
      setMessage(
        `האירוע "${result.event.name}" קושר מחדש. נמצאו ${result.matched_files} קבצים מוכרים.`,
      );
      await refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקשר מחדש את האירוע לתיקייה שנבחרה.",
      );
    } finally {
      setBusy(false);
    }
  }

  function eventName(name: string): React.ReactNode {
    return (
      <span className={styles.eventName} dir="rtl">
        &quot;{name}&quot;
      </span>
    );
  }

  function noticeClassName(result: EventOpenResponse): string {
    if (result.result === "existing") return styles.warning;
    if (result.result === "updated") return styles.info;
    return styles.success;
  }

  function noticeContent(result: EventOpenResponse): React.ReactNode {
    if (result.result === "existing") {
      return (
        <>
          התיקייה כבר משויכת לאירוע {eventName(result.event.name)}. לא נוצר
          אירוע נוסף.
        </>
      );
    }

    if (result.result === "updated") {
      return (
        <>
          האירוע {eventName(result.event.name)} עודכן. נוספו{" "}
          {result.new_files_added} קבצים חדשים.
        </>
      );
    }

    return (
      <>
        האירוע נקלט. קובצי <bdi dir="ltr">RAW</bdi>: {result.event.raw_files}
        {result.duplicate_files_ignored > 0
          ? ` · קבצים כפולים שלא נוספו: ${result.duplicate_files_ignored}`
          : ""}
      </>
    );
  }

  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>EVENTS</span>
        <div className={styles.heroRow}>
          <div>
            <h2>אירועים</h2>
            <p>
              בחר תיקיית צילום מהמחשב. ProGrapher קורא את המקורות מהמיקום
              שלהם ואינו מעתיק או משנה את קובצי ה־RAW.
            </p>
          </div>

          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => void chooseFolder()}
            disabled={busy}
          >
            {busy ? "סורק תיקייה..." : "בחירת תיקיית אירוע"}
          </button>
        </div>
      </div>

      {notice ? (
        <div className={noticeClassName(notice)}>
          {noticeContent(notice)}
        </div>
      ) : null}

      {message ? <div className={styles.info}>{message}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}

      <div className={styles.sectionHeader}>
        <div>
          <h3>האירועים שלי</h3>
          <p>האירועים נשמרים מקומית ויחזרו גם לאחר סגירת ProGrapher.</p>
        </div>
        <span className={styles.count}>{events.length}</span>
      </div>

      {events.length === 0 ? (
        <div className={styles.empty}>
          עדיין אין אירועים. בחר תיקיית RAW כדי ליצור את האירוע הראשון.
        </div>
      ) : (
        <div className={styles.grid}>
          {events.map((event) => {
            const status = availability[event.id];
            const unavailable =
              status && (!status.root_exists || status.missing_files > 0);

            return (
              <article key={event.id} className={styles.card}>
                <div className={styles.cardTop}>
                  <div>
                    <h4>{event.name}</h4>
                    <p className={styles.path} title={event.root_path}>
                      {event.root_path}
                    </p>
                  </div>

                  <span
                    className={unavailable ? styles.missing : styles.ready}
                  >
                    {unavailable ? "מקור חסר" : "מקומי"}
                  </span>
                </div>

                {unavailable ? (
                  <div className={styles.missingPanel}>
                    <span>
                      {!status.root_exists
                        ? "תיקיית המקור אינה זמינה."
                        : `${status.missing_files} קבצי מקור אינם זמינים.`}
                    </span>
                    <button
                      type="button"
                      onClick={() => void relink(event)}
                      disabled={busy}
                    >
                      איתור מחדש
                    </button>
                  </div>
                ) : null}

                <div className={styles.stats}>
                  <div>
                    <strong>{event.raw_files}</strong>
                    <span>RAW</span>
                  </div>
                  <div>
                    <strong>{event.rendered_files}</strong>
                    <span>JPG / TIFF</span>
                  </div>
                  <div>
                    <strong>{event.total_files}</strong>
                    <span>סה״כ</span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
