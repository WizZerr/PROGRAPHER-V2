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

type RenderedPreview = {
  url: string;
  signature: string;
};

type PreviewFailure = {
  message: string;
  signature: string;
};

function controlsSignature(controls: JpegGlobalControls): string {
  return [
    controls.brightness,
    controls.contrast,
    controls.warmth,
    controls.tint,
  ].join("|");
}

export default function JpegRenderedPreview({
  eventId,
  fingerprint,
  controls,
  alt,
  className,
  style,
}: Props) {
  const [rendered, setRendered] = useState<RenderedPreview | null>(null);
  const [failure, setFailure] = useState<PreviewFailure | null>(null);
  const requestId = useRef(0);
  const lastRevision = useRef(0);
  const activeUrl = useRef<string | null>(null);
  const signature = controlsSignature(controls);

  useEffect(() => {
    const currentRequest = ++requestId.current;
    const requestSignature = controlsSignature(controls);
    const candidateRevision = Date.now() * 1000 + currentRequest;
    const revision = Math.max(
      lastRevision.current + 1,
      candidateRevision,
    );
    lastRevision.current = revision;

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
          setRendered({
            url: objectUrl,
            signature: requestSignature,
          });
          setFailure(null);
          objectUrl = "";

          if (previousUrl) {
            URL.revokeObjectURL(previousUrl);
          }
        })
        .catch((cause: unknown) => {
          if (!cancelled && currentRequest === requestId.current) {
            setFailure({
              signature: requestSignature,
              message:
                cause instanceof Error
                  ? cause.message
                  : "תצוגת JPEG נכשלה מסיבה לא ידועה.",
            });
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

  const currentFailure =
    failure?.signature === signature ? failure.message : "";

  if (currentFailure) {
    const stateClassName = [
      previewStyles.state,
      previewStyles.jpegFailureState,
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div
        className={stateClassName}
        style={style}
        role="img"
        aria-label={`${alt || "תצוגת JPEG נכשלה"}: ${currentFailure}`}
        title={currentFailure}
      >
        <div className={previewStyles.failureDetails}>
          <span className={previewStyles.failedIcon} aria-hidden="true">
            ×
          </span>
          <span>{currentFailure}</span>
        </div>
      </div>
    );
  }

  // While the authoritative render is still catching up, render nothing here.
  // DarkroomScreen keeps the instant local illustration visible underneath.
  if (!rendered || rendered.signature !== signature) {
    return null;
  }

  const previewClassName = [previewStyles.previewWrap, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={previewClassName} style={style}>
      <img
        className={previewStyles.previewImage}
        src={rendered.url}
        alt={alt}
        draggable={false}
      />
    </div>
  );
}
