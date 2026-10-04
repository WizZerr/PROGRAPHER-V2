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
  const revisionSequence = useRef(0);

  useEffect(() => {
    const currentRequest = ++requestId.current;
    revisionSequence.current += 1;
    const revision =
      Date.now() * 1000 + (revisionSequence.current % 1000);

    let cancelled = false;
    let objectUrl = "";
    const timer = window.setTimeout(() => {
      setFailed(false);

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
          setUrl((previous) => {
            if (previous) URL.revokeObjectURL(previous);
            return objectUrl;
          });
          objectUrl = "";
        })
        .catch(() => {
          if (!cancelled && currentRequest === requestId.current) {
            setFailed(true);
            setUrl((previous) => {
              if (previous) URL.revokeObjectURL(previous);
              return null;
            });
          }
        });
    }, 110);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [
    eventId,
    fingerprint,
    controls.brightness,
    controls.contrast,
    controls.warmth,
    controls.tint,
  ]);

  useEffect(
    () => () => {
      setUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return null;
      });
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
