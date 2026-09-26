"use client";

import { useCallback, useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useTestingNav } from "@/features/testing/TestingNav";
import {
  deleteEvent,
  getEventAvailability,
  getEventScanProgress,
  listEvents,
  relinkEvent,
  startEventScan,
  type EventAvailability,
  type EventOpenResponse,
  type EventScanProgress,
  type EventSummary,
} from "./events.api";
import styles from "./EventsScreen.module.css";

const POLL_MS = 140;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function EventsScreen() {
  const { forgetEvent, notifyEventCatalogChanged } = useTestingNav();
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [availability, setAvailability] = useState<
    Record<string, EventAvailability>
  >({});
  const [busy, setBusy] = useState(false);
  const [scan, setScan] = useState<EventScanProgress | null>(null);
  const [notice, setNotice] = useState<EventOpenResponse | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<EventSummary | null>(null);

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

  async function waitForScan(jobId: string) {
    while (true) {
      const progress = await getEventScanProgress(jobId);
      setScan(progress);

      if (progress.status === "completed") {
        if (!progress.result) {
          throw new Error("הסריקה הסתיימה ללא תוצאת אירוע.");
        }

        setNotice(progress.result);
        notifyEventCatalogChanged(progress.result.event.id);
        await refresh();
        return;
      }

      if (progress.status === "failed") {
        throw new Error(progress.error || "סריקת האירוע נכשלה.");
      }

      await sleep(POLL_MS);
    }
  }

  async function chooseFolder() {
    setError("");
    setMessage("");
    setNotice(null);
    setScan(null);

    const selected = await open({
      directory: true,
      multiple: false,
      title: "בחר תיקיית אירוע",
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);

    try {
      const started = await startEventScan(selected);
      await waitForScan(started.job_id);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "קליטת תיקיית האירוע נכשלה.",
      );
    } finally {
      setBusy(false);
      setScan(null);
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
      notifyEventCatalogChanged(result.event.id);
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

  async function removeEvent() {
    if (!deleteTarget) return;

    setBusy(true);
    setError("");
    setMessage("");
    setNotice(null);

    try {
      const removed = await deleteEvent(deleteTarget.id);
      forgetEvent(deleteTarget.id);
      setDeleteTarget(null);
      setMessage(
        `האירוע "${removed.name}" הוסר מ-ProGrapher. קובצי המקור נשארו ללא שינוי.`,
      );
      await refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן להסיר את האירוע.",
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

  function scanTitle(progress: EventScanProgress): string {
    if (progress.status === "discovering") {
      return "מאתר קבצי צילום...";
    }

    if (progress.status === "finalizing") {
      return "מסיים קליטת האירוע...";
    }

    return "סורק את האירוע...";
  }

  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>ספריית אירועים</span>
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

      {scan ? (
        <div className={styles.scanPanel}>
          <div className={styles.scanHeader}>
            <div>
              <strong>{scanTitle(scan)}</strong>
              <span>
                {scan.total_files > 0
                  ? `${scan.processed_files.toLocaleString()} / ${scan.total_files.toLocaleString()}`
                  : "מכין את רשימת הקבצים"}
              </span>
            </div>
            <bdi dir="ltr">{scan.percent}%</bdi>
          </div>
          <div
            className={styles.progressTrack}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={scan.percent}
          >
            <div
              className={styles.progressFill}
              style={{ width: `${scan.percent}%` }}
            />
          </div>
        </div>
      ) : null}

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

                  <div className={styles.cardActions}>
                    <span
                      className={unavailable ? styles.missing : styles.ready}
                    >
                      {unavailable ? "מקור חסר" : "מקומי"}
                    </span>
                    <button
                      type="button"
                      className={styles.deleteButton}
                      onClick={() => setDeleteTarget(event)}
                      disabled={busy}
                    >
                      הסר
                    </button>
                  </div>
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

      {deleteTarget ? (
        <div className={styles.modalBackdrop}>
          <div
            className={styles.deleteDialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-event-title"
          >
            <span className={styles.dialogEyebrow}>הסרת אירוע</span>
            <h3 id="delete-event-title">
              להסיר את &quot;{deleteTarget.name}&quot;?
            </h3>
            <p>
              האירוע יוסר מהספרייה המקומית של ProGrapher בלבד.
              קובצי התמונות בתיקייה המקורית לא יימחקו ולא ישתנו.
            </p>
            <div className={styles.dialogActions}>
              <button
                type="button"
                className={styles.dialogCancel}
                onClick={() => setDeleteTarget(null)}
                disabled={busy}
              >
                ביטול
              </button>
              <button
                type="button"
                className={styles.dialogDelete}
                onClick={() => void removeEvent()}
                disabled={busy}
              >
                {busy ? "מסיר…" : "הסר מ-ProGrapher"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
