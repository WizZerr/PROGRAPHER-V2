"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { listEvents, type EventSummary } from "@/features/events/events.api";
import CameraPreview from "@/features/review/CameraPreview";
import {
  getReviewSheet,
  type LearningSource,
  type ReviewFile,
  type ReviewSheet,
} from "@/features/testing/testing.api";
import {
  useTestingNav,
  type GalleryViewMode,
} from "@/features/testing/TestingNav";
import WorkspaceBar from "@/components/layout/WorkspaceBar";
import styles from "./GalleryScreen.module.css";

function statusLabel(status: string) {
  if (status === "jpeg") return "JPEG";
  if (status === "matched") return "יש עריכת צלם";
  if (status === "ambiguous") return "שם לא חד";
  return "בלי XMP";
}

function eventSource(event: EventSummary): LearningSource {
  if (event.raw_files > 0) return "raw";
  return "jpeg";
}

function eventCountLabel(event: EventSummary) {
  const parts: string[] = [];
  if (event.raw_files > 0) parts.push(`${event.raw_files} RAW`);
  if (event.jpeg_files > 0) parts.push(`${event.jpeg_files} JPEG`);
  if (parts.length === 0) parts.push(`${event.total_files} קבצים`);
  return parts.join(" · ");
}

function GalleryCard({
  eventId,
  file,
  mode,
  onOpen,
}: {
  eventId: string;
  file: ReviewFile;
  mode: GalleryViewMode;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "320px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <button
      ref={ref}
      type="button"
      className={`${styles.card} ${styles[`card_${mode}`]}`}
      onClick={onOpen}
    >
      <div className={styles.thumb}>
        {visible && (
          <CameraPreview
            eventId={eventId}
            fingerprint={file.fingerprint}
            alt=""
          />
        )}
      </div>
      <span className={`${styles.statusDot} ${styles[`dot_${file.pair_status}`] || ""}`} title={statusLabel(file.pair_status)} />
      <div className={styles.cardText}>
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
      </div>
    </button>
  );
}

function ViewButton({
  mode,
  current,
  label,
  glyph,
  onClick,
}: {
  mode: GalleryViewMode;
  current: GalleryViewMode;
  label: string;
  glyph: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={
        mode === current
          ? `${styles.viewButton} ${styles.viewButtonActive}`
          : styles.viewButton
      }
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      <span aria-hidden="true">{glyph}</span>
    </button>
  );
}

export default function GalleryScreen() {
  const {
    galleryEventId,
    setGalleryEventId,
    galleryViewMode,
    setGalleryViewMode,
    eventCatalogRevision,
    getReviewSheetCache,
    setReviewSheetCache,
    openPhoto,
  } = useTestingNav();

  const [events, setEvents] = useState<EventSummary[]>([]);
  const [sheet, setSheet] = useState<ReviewSheet | null>(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [renderLimit, setRenderLimit] = useState(240);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === galleryEventId) ?? null,
    [events, galleryEventId],
  );
  const selectedSource = selectedEvent ? eventSource(selectedEvent) : null;

  useEffect(() => {
    let cancelled = false;
    setLoadingEvents(true);
    void listEvents()
      .then((items) => {
        if (cancelled) return;
        setEvents(items);
        if (
          galleryEventId &&
          !items.some((item) => item.id === galleryEventId)
        ) {
          setGalleryEventId("");
          setSheet(null);
        }
        setError("");
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof Error ? cause.message : "טעינת האירועים נכשלה.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingEvents(false);
      });

    return () => {
      cancelled = true;
    };
  }, [eventCatalogRevision, setGalleryEventId]);

  useEffect(() => {
    if (!galleryEventId || !selectedSource) {
      setSheet(null);
      setLoadingSheet(false);
      return;
    }

    const cached = getReviewSheetCache(galleryEventId, selectedSource);
    if (cached) {
      setSheet(cached);
      setLoadingSheet(false);
      setError("");
      return;
    }

    let cancelled = false;
    setSheet(null);
    setLoadingSheet(true);
    setError("");

    void getReviewSheet(galleryEventId, selectedSource)
      .then((value) => {
        if (cancelled) return;
        setReviewSheetCache(value);
        setSheet(value);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof Error ? cause.message : "טעינת התמונות נכשלה.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingSheet(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    galleryEventId,
    selectedSource,
    getReviewSheetCache,
    setReviewSheetCache,
    eventCatalogRevision,
  ]);

  useEffect(() => {
    setRenderLimit(240);
  }, [sheet?.event_id]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || !sheet || renderLimit >= sheet.files.length) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setRenderLimit((current) =>
          Math.min(sheet.files.length, current + 240),
        );
      },
      { rootMargin: "700px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [sheet, renderLimit]);

  const visibleFiles = useMemo(() => {
    const files = sheet?.files ?? [];
    const needle = query.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) => file.filename.toLowerCase().includes(needle));
  }, [query, sheet]);

  function selectEvent(value: string) {
    setGalleryEventId(value);
    setSheet(null);
    setRenderLimit(240);
    setError("");
  }

  return (
    <div className={styles.screen}>
      <WorkspaceBar
        kicker="גלריה"
        title={selectedEvent?.name || "בחירת אירוע"}
        detail={selectedEvent ? eventCountLabel(selectedEvent) : undefined}
        counter={sheet ? `${visibleFiles.length.toLocaleString("he-IL")} / ${sheet.files.length.toLocaleString("he-IL")}` : undefined}
      >
        <input
          className={styles.search}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="חיפוש לפי שם קובץ"
          aria-label="חיפוש לפי שם קובץ"
        />
        <div className={styles.toolbarActions}>
          <div className={styles.viewSwitcher} aria-label="תצוגת גלריה">
            <ViewButton
              mode="standard"
              current={galleryViewMode}
              label="תמונות גדולות"
              glyph="▦"
              onClick={() => setGalleryViewMode("standard")}
            />
            <ViewButton
              mode="compact"
              current={galleryViewMode}
              label="תמונות קטנות"
              glyph="▦▦"
              onClick={() => setGalleryViewMode("compact")}
            />
            <ViewButton
              mode="list"
              current={galleryViewMode}
              label="רשימה"
              glyph="☷"
              onClick={() => setGalleryViewMode("list")}
            />
          </div>

          <label className={styles.field}>
            <span>אירוע</span>
            <select
              value={galleryEventId}
              onChange={(event) => selectEvent(event.target.value)}
              disabled={loadingEvents}
            >
              <option value="">
                {loadingEvents ? "טוען אירועים…" : "בחר אירוע"}
              </option>
              {events.map((event) => (
                <option key={event.id} value={event.id}>
                  {event.name} · {eventCountLabel(event)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </WorkspaceBar>
      <div className={styles.workspace}>

      {!loadingEvents && events.length === 0 && (
        <div className={styles.emptyState}>
          <strong>עדיין אין אירועים.</strong>
          <span>הוסף אירוע במסך אירועים ואז חזור לגלריה.</span>
        </div>
      )}

      {!galleryEventId && !loadingEvents && events.length > 0 && (
        <div className={styles.emptyState}>
          <strong>בחר אירוע כדי לפתוח את הגלריה.</strong>
          <span>האירוע שתבחר יישאר נבחר גם אם תעבור למסך אחר.</span>
        </div>
      )}

      {loadingSheet && (
        <div className={styles.loadingState} role="status" aria-live="polite">
          <span className={styles.spinner} aria-hidden="true" />
          <div>
            <strong>טוען את הגלריה…</strong>
            <span>
              {selectedEvent
                ? `${selectedEvent.name} · ${eventCountLabel(selectedEvent)}`
                : "מכין את התמונות"}
            </span>
          </div>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}

      {sheet && sheet.files.length === 0 && (
        <div className={styles.emptyState}>
          <strong>לא נמצאו תמונות להצגה.</strong>
          <span>
            {sheet.learning_source === "jpeg"
              ? "באירוע הזה אין קבצי JPEG."
              : "באירוע הזה אין קבצי RAW."}
          </span>
        </div>
      )}

      {sheet && sheet.files.length > 0 && (
        <>
          <div className={styles.gallerySummary}>
            <strong>{sheet.event_name}</strong>
            <span>
              {sheet.files.length.toLocaleString("he-IL")} תמונות ·{" "}
              {sheet.learning_source === "jpeg" ? "JPEG" : "RAW"}
            </span>
          </div>

          <div
            className={`${styles.grid} ${styles[`grid_${galleryViewMode}`]}`}
          >
            {visibleFiles.slice(0, renderLimit).map((file) => (
              <GalleryCard
                key={file.fingerprint}
                eventId={sheet.event_id}
                file={file}
                mode={galleryViewMode}
                onOpen={() =>
                  openPhoto(
                    sheet.event_id,
                    file.fingerprint,
                    sheet.learning_source,
                  )
                }
              />
            ))}
          </div>

          {renderLimit < visibleFiles.length && (
            <div
              ref={loadMoreRef}
              className={styles.moreState}
              aria-live="polite"
            >
              מציג {renderLimit.toLocaleString("he-IL")} מתוך{" "}
              {visibleFiles.length.toLocaleString("he-IL")} · ממשיך לטעון בגלילה
            </div>
          )}
        </>
      )}
      </div>
    </div>
  );
}
