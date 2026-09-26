"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { apiBlob } from "@/lib/api";
import previewStyles from "./CameraPreview.module.css";

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
    const stateClassName = [previewStyles.state, className]
      .filter(Boolean)
      .join(" ");

    return (
      <div
        className={stateClassName}
        style={style}
        role="img"
        aria-label={failed ? (alt || "אין תצוגה זמינה") : (alt || "טוען תצוגה")}
        title={failed ? "אין תצוגה זמינה" : undefined}
      >
        {failed ? (
          <span className={previewStyles.failedIcon} aria-hidden="true">×</span>
        ) : (
          <span className={previewStyles.spinner} aria-hidden="true" />
        )}
        <span className={previewStyles.srOnly}>
          {failed ? "אין תצוגה זמינה" : "טוען תצוגה"}
        </span>
      </div>
    );
  }

  return <img className={className} style={style} src={url} alt={alt} draggable={false} />;
}
