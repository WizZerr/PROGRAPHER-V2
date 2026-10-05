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
  const [failureMessage, setFailureMessage] = useState("");
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

    setFailureMessage("");

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
          const previousUrl = activeUrl.current;
          activeUrl.current = objectUrl;
          setUrl(objectUrl);
          setFailureMessage("");
          objectUrl = "";
          if (previousUrl) {
            URL.revokeObjectURL(previousUrl);
          }
        })
        .catch((cause: unknown) => {
          if (!cancelled && currentRequest === requestId.current) {
            setFailureMessage(
              cause instanceof Error
                ? cause.message
                : "תצוגת JPEG נכשלה מסיבה לא ידועה.",
            );
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

  if (!url) {
    const stateClassName = [previewStyles.state, className]
      .filter(Boolean)
      .join(" ");

    return (
      <div
        className={stateClassName}
        style={style}
        role="img"
        aria-label={
          failureMessage
            ? `${alt || "תצוגת JPEG נכשלה"}: ${failureMessage}`
            : (alt || "מעבד תצוגת JPEG")
        }
        title={failureMessage || undefined}
      >
        {failureMessage ? (
          <div className={previewStyles.failureDetails}>
            <span className={previewStyles.failedIcon} aria-hidden="true">
              ×
            </span>
            <span>{failureMessage}</span>
          </div>
        ) : (
          <span className={previewStyles.spinner} aria-hidden="true" />
        )}
        <span className={previewStyles.srOnly}>
          {failureMessage ? "תצוגת JPEG נכשלה" : "מעבד תצוגת JPEG"}
        </span>
      </div>
    );
  }

  const previewClassName = [previewStyles.previewWrap, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={previewClassName} style={style}>
      <img
        className={previewStyles.previewImage}
        src={url}
        alt={alt}
        draggable={false}
      />
      {failureMessage ? (
        <div className={previewStyles.failureOverlay} role="status">
          {failureMessage}
        </div>
      ) : null}
    </div>
  );
}
