"use client";

import { useEffect, useState } from "react";
import { listEvents, type EventSummary } from "@/features/events/events.api";
import { getReviewSheet, type ReviewSheet } from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import styles from "@/features/testing/testing.module.css";

function statusLabel(status: string) {
  if (status === "matched") return "יש עריכת צלם";
  if (status === "ambiguous") return "שם קובץ לא חד";
  return "אין XMP תואם";
}

export default function GalleryScreen() {
  const { openPhoto } = useTestingNav();
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [eventId, setEventId] = useState("");
  const [sheet, setSheet] = useState<ReviewSheet | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void listEvents()
      .then((items) => {
        setEvents(items);
        if (items[0]) setEventId(items[0].id);
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת האירועים נכשלה.");
      });
  }, []);

  useEffect(() => {
    if (!eventId) return;
    void getReviewSheet(eventId)
      .then(setSheet)
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת התמונות נכשלה.");
      });
  }, [eventId]);

  return (
    <div className={styles.screen}>
      <section className={styles.hero}>
        <h2>גלריית בדיקה</h2>
        <p>
          בוחרים אירוע שנסרק, ופותחים תמונה כדי לראות את הצעת הבסיס מול עריכת
          הצלם אם קיימת. כל התמונות נשארות לבדיקה.
        </p>
        <div className={styles.actions}>
          <label className={styles.field}>
            <span>אירוע</span>
            <select
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
            >
              {events.length === 0 && <option value="">אין אירועים</option>}
              {events.map((event) => (
                <option key={event.id} value={event.id}>
                  {event.name} · {event.raw_files} RAW
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {error && <p className={styles.error}>{error}</p>}
      {sheet && <p className={styles.note}>{sheet.note}</p>}

      <section className={styles.fileList}>
        {sheet?.files.map((file) => (
          <button
            key={file.fingerprint}
            className={styles.fileButton}
            type="button"
            onClick={() => openPhoto(sheet.event_id, file.fingerprint)}
          >
            <span>
              <strong className={styles.fileName}>{file.filename}</strong>
              <small className={styles.note}> {statusLabel(file.pair_status)}</small>
            </span>
            <bdi className={styles.ltr}>
              {file.suggested
                ? `${file.suggested.exposure} / ${file.suggested.temperature}K / ${file.suggested.tint}`
                : "אין הצעה"}
            </bdi>
          </button>
        ))}
        {sheet && sheet.files.length === 0 && (
          <p className={styles.note}>באירוע הזה אין קבצי RAW.</p>
        )}
      </section>
    </div>
  );
}
