"use client";

import { useEffect, useRef, useState } from "react";
import { listEvents, type EventSummary } from "@/features/events/events.api";
import CameraPreview from "@/features/review/CameraPreview";
import { getReviewSheet, type ReviewFile, type ReviewSheet } from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import styles from "./GalleryScreen.module.css";

function statusLabel(status: string) {
  if (status === "jpeg") return "JPEG";
  if (status === "matched") return "יש עריכת צלם";
  if (status === "ambiguous") return "שם לא חד";
  return "בלי XMP";
}

function GalleryCard({
  eventId,
  file,
  onOpen,
}: {
  eventId: string;
  file: ReviewFile;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setVisible(true);
      },
      { rootMargin: "240px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <button ref={ref} type="button" className={styles.card} onClick={onOpen}>
      <div className={styles.thumb}>
        {visible && (
          <CameraPreview eventId={eventId} fingerprint={file.fingerprint} alt="" />
        )}
      </div>
      <strong>{file.filename}</strong>
      <span className={styles.meta}>
        <span>{statusLabel(file.pair_status)}</span>
        <bdi>
          {file.pair_status === "jpeg"
            ? "בלי מתכון"
            : file.suggested?.exposure != null
              ? file.suggested.exposure.toFixed(2)
              : "—"}
        </bdi>
      </span>
    </button>
  );
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
      .then((value) => {
        setSheet(value);
        setError("");
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת התמונות נכשלה.");
      });
  }, [eventId]);

  return (
    <div className={styles.screen}>
      <div className={styles.toolbar}>
        <div>
          <h2>גלריה</h2>
          <p>כל התמונות נשארות לבדיקה. לחיצה פותחת את חדר העריכה.</p>
        </div>
        <label className={styles.field}>
          <span>אירוע</span>
          <select value={eventId} onChange={(event) => setEventId(event.target.value)}>
            {events.length === 0 && <option value="">אין אירועים</option>}
            {events.map((event) => (
              <option key={event.id} value={event.id}>
                {event.name} · {event.raw_files} RAW
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className={styles.error}>{error}</p>}
      {sheet && sheet.files.length === 0 && (
        <p className={styles.empty}>
          {sheet.learning_source === "jpeg"
            ? "באירוע הזה אין קבצי JPEG."
            : "באירוע הזה אין קבצי RAW."}
        </p>
      )}

      <div className={styles.grid}>
        {sheet?.files.map((file) => (
          <GalleryCard
            key={file.fingerprint}
            eventId={sheet.event_id}
            file={file}
            onOpen={() => openPhoto(sheet.event_id, file.fingerprint)}
          />
        ))}
      </div>
    </div>
  );
}
