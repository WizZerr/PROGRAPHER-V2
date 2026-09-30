"use client";

import { useEffect, useState } from "react";
import CameraPreview from "@/features/review/CameraPreview";
import { listEventFiles } from "./events.api";
import styles from "./EventCover.module.css";

export default function EventCover({
  eventId,
  label,
}: {
  eventId: string;
  label: string;
}) {
  const [fingerprint, setFingerprint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listEventFiles(eventId, 1)
      .then((files) => {
        if (cancelled) return;
        const cover = files.find((file) => file.present) ?? files[0];
        setFingerprint(cover?.fingerprint ?? null);
      })
      .catch(() => {
        if (!cancelled) setFingerprint(null);
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  return (
    <div className={styles.cover}>
      {fingerprint ? (
        <CameraPreview eventId={eventId} fingerprint={fingerprint} alt="" />
      ) : (
        <span>{label.slice(0, 1)}</span>
      )}
    </div>
  );
}
