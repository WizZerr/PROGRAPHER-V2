"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { apiBlob } from "@/lib/api";

type CameraPreviewProps = {
  eventId: string;
  fingerprint: string;
  alt: string;
  className?: string;
  style?: CSSProperties;
};

export default function CameraPreview({
  eventId,
  fingerprint,
  alt,
  className,
  style,
}: CameraPreviewProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    setUrl(null);
    setFailed(false);

    void apiBlob(`/api/events/${eventId}/files/${fingerprint}/preview`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [eventId, fingerprint]);

  if (failed || !url) {
    return (
      <div className={className} style={style} role="img" aria-label={alt}>
        <span>{failed ? "אין תצוגת מצלמה" : "טוען תצוגה"}</span>
      </div>
    );
  }

  return <img className={className} style={style} src={url} alt={alt} draggable={false} />;
}
