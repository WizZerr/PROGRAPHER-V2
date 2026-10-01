"use client";

import { useEffect, useState } from "react";
import CameraPreview from "@/features/review/CameraPreview";
import { listEventFiles } from "./events.api";
import styles from "./EventCover.module.css";

const coverFingerprintCache = new Map<string, string | null>();
const coverRequestCache = new Map<string, Promise<string | null>>();

async function getCoverFingerprint(eventId: string): Promise<string | null> {
  if (coverFingerprintCache.has(eventId)) {
    return coverFingerprintCache.get(eventId) ?? null;
  }

  const existing = coverRequestCache.get(eventId);
  if (existing) return existing;

  const request = listEventFiles(eventId, 1)
    .then((files) => {
      const cover = files.find((file) => file.present) ?? files[0];
      const fingerprint = cover?.fingerprint ?? null;
      coverFingerprintCache.set(eventId, fingerprint);
      return fingerprint;
    })
    .catch(() => {
      coverFingerprintCache.set(eventId, null);
      return null;
    })
    .finally(() => {
      coverRequestCache.delete(eventId);
    });

  coverRequestCache.set(eventId, request);
  return request;
}

export default function EventCover({
  eventId,
  label,
}: {
  eventId: string;
  label: string;
}) {
  const [fingerprint, setFingerprint] = useState<string | null>(
    coverFingerprintCache.get(eventId) ?? null,
  );

  useEffect(() => {
    let cancelled = false;
    void getCoverFingerprint(eventId).then((value) => {
      if (!cancelled) setFingerprint(value);
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
