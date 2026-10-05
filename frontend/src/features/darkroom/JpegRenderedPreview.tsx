"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import {
  renderJpegControlPreview,
  type JpegGlobalControls,
} from "./jpegControls.api";
import previewStyles from "@/features/review/CameraPreview.module.css";

type Props = {
  eventId: string;
  fingerprint: string;
  controls: JpegGlobalControls;
  alt: string;
  className?: string;
  style?: CSSProperties;
};

export default function JpegRenderedPreview({
  eventId,
  fingerprint,
  controls,
  alt,
  className,
  style,
}: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const requestId = useRef(0);
  const lastRevision = useRef(0);
  const activeUrl = useRef<string | null>(null);

  useEffect(() => {
    const currentRequest = ++requestId.current;
    const candidateRevision = Date.now() * 1000 + currentRequest;
    const revision = Math.max(
      lastRevision.current + 1,
      candidateRevision,
    );
    lastRevision.current = revision;

    if (activeUrl.current) {
      URL.revokeObjectURL(activeUrl.current);
      activeUrl.current = null;
    }
    setUrl(null);
    setFailed(false);

    let cancelled = false;
    let objectUrl = "";
    const timer = window.setTimeout(() => {

      void renderJpegControlPreview({
        eventId,
        fingerprint,
        revision,
        controls,
      })
        .then((blob) => {
          objectUrl = URL.createObjectURL(blob);
          if (cancelled || currentRequest !== requestId.current) {
            URL.revokeObjectURL(objectUrl);
            objectUrl = "";
            return;
          }
          activeUrl.current = objectUrl;
          setUrl(objectUrl);
          objectUrl = "";
        })
        .catch(() => {
          if (!cancelled && currentRequest === requestId.current) {
            setFailed(true);
            setUrl(null);
          }
        });
    }, 110);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [eventId, fingerprint, controls]);

  useEffect(
    () => () => {
      if (activeUrl.current) {
        URL.revokeObjectURL(activeUrl.current);
        activeUrl.current = null;
      }
    },
    [],
  );

  if (failed || !url) {
    const stateClassName = [previewStyles.state, className]
      .filter(Boolean)
      .join(" ");

    return (
      <div
        className={stateClassName}
        style={style}
        role="img"
        aria-label={
          failed
            ? (alt || "תצוגת JPEG נכשלה")
            : (alt || "מעבד תצוגת JPEG")
        }
      >
        {failed ? (
          <span className={previewStyles.failedIcon} aria-hidden="true">
            ×
          </span>
        ) : (
          <span className={previewStyles.spinner} aria-hidden="true" />
        )}
        <span className={previewStyles.srOnly}>
          {failed ? "תצוגת JPEG נכשלה" : "מעבד תצוגת JPEG"}
        </span>
      </div>
    );
  }

  return (
    <img
      className={className}
      style={style}
      src={url}
      alt={alt}
      draggable={false}
    />
  );
}
