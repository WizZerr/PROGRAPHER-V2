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
import EventCover from "@/features/events/EventCover";
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

type GalleryFilter = "all" | "matched" | "unmatched" | "ambiguous" | "jpeg";

const FILTER_OPTIONS: Array<{ value: GalleryFilter; label: string; note: string }> = [
  { value: "all", label: "הכל", note: "כל התמונות באירוע" },
  { value: "matched", label: "עם עריכת צלם", note: "קבצים עם התאמת XMP" },
  { value: "unmatched", label: "ללא XMP", note: "קבצים שדורשים בדיקה" },
  { value: "ambiguous", label: "לבדיקה", note: "שמות שלא הותאמו בוודאות" },
  { value: "jpeg", label: "JPEG", note: "קובצי JPEG בלבד" },
];

function filterLabel(value: GalleryFilter) {
  return FILTER_OPTIONS.find((option) => option.value === value)?.label ?? "הכל";
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
        <span
          className={`${styles.statusDot} ${styles[`dot_${file.pair_status}`] || ""}`}
          title={statusLabel(file.pair_status)}
        />
        {file.saved_review ? (
          <span className={styles.reviewedBadge} title="נשמרה עריכה">✓</span>
        ) : null}
      </div>

      <div className={styles.cardText}>
        <strong>{file.filename}</strong>
        <span className={styles.cardStatus} title={statusLabel(file.pair_status)}>
          <span
            className={`${styles.inlineDot} ${styles[`dot_${file.pair_status}`] || ""}`}
          />
          {file.pair_status === "matched"
            ? "עריכת צלם"
            : file.pair_status === "jpeg"
              ? "JPEG"
              : file.pair_status === "ambiguous"
                ? "לבדיקה"
                : "ללא XMP"}
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
      <span className={styles.viewButtonGlyph} aria-hidden="true">{glyph}</span>
      <span className={styles.viewButtonLabel}>{label}</span>
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
  const [statusFilter, setStatusFilter] = useState<GalleryFilter>("all");
  const [eventMenuOpen, setEventMenuOpen] = useState(false);
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const eventMenuRef = useRef<HTMLDivElement>(null);
  const filterMenuRef = useRef<HTMLDivElement>(null);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === galleryEventId) ?? null,
    [events, galleryEventId],
  );
  const selectedSource = selectedEvent ? eventSource(selectedEvent) : null;
  const libraryPhotoCount = useMemo(
    () => events.reduce((total, event) => total + event.total_files, 0),
    [events],
  );

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node;
      if (eventMenuRef.current && !eventMenuRef.current.contains(target)) {
        setEventMenuOpen(false);
      }
      if (filterMenuRef.current && !filterMenuRef.current.contains(target)) {
        setFilterMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setEventMenuOpen(false);
        setFilterMenuOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

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

    return files.filter((file) => {
      if (needle && !file.filename.toLowerCase().includes(needle)) {
        return false;
      }

      if (statusFilter === "all") return true;
      if (statusFilter === "matched") return file.pair_status === "matched";
      if (statusFilter === "ambiguous") return file.pair_status === "ambiguous";
      if (statusFilter === "jpeg") return file.pair_status === "jpeg";
      return (
        file.pair_status !== "matched" &&
        file.pair_status !== "jpeg" &&
        file.pair_status !== "ambiguous"
      );
    });
  }, [query, sheet, statusFilter]);

  function selectEvent(value: string) {
    setEventMenuOpen(false);
    setGalleryEventId(value);
    setSheet(null);
    setRenderLimit(240);
    setStatusFilter("all");
    setError("");
  }

  return (
    <div className={styles.screen}>
      <div
        className={
          sheet
            ? styles.topBar
            : `${styles.topBar} ${styles.topBarEmpty}`
        }
      >
        <div className={styles.topIdentity}>
          <span className={styles.galleryMark} aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>

          <div className={styles.topIdentityCopy}>
            <span className={styles.topKicker}>ספריית תמונות</span>
            <strong>{selectedEvent?.name || "גלריה"}</strong>
            <span>
              {selectedEvent
                ? eventCountLabel(selectedEvent)
                : "בחר אירוע כדי לפתוח את סביבת העבודה"}
            </span>
          </div>
        </div>

        {sheet ? (
          <>
            <div className={styles.topCounter}>
              <button type="button" aria-label="תמונה קודמת" disabled>‹</button>
              <bdi>
                {visibleFiles.length.toLocaleString("he-IL")} /{" "}
                {sheet.files.length.toLocaleString("he-IL")}
              </bdi>
              <button type="button" aria-label="תמונה הבאה" disabled>›</button>
            </div>

            <div className={styles.topUtility}>
              {selectedSource ? (
                <span className={styles.sourceChip}>
                  {selectedSource === "raw" ? "RAW" : "JPEG"}
                </span>
              ) : null}
              <span>{sheet.files.length.toLocaleString("he-IL")} תמונות</span>
            </div>
          </>
        ) : (
          <div className={styles.libraryStats}>
            <div>
              <strong>{events.length.toLocaleString("he-IL")}</strong>
              <span>אירועים</span>
            </div>
            <div>
              <strong>{libraryPhotoCount.toLocaleString("he-IL")}</strong>
              <span>תמונות</span>
            </div>
          </div>
        )}
      </div>

      <div className={styles.controlBar}>
        <div className={styles.eventPickerShell} ref={eventMenuRef}>
          <button
            type="button"
            className={
              eventMenuOpen
                ? `${styles.eventPicker} ${styles.eventPickerOpen}`
                : styles.eventPicker
            }
            onClick={() => {
              setEventMenuOpen((open) => !open);
              setFilterMenuOpen(false);
            }}
            disabled={loadingEvents}
            aria-haspopup="listbox"
            aria-expanded={eventMenuOpen}
          >
            {selectedEvent ? (
              <div className={styles.eventPickerThumb}>
                <EventCover eventId={selectedEvent.id} label={selectedEvent.name} />
              </div>
            ) : (
              <div className={styles.eventPickerPlaceholder} aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
            )}

            <div className={styles.eventPickerText}>
              <span className={styles.eventPickerKicker}>אירוע פעיל</span>
              <strong>{selectedEvent?.name || "בחר אירוע"}</strong>
              <span>
                {selectedEvent
                  ? eventCountLabel(selectedEvent)
                  : events.length > 0
                    ? `${events.length.toLocaleString("he-IL")} אירועים זמינים`
                    : "אין אירועים זמינים"}
              </span>
            </div>

            <span className={styles.eventPickerArrow} aria-hidden="true" />
          </button>

          {eventMenuOpen ? (
            <div className={styles.eventMenu} role="listbox" aria-label="בחירת אירוע">
              <div className={styles.menuHeader}>
                <div>
                  <strong>האירועים שלי</strong>
                  <span>{events.length.toLocaleString("he-IL")} אירועים</span>
                </div>
                <span className={styles.menuHint}>בחר כדי לפתוח</span>
              </div>

              <div className={styles.eventMenuList}>
                {events.map((event) => {
                  const active = event.id === galleryEventId;
                  return (
                    <button
                      key={event.id}
                      type="button"
                      role="option"
                      aria-selected={active}
                      className={
                        active
                          ? `${styles.eventMenuItem} ${styles.eventMenuItemActive}`
                          : styles.eventMenuItem
                      }
                      onClick={() => selectEvent(event.id)}
                    >
                      <div className={styles.eventMenuThumb}>
                        <EventCover eventId={event.id} label={event.name} />
                      </div>

                      <div className={styles.eventMenuCopy}>
                        <strong>{event.name}</strong>
                        <div className={styles.eventMenuMeta}>
                          <span>{eventCountLabel(event)}</span>
                          <span
                            className={
                              eventSource(event) === "raw"
                                ? `${styles.menuSourceBadge} ${styles.menuSourceRaw}`
                                : `${styles.menuSourceBadge} ${styles.menuSourceJpeg}`
                            }
                          >
                            {eventSource(event) === "raw" ? "RAW" : "JPEG"}
                          </span>
                        </div>
                      </div>

                      <span className={styles.menuCheck} aria-hidden="true">
                        {active ? "✓" : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>

        <div className={styles.searchWrap}>
          <span aria-hidden="true">⌕</span>
          <input
            className={styles.search}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="חיפוש לפי שם קובץ…"
            aria-label="חיפוש לפי שם קובץ"
          />
        </div>

        <div className={styles.filterShell} ref={filterMenuRef}>
          <button
            type="button"
            className={
              filterMenuOpen
                ? `${styles.filterControl} ${styles.filterControlOpen}`
                : styles.filterControl
            }
            onClick={() => {
              setFilterMenuOpen((open) => !open);
              setEventMenuOpen(false);
            }}
            aria-haspopup="listbox"
            aria-expanded={filterMenuOpen}
          >
            <span className={styles.filterIcon} aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <strong>{filterLabel(statusFilter)}</strong>
            <span className={styles.filterArrow} aria-hidden="true" />
          </button>

          {filterMenuOpen ? (
            <div className={styles.filterMenu} role="listbox" aria-label="סינון גלריה">
              {FILTER_OPTIONS.map((option) => {
                const active = option.value === statusFilter;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={
                      active
                        ? `${styles.filterMenuItem} ${styles.filterMenuItemActive}`
                        : styles.filterMenuItem
                    }
                    onClick={() => {
                      setStatusFilter(option.value);
                      setFilterMenuOpen(false);
                    }}
                  >
                    <span className={styles.filterMenuCheck} aria-hidden="true">
                      {active ? "✓" : ""}
                    </span>
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.note}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className={styles.viewSwitcher} aria-label="תצוגת גלריה">
          <ViewButton
            mode="standard"
            current={galleryViewMode}
            label="סטנדרטי"
            glyph="▦"
            onClick={() => setGalleryViewMode("standard")}
          />
          <ViewButton
            mode="compact"
            current={galleryViewMode}
            label="קומפקטי"
            glyph="▦"
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
      </div>
      <div className={styles.workspace}>

      {!loadingEvents && events.length === 0 && (
        <div className={styles.emptyState}>
          <strong>עדיין אין אירועים.</strong>
          <span>הוסף אירוע במסך אירועים ואז חזור לגלריה.</span>
        </div>
      )}

      {!galleryEventId && !loadingEvents && events.length > 0 && (
        <section className={styles.eventStart}>
          <div className={styles.eventStartHead}>
            <div>
              <span className={styles.eventStartEyebrow}>ספריית אירועים</span>
              <h2>בחר אירוע לפתיחת הגלריה</h2>
              <p>
                האירוע שתבחר יישאר פעיל גם אם תעבור בין מסכים, כך שאפשר
                להמשיך לעבוד בלי לבחור אותו מחדש.
              </p>
            </div>

            <span className={styles.eventStartCount}>
              {events.length.toLocaleString("he-IL")} אירועים זמינים
            </span>
          </div>

          <div className={styles.eventStartGrid}>
            {events.slice(0, 4).map((event) => (
              <button
                key={event.id}
                type="button"
                className={styles.eventStartCard}
                onClick={() => selectEvent(event.id)}
              >
                <div className={styles.eventStartCover}>
                  <EventCover eventId={event.id} label={event.name} />
                  <span
                    className={
                      eventSource(event) === "raw"
                        ? styles.eventStartRaw
                        : styles.eventStartJpeg
                    }
                  >
                    {eventSource(event) === "raw" ? "RAW" : "JPEG"}
                  </span>
                </div>

                <div className={styles.eventStartBody}>
                  <div>
                    <strong>{event.name}</strong>
                    <span>{eventCountLabel(event)}</span>
                  </div>
                  <span className={styles.eventStartArrow} aria-hidden="true">
                    ←
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
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
