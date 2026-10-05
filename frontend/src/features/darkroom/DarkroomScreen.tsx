"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import WorkspaceBar from "@/components/layout/WorkspaceBar";
import CameraPreview from "@/features/review/CameraPreview";
import JpegRenderedPreview from "@/features/darkroom/JpegRenderedPreview";
import {
  JPEG_NEUTRAL_CONTROLS,
  type JpegGlobalControls,
} from "@/features/darkroom/jpegControls.api";
import {
  exportRecipes,
  getReviewSheet,
  saveReview,
  type LearningSource,
  type ReviewFile,
} from "@/features/testing/testing.api";
import { useTestingNav } from "@/features/testing/TestingNav";
import styles from "./DarkroomScreen.module.css";

type Recipe = {
  exposure: number;
  temperature: number;
  tint: number;
};

function sameRecipe(left: Recipe, right: Recipe) {
  return (
    left.exposure === right.exposure &&
    left.temperature === right.temperature &&
    left.tint === right.tint
  );
}

function formatRecipe(recipe: Recipe | null | undefined) {
  if (
    !recipe ||
    recipe.exposure == null ||
    recipe.temperature == null ||
    recipe.tint == null
  ) {
    return "חסר";
  }
  const exposure = `${recipe.exposure >= 0 ? "+" : ""}${recipe.exposure.toFixed(2)}`;
  const tint = `${recipe.tint >= 0 ? "+" : ""}${recipe.tint}`;
  return `${exposure} / ${recipe.temperature}K / ${tint}`;
}

function jpegIllustrationStyle(
  controls: JpegGlobalControls,
  enabled: boolean,
): CSSProperties {
  if (!enabled) return {};

  const brightness = 2 ** (controls.brightness / 100);
  const contrast = 1 + 0.005 * controls.contrast;
  const warmthAmount = Math.min(1, Math.abs(controls.warmth) / 100);
  const tintAmount = Math.min(1, Math.abs(controls.tint) / 100);

  return {
    ["--preview-brightness" as string]: String(brightness),
    ["--preview-contrast" as string]: String(contrast),
    ["--preview-sepia" as string]: "0",
    ["--preview-saturate" as string]: "1",
    ["--preview-hue" as string]: "0deg",
    ["--preview-warmth-color" as string]:
      controls.warmth < 0
        ? "rgb(70 145 255)"
        : controls.warmth > 0
          ? "rgb(255 148 72)"
          : "transparent",
    ["--preview-warmth-opacity" as string]: String(warmthAmount * 0.16),
    ["--preview-tint-color" as string]:
      controls.tint < 0
        ? "rgb(42 201 122)"
        : controls.tint > 0
          ? "rgb(218 74 184)"
          : "transparent",
    ["--preview-tint-opacity" as string]: String(tintAmount * 0.14),
  };
}

function illustrationStyle(recipe: Recipe, enabled: boolean): CSSProperties {
  if (!enabled) return {};

  const brightness = Math.min(1.8, Math.max(0.45, 1 + recipe.exposure * 0.18));
  const warmth = Math.max(-40, Math.min(40, (recipe.temperature - 5500) / 80));
  const tintAmount = Math.min(1, Math.abs(recipe.tint) / 150);
  const tintColor =
    recipe.tint < 0
      ? "rgb(42 201 122)"
      : recipe.tint > 0
        ? "rgb(218 74 184)"
        : "transparent";

  return {
    ["--preview-brightness" as string]: String(brightness),
    ["--preview-sepia" as string]: warmth > 0 ? "0.25" : "0",
    ["--preview-saturate" as string]: String(
      Math.min(1.16, 1.03 + Math.abs(recipe.tint) * 0.0007),
    ),
    ["--preview-hue" as string]: `${-warmth * 0.35}deg`,
    ["--preview-tint-color" as string]: tintColor,
    ["--preview-tint-opacity" as string]: String(tintAmount * 0.34),
  };
}

export default function DarkroomScreen() {
  const {
    selection,
    outputDir,
    setOutputDir,
    getReviewSheetCache,
    setReviewSheetCache,
    patchCachedReview,
    getDraft,
    setDraft,
    clearDraft,
    openPhoto,
    openGallery,
  } = useTestingNav();
  const frameRef = useRef<HTMLDivElement>(null);
  const filmstripRef = useRef<HTMLDivElement>(null);
  const activeThumbRef = useRef<HTMLButtonElement>(null);
  const [filmstripWindow, setFilmstripWindow] = useState({ start: 0, end: 24 });
  const [files, setFiles] = useState<ReviewFile[]>([]);
  const [learningSource, setLearningSource] = useState<LearningSource>("raw");
  const [sheetNote, setSheetNote] = useState("");
  const [exposure, setExposure] = useState(0);
  const [temperature, setTemperature] = useState(5500);
  const [tint, setTint] = useState(0);
  const [jpegControls, setJpegControls] = useState<JpegGlobalControls>(
    JPEG_NEUTRAL_CONTROLS,
  );
  const jpegDrafts = useRef<Record<string, JpegGlobalControls>>({});
  const [ready, setReady] = useState(false);
  const [compare, setCompare] = useState(62);
  const [showIllustration, setShowIllustration] = useState(false);
  const [showJpegPreview, setShowJpegPreview] = useState(false);
  const [holdOriginal, setHoldOriginal] = useState(false);
  const [history, setHistory] = useState<Recipe[]>([]);
  const [, setFuture] = useState<Recipe[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dirty, setDirty] = useState(false);
  const dragOrigin = useRef<Recipe | null>(null);

  const file = files.find((item) => item.fingerprint === selection?.fingerprint) ?? null;
  const index = file ? files.findIndex((item) => item.fingerprint === file.fingerprint) : -1;
  const current = useMemo<Recipe>(
    () => ({ exposure, temperature, tint }),
    [exposure, temperature, tint],
  );

  const jpegDraftKey =
    selection && file
      ? `${selection.eventId}:${file.fingerprint}`
      : "";

  useEffect(() => {
    if (learningSource !== "jpeg" || !jpegDraftKey) return;
    setJpegControls(
      jpegDrafts.current[jpegDraftKey] ?? JPEG_NEUTRAL_CONTROLS,
    );
  }, [learningSource, jpegDraftKey]);

  const updateJpegControl = useCallback(
    (name: keyof JpegGlobalControls, value: number) => {
      setJpegControls((currentControls) => {
        const next = { ...currentControls, [name]: value };
        if (jpegDraftKey) {
          jpegDrafts.current[jpegDraftKey] = next;
        }
        return next;
      });
    },
    [jpegDraftKey],
  );

  const resetJpegControls = useCallback(() => {
    const next = { ...JPEG_NEUTRAL_CONTROLS };
    if (jpegDraftKey) {
      jpegDrafts.current[jpegDraftKey] = next;
    }
    setJpegControls(next);
  }, [jpegDraftKey]);

  const updateFilmstripWindow = useCallback(() => {
    const strip = filmstripRef.current;
    if (!strip) return;

    const thumbStride = 100; // 92px thumbnail + 8px gap
    const preload = 8;
    const start = Math.max(0, Math.floor(strip.scrollLeft / thumbStride) - preload);
    const end = Math.min(
      Math.max(0, files.length - 1),
      Math.ceil((strip.scrollLeft + strip.clientWidth) / thumbStride) + preload,
    );

    setFilmstripWindow((currentWindow) =>
      currentWindow.start === start && currentWindow.end === end
        ? currentWindow
        : { start, end },
    );
  }, [files.length]);

  useEffect(() => {
    const active = activeThumbRef.current;
    if (!active) return;

    // Keep keyboard focus attached to the currently selected thumbnail.
    // Otherwise a mouse-selected thumbnail keeps its focus outline even
    // after ArrowLeft/ArrowRight move the actual selection elsewhere.
    active.focus({ preventScroll: true });
    active.scrollIntoView({
      behavior: "auto",
      block: "nearest",
      inline: "center",
    });

    requestAnimationFrame(updateFilmstripWindow);
  }, [file?.fingerprint, updateFilmstripWindow]);

  useEffect(() => {
    updateFilmstripWindow();
    const strip = filmstripRef.current;
    if (!strip) return;

    const observer = new ResizeObserver(updateFilmstripWindow);
    observer.observe(strip);
    return () => observer.disconnect();
  }, [updateFilmstripWindow]);

  const suggestion =
    file?.suggested ?? file?.baseline ?? file?.photographer ?? null;
  const suggestedRecipe =
    suggestion?.exposure != null &&
    suggestion.temperature != null &&
    suggestion.tint != null
      ? {
          exposure: suggestion.exposure,
          temperature: suggestion.temperature,
          tint: suggestion.tint,
        }
      : null;

  const applyRecipe = useCallback((recipe: Recipe, recordHistory: boolean) => {
    if (recordHistory) {
      setHistory((items) => [...items, current]);
      setFuture([]);
    }
    setExposure(recipe.exposure);
    setTemperature(recipe.temperature);
    setTint(recipe.tint);
    setReady(true);
    if (selection && file) {
      setDraft(selection.eventId, file.fingerprint, recipe);
    }
    setDirty(true);
  }, [current, file, selection, setDraft]);

  useEffect(() => {
    if (!selection) {
      setFiles([]);
      setReady(false);
      setLoading(false);
      return;
    }

    let cancelled = false;

    function applySheet(sheet: Awaited<ReturnType<typeof getReviewSheet>>) {
      if (cancelled) return;
      setFiles(sheet.files);
      setLearningSource(sheet.learning_source ?? selection!.learningSource);
      setSheetNote(sheet.note);

      const match = sheet.files.find(
        (item) => item.fingerprint === selection!.fingerprint,
      );
      const draft = match
        ? getDraft(selection!.eventId, match.fingerprint)
        : null;
      const source = draft ?? match?.saved_review ?? match?.suggested;

      if (
        source?.exposure != null &&
        source.temperature != null &&
        source.tint != null
      ) {
        setExposure(source.exposure);
        setTemperature(source.temperature);
        setTint(source.tint);
        setReady(true);
        setDirty(Boolean(draft));
      } else {
        setReady(false);
        setDirty(false);
      }

      setHistory([]);
      setFuture([]);
      setError("");
      setMessage("");
      setLoading(false);
    }

    const cached = getReviewSheetCache(
      selection.eventId,
      selection.learningSource,
    );

    if (cached) {
      applySheet(cached);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setFiles([]);
    setReady(false);
    setError("");

    void getReviewSheet(selection.eventId, selection.learningSource)
      .then((sheet) => {
        setReviewSheetCache(sheet);
        applySheet(sheet);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof Error ? cause.message : "טעינת התמונה נכשלה.",
        );
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selection, getDraft, getReviewSheetCache, setReviewSheetCache]);

  function rememberBeforeDrag() {
    dragOrigin.current = current;
  }

  function commitDrag() {
    const origin = dragOrigin.current;
    dragOrigin.current = null;
    if (!origin || sameRecipe(origin, current)) return;
    setHistory((items) => [...items, origin]);
    setFuture([]);
  }

  function undo() {
    setHistory((items) => {
      const previous = items.at(-1);
      if (!previous) return items;
      setFuture((upcoming) => [current, ...upcoming]);
      setExposure(previous.exposure);
      setTemperature(previous.temperature);
      setTint(previous.tint);
      if (selection && file) {
        setDraft(selection.eventId, file.fingerprint, previous);
      }
      setDirty(true);
      return items.slice(0, -1);
    });
  }

  function redo() {
    setFuture((items) => {
      const next = items[0];
      if (!next) return items;
      setHistory((past) => [...past, current]);
      setExposure(next.exposure);
      setTemperature(next.temperature);
      setTint(next.tint);
      if (selection && file) {
        setDraft(selection.eventId, file.fingerprint, next);
      }
      setDirty(true);
      return items.slice(1);
    });
  }

  async function chooseOutput() {
    const selected = await open({
      directory: true,
      multiple: false,
      title: "בחר תיקיית ייצוא XMP",
    });
    if (!selected || Array.isArray(selected)) return null;
    setOutputDir(selected);
    return selected;
  }

  function decisionForCurrent(): "approved" | "corrected" {
    return suggestedRecipe && sameRecipe(current, suggestedRecipe)
      ? "approved"
      : "corrected";
  }

  function markCurrentSaved(recipe: Recipe) {
    if (!file) return;
    if (selection) {
      patchCachedReview(
        selection.eventId,
        selection.learningSource,
        file.fingerprint,
        recipe,
      );
    }
    setFiles((items) =>
      items.map((item) =>
        item.fingerprint === file.fingerprint
          ? {
              ...item,
              saved_review: {
                exposure: recipe.exposure,
                temperature: recipe.temperature,
                tint: recipe.tint,
                process_version: item.photographer?.process_version ?? null,
                camera_profile: item.photographer?.camera_profile ?? null,
              },
            }
          : item,
      ),
    );
    if (selection) {
      clearDraft(selection.eventId, file.fingerprint);
    }
    setDirty(false);
  }

  function stashDraft() {
    if (!selection || !file || !ready || !dirty) return;
    setDraft(selection.eventId, file.fingerprint, current);
  }

  async function saveCurrentReview() {
    if (!selection || !file || !ready) return;
    const decision = decisionForCurrent();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await saveReview({
        event_id: selection.eventId,
        item: {
          fingerprint: file.fingerprint,
          exposure,
          temperature,
          tint,
          decision,
        },
      });
      markCurrentSaved(current);
      setMessage(decision === "approved" ? "האישור נשמר." : "התיקון נשמר.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "שמירת התיקון נכשלה.");
    } finally {
      setBusy(false);
    }
  }

  async function exportCurrent() {
    if (!selection || !file || !ready) return;
    const folder = outputDir || (await chooseOutput());
    if (!folder) return;
    const decision = decisionForCurrent();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await exportRecipes({
        event_id: selection.eventId,
        output_dir: folder,
        items: [
          {
            fingerprint: file.fingerprint,
            exposure,
            temperature,
            tint,
            decision,
          },
        ],
      });
      const item = result.files[0];
      if (item?.status === "written") {
        markCurrentSaved(current);
        setMessage(decision === "approved" ? "האישור נשמר וה-XMP יוצא." : "התיקון נשמר וה-XMP יוצא.");
      } else {
        setError(item?.reason || "הייצוא לא נכתב.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הייצוא נכשל.");
    } finally {
      setBusy(false);
    }
  }

  function openSelectedPhoto(fingerprint: string) {
    if (!selection) return;
    stashDraft();
    openPhoto(selection.eventId, fingerprint, selection.learningSource);
  }

  function returnToGallery() {
    stashDraft();
    openGallery();
  }

  function move(step: number) {
    if (!selection || index < 0) return;
    const next = files[index + step];
    if (!next) return;
    openSelectedPhoto(next.fingerprint);
  }

  function updateCompare(clientX: number) {
    const frame = frameRef.current;
    if (!frame) return;
    const bounds = frame.getBoundingClientRect();
    const ratio = (clientX - bounds.left) / bounds.width;
    setCompare(Math.min(100, Math.max(0, ratio * 100)));
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target;
      const typing =
        target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
      if (event.key === "Escape") {
        returnToGallery();
        return;
      }
      if (typing && event.key !== "z" && event.key !== "Z") return;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        move(1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        move(-1);
      } else if (event.key === "Enter" && !typing && learningSource !== "jpeg") {
        event.preventDefault();
        void exportCurrent();
      } else if ((event.key === "z" || event.key === "Z") && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      } else if (event.key === "b" || event.key === "B" || event.key === "\\") {
        setHoldOriginal(true);
      }
    }

    function onKeyUp(event: KeyboardEvent) {
      if (event.key === "b" || event.key === "B" || event.key === "\\") {
        setHoldOriginal(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  });

  if (selection && loading) {
    return (
      <div className={styles.empty}>
        <div className={styles.loadingBox} role="status" aria-live="polite">
          <span className={styles.loadingSpinner} aria-hidden="true" />
          <h2>טוען את התמונה…</h2>
          <p>מכין את חדר העריכה ואת נתוני האירוע.</p>
        </div>
      </div>
    );
  }

  if (!selection || !file) {
    return (
      <div className={styles.emptyWorkspace}>
        <section className={styles.emptyHero}>
          <div className={styles.emptyCopy}>
            <span className={styles.emptyEyebrow}>חדר עריכה</span>
            <h2>
              <span>העריכה מתחילה</span>
              <span className={styles.emptyAccent}>מהתמונה הנכונה.</span>
            </h2>
            <p>
              {error
                ? error
                : "בחר תמונה מהגלריה כדי לפתוח אותה בסביבת העריכה, להשוות מול המקור ולשמור תיקון או לייצא XMP ל-Lightroom."}
            </p>

            <div className={styles.emptyActions}>
              <button
                className={styles.emptyPrimary}
                type="button"
                onClick={openGallery}
              >
                <span className={styles.emptyButtonIcon} aria-hidden="true">
                  ▧
                </span>
                פתח את הגלריה
              </button>
            </div>

            <div className={styles.emptyCapabilities}>
              <span>RAW + XMP</span>
              <span>טיוטות נשמרות</span>
              <span>ייצוא ל-Lightroom</span>
            </div>
          </div>

          <div className={styles.emptyMock} aria-hidden="true">
            <div className={styles.emptyMockTop}>
              <span />
              <span />
              <span />
            </div>

            <div className={styles.emptyMockBody}>
              <div className={styles.emptyMockCanvas}>
                <div className={styles.emptyMockFrame}>
                  <span className={styles.emptyMockPhotoIcon}>▧</span>
                  <strong>בחר תמונה לעריכה</strong>
                  <small>התצוגה תיפתח כאן</small>
                </div>
              </div>

              <div className={styles.emptyMockPanel}>
                <div className={styles.emptyMockPanelTitle}>
                  <strong>עריכה</strong>
                  <span>RAW</span>
                </div>

                <div className={styles.emptyControl}>
                  <div>
                    <span>חשיפה</span>
                    <bdi>0.00</bdi>
                  </div>
                  <i className={styles.emptyExposureTrack} />
                </div>

                <div className={styles.emptyControl}>
                  <div>
                    <span>טמפרטורה</span>
                    <bdi>5,500 K</bdi>
                  </div>
                  <i className={styles.emptyTemperatureTrack} />
                </div>

                <div className={styles.emptyControl}>
                  <div>
                    <span>גוון</span>
                    <bdi>0</bdi>
                  </div>
                  <i className={styles.emptyTintTrack} />
                </div>
              </div>
            </div>

            <div className={styles.emptyMockFilmstrip}>
              {Array.from({ length: 7 }).map((_, itemIndex) => (
                <span key={itemIndex} />
              ))}
            </div>
          </div>
        </section>

        <section className={styles.emptyWorkflow} aria-label="תהליך העבודה">
          <article>
            <span className={styles.workflowIndex}>01</span>
            <div>
              <strong>בחר תמונה</strong>
              <small>פתח אירוע מהגלריה ובחר את הפריים שדורש בדיקה.</small>
            </div>
          </article>
          <article>
            <span className={styles.workflowIndex}>02</span>
            <div>
              <strong>כוונן במדויק</strong>
              <small>חשיפה, טמפרטורה וגוון נשמרים כטיוטה בזמן העבודה.</small>
            </div>
          </article>
          <article>
            <span className={styles.workflowIndex}>03</span>
            <div>
              <strong>שמור או ייצא</strong>
              <small>אשר את העריכה או ייצא XMP מוכן להמשך ב-Lightroom.</small>
            </div>
          </article>
        </section>
      </div>
    );
  }

  const hasComparison =
    learningSource === "jpeg" ? showJpegPreview : showIllustration;
  const split = holdOriginal ? 100 : hasComparison ? compare : 0;
  const previewStyle = illustrationStyle(
    current,
    showIllustration && !holdOriginal,
  );
  const jpegPreviewStyle = jpegIllustrationStyle(
    jpegControls,
    showJpegPreview && !holdOriginal,
  );

  return (
    <div className={styles.room}>
      <WorkspaceBar
        kicker="חדר עריכה"
        title={file.filename}
        detail={learningSource === "jpeg" ? "JPEG" : "RAW"}
        counter={`${index + 1} / ${files.length}`}
      >
        <button className={styles.navStep} type="button" onClick={() => move(-1)} aria-label="תמונה קודמת">‹</button>
        <button className={styles.navStep} type="button" onClick={() => move(1)} aria-label="תמונה הבאה">›</button>
      </WorkspaceBar>
      <div className={styles.workspace}>
      <section className={styles.stage}>
        <div
          ref={frameRef}
          className={styles.frame}
          onPointerDown={(event) => {
            if (!hasComparison) return;
            updateCompare(event.clientX);
          }}
        >
          <CameraPreview
            eventId={selection.eventId}
            fingerprint={file.fingerprint}
            alt={`מקור ${file.filename}`}
            className={styles.photo}
          />
          {learningSource === "jpeg" && showJpegPreview ? (
            <>
              <CameraPreview
                eventId={selection.eventId}
                fingerprint={file.fingerprint}
                alt={`המחשת JPEG ${file.filename}`}
                className={styles.photoAfter}
                style={{
                  ...jpegPreviewStyle,
                  clipPath: `inset(0 0 0 ${split}%)`,
                }}
              />
              {!holdOriginal && (
                <>
                  <span
                    className={styles.warmthOverlay}
                    style={{
                      ...jpegPreviewStyle,
                      clipPath: `inset(0 0 0 ${split}%)`,
                    }}
                    aria-hidden="true"
                  />
                  <span
                    className={styles.tintOverlay}
                    style={{
                      ...jpegPreviewStyle,
                      clipPath: `inset(0 0 0 ${split}%)`,
                    }}
                    aria-hidden="true"
                  />
                </>
              )}
              <JpegRenderedPreview
                eventId={selection.eventId}
                fingerprint={file.fingerprint}
                controls={jpegControls}
                alt={`JPEG render ${file.filename}`}
                className={styles.photoAfter}
                style={{
                  clipPath: `inset(0 0 0 ${split}%)`,
                }}
              />
            </>
          ) : showIllustration ? (
            <>
              <CameraPreview
                eventId={selection.eventId}
                fingerprint={file.fingerprint}
                alt={`המחשה ${file.filename}`}
                className={styles.photoAfter}
                style={{
                  ...previewStyle,
                  clipPath: `inset(0 0 0 ${split}%)`,
                }}
              />
              {!holdOriginal && (
                <span
                  className={styles.tintOverlay}
                  style={{
                    ...previewStyle,
                    clipPath: `inset(0 0 0 ${split}%)`,
                  }}
                  aria-hidden="true"
                />
              )}
            </>
          ) : null}
          <span className={`${styles.badge} ${styles.beforeBadge}`}>מקור</span>
          {hasComparison && (
            <span className={`${styles.badge} ${styles.afterBadge}`}>
              המחשה
            </span>
          )}
          {hasComparison && (
            <button
              type="button"
              className={styles.handle}
              style={{ left: `${split}%` }}
              aria-label="ידית השוואה"
              onPointerDown={(event) => {
                event.preventDefault();
                event.currentTarget.setPointerCapture(event.pointerId);
                updateCompare(event.clientX);
              }}
              onPointerMove={(event) => {
                if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
                updateCompare(event.clientX);
              }}
            >
              <span className={styles.handleLine} />
              <span className={styles.handleGrip}>↔</span>
            </button>
          )}
          {hasComparison && (
            <p className={styles.truth}>
              {learningSource === "jpeg"
                ? "המחשה מיידית · ה-render המדויק מתעדכן ברקע."
                : "תצוגה משוערת בלבד · התוצאה הסופית נקבעת ב-Lightroom."}
            </p>
          )}
        </div>

        <div className={styles.meta}>
          <p className={styles.fileName}>{file.filename}</p>
          <p className={styles.metaNote}>
            <bdi dir="ltr">{index + 1} / {files.length}</bdi>
          </p>
        </div>

        <div
          ref={filmstripRef}
          className={styles.filmstrip}
          aria-label="תמונות האירוע"
          onScroll={updateFilmstripWindow}
        >
          {files.map((item, itemIndex) => (
            <button
              key={item.fingerprint}
              ref={item.fingerprint === file.fingerprint ? activeThumbRef : null}
              type="button"
              className={item.fingerprint === file.fingerprint ? `${styles.thumb} ${styles.thumbActive}` : styles.thumb}
              onClick={() => openSelectedPhoto(item.fingerprint)}
              aria-label={item.filename}
            >
              {itemIndex >= filmstripWindow.start && itemIndex <= filmstripWindow.end && (
                <CameraPreview
                  eventId={selection.eventId}
                  fingerprint={item.fingerprint}
                  alt=""
                />
              )}
            </button>
          ))}
        </div>
        {learningSource !== "jpeg" && (
          <div className={styles.dock}>
            <div className={styles.dockCommit}>
              <button
                className={styles.saveButton}
                type="button"
                disabled={!ready || busy}
                onClick={() => void saveCurrentReview()}
              >
                {busy
                  ? "שומר…"
                  : suggestedRecipe && sameRecipe(current, suggestedRecipe)
                    ? "אשר עריכה"
                    : "שמור תיקון"}
              </button>
              <button
                className={styles.exportButton}
                type="button"
                disabled={!ready || busy}
                onClick={() => void exportCurrent()}
              >
                {busy ? "מייצא…" : "ייצוא XMP"}
              </button>
            </div>

            <div className={styles.dockTools}>
              <button
                className={styles.dockTool}
                type="button"
                onClick={() => void chooseOutput()}
              >
                <span className={styles.dockToolIcon} aria-hidden="true">⌑</span>
                {outputDir ? "החלף תיקיית ייצוא" : "תיקיית ייצוא"}
              </button>
              <span className={styles.dockDivider} aria-hidden="true" />
              <button
                className={styles.dockTool}
                type="button"
                disabled={!suggestedRecipe}
                onClick={() => suggestedRecipe && applyRecipe(suggestedRecipe, true)}
              >
                <span className={styles.dockToolIcon} aria-hidden="true">↺</span>
                איפוס ל-ProGrapher
              </button>
              <button
                className={styles.dockTool}
                type="button"
                disabled={history.length === 0}
                onClick={undo}
              >
                <span className={styles.dockToolIcon} aria-hidden="true">↶</span>
                בטל שינוי
              </button>
            </div>
          </div>
        )}
      </section>

      <aside className={styles.panel}>
        {learningSource === "jpeg" ? (
          <div className={styles.panelBody}>
            <div className={styles.panelHeading}>
              <h2 className={styles.panelTitle}>עריכת JPEG</h2>
              <div className={styles.panelHeadingActions}>
                <button
                  type="button"
                  className={
                    showJpegPreview
                      ? `${styles.previewToggle} ${styles.previewToggleOn}`
                      : styles.previewToggle
                  }
                  aria-pressed={showJpegPreview}
                  title="תצוגת JPEG אמיתית — מופקת על ידי מנוע ה-render המשותף"
                  onClick={() => setShowJpegPreview((value) => !value)}
                >
                  <span className={styles.previewToggleLabel}>תצוגה מקדימה</span>
                  <span className={styles.previewSwitch} aria-hidden="true">
                    <span />
                  </span>
                </button>
              </div>
            </div>

            <p className={styles.keys}>
              {sheetNote}
            </p>

            <div className={styles.jpegUtilityRow}>
              <button
                type="button"
                className={styles.jpegResetButton}
                onClick={resetJpegControls}
                disabled={
                  jpegControls.brightness === 0 &&
                  jpegControls.contrast === 0 &&
                  jpegControls.warmth === 0 &&
                  jpegControls.tint === 0
                }
              >
                <span className={styles.jpegResetIcon} aria-hidden="true">↺</span>
                <span>איפוס ערכים</span>
              </button>
            </div>

            <details className={styles.group} open>
              <summary>אור</summary>
              <div className={styles.groupBody}>
                <div className={styles.slider}>
                  <div className={styles.sliderHeader}>
                    <span>בהירות</span>
                    <bdi className={styles.sliderValue}>
                      {jpegControls.brightness >= 0 ? "+" : ""}
                      {jpegControls.brightness}
                    </bdi>
                  </div>
                  <input
                    className={`${styles.range} ${styles.exposureRange}`}
                    type="range"
                    min={-100}
                    max={100}
                    step={1}
                    value={jpegControls.brightness}
                    aria-label="בהירות JPEG"
                    onChange={(event) =>
                      updateJpegControl(
                        "brightness",
                        Number(event.target.value),
                      )
                    }
                  />
                  <div className={styles.rangeHint} aria-hidden="true">
                    <span>כהה</span><span>ניטרלי</span><span>בהיר</span>
                  </div>
                </div>

                <div className={styles.slider}>
                  <div className={styles.sliderHeader}>
                    <span>ניגודיות</span>
                    <bdi className={styles.sliderValue}>
                      {jpegControls.contrast >= 0 ? "+" : ""}
                      {jpegControls.contrast}
                    </bdi>
                  </div>
                  <input
                    className={styles.range}
                    type="range"
                    min={-100}
                    max={100}
                    step={1}
                    value={jpegControls.contrast}
                    aria-label="ניגודיות JPEG"
                    onChange={(event) =>
                      updateJpegControl(
                        "contrast",
                        Number(event.target.value),
                      )
                    }
                  />
                  <div className={styles.rangeHint} aria-hidden="true">
                    <span>רך</span><span>ניטרלי</span><span>חזק</span>
                  </div>
                </div>
              </div>
            </details>

            <details className={styles.group} open>
              <summary>צבע</summary>
              <div className={styles.groupBody}>
                <div className={styles.slider}>
                  <div className={styles.sliderHeader}>
                    <span>חום צבע</span>
                    <bdi className={styles.sliderValue}>
                      {jpegControls.warmth >= 0 ? "+" : ""}
                      {jpegControls.warmth}
                    </bdi>
                  </div>
                  <input
                    className={`${styles.range} ${styles.temperatureRange}`}
                    type="range"
                    min={-100}
                    max={100}
                    step={1}
                    value={jpegControls.warmth}
                    aria-label="חום צבע JPEG"
                    onChange={(event) =>
                      updateJpegControl(
                        "warmth",
                        Number(event.target.value),
                      )
                    }
                  />
                  <div className={styles.rangeHint} aria-hidden="true">
                    <span>קר</span><span>ניטרלי</span><span>חם</span>
                  </div>
                </div>

                <div className={styles.slider}>
                  <div className={styles.sliderHeader}>
                    <span>ירוק ↔ מג׳נטה</span>
                    <bdi className={styles.sliderValue}>
                      {jpegControls.tint >= 0 ? "+" : ""}
                      {jpegControls.tint}
                    </bdi>
                  </div>
                  <input
                    className={`${styles.range} ${styles.tintRange}`}
                    type="range"
                    min={-100}
                    max={100}
                    step={1}
                    value={jpegControls.tint}
                    aria-label="Green Magenta JPEG"
                    onChange={(event) =>
                      updateJpegControl(
                        "tint",
                        Number(event.target.value),
                      )
                    }
                  />
                  <div className={styles.rangeHint} aria-hidden="true">
                    <span>ירוק</span><span>ניטרלי</span><span>מג׳נטה</span>
                  </div>
                </div>
              </div>
            </details>

            <p className={styles.keys}>
              ערכי JPEG הם יחידות נורמליות ‎-100…+100. חום צבע אינו Kelvin,
              והגוון אינו ערך Lightroom/Camera Raw. B מציג את המקור.
            </p>
          </div>
        ) : (
        <div className={styles.panelBody}>
          <div className={styles.panelHeading}>
            <h2 className={styles.panelTitle}>עריכה</h2>
            <button
              type="button"
              className={
                showIllustration
                  ? `${styles.previewToggle} ${styles.previewToggleOn}`
                  : styles.previewToggle
              }
              aria-pressed={showIllustration}
              title="תצוגה משוערת בלבד — התוצאה הסופית נקבעת ב-Lightroom"
              onClick={() => setShowIllustration((value) => !value)}
            >
              <span className={styles.previewToggleLabel}>תצוגה מקדימה</span>
              <span className={styles.previewSwitch} aria-hidden="true">
                <span />
              </span>
            </button>
          </div>
          <div className={styles.reference}>
            <div>
              <span>עריכת הצלם</span>
              <bdi>{formatRecipe(file.photographer && file.photographer.exposure != null && file.photographer.temperature != null && file.photographer.tint != null ? {
                exposure: file.photographer.exposure,
                temperature: file.photographer.temperature,
                tint: file.photographer.tint,
              } : null)}</bdi>
            </div>
            <div>
              <span>הצעת ProGrapher</span>
              <bdi>{formatRecipe(file.suggested && file.suggested.exposure != null && file.suggested.temperature != null && file.suggested.tint != null ? {
                exposure: file.suggested.exposure,
                temperature: file.suggested.temperature,
                tint: file.suggested.tint,
              } : null)}</bdi>
            </div>
            {file.saved_review && (
              <div>
                <span>עריכה שמורה</span>
                <bdi>{formatRecipe(
                  file.saved_review.exposure != null &&
                  file.saved_review.temperature != null &&
                  file.saved_review.tint != null
                    ? {
                        exposure: file.saved_review.exposure,
                        temperature: file.saved_review.temperature,
                        tint: file.saved_review.tint,
                      }
                    : null,
                )}</bdi>
              </div>
            )}
          </div>

          <details className={styles.group} open>
            <summary>אור</summary>
            <div className={styles.groupBody}>
          <div className={styles.slider}>
            <div className={styles.sliderHeader}>
              <span>חשיפה</span>
              <span className={styles.sliderControls}>
                <bdi className={styles.sliderValue}>{exposure >= 0 ? "+" : ""}{exposure.toFixed(2)}</bdi>
                <button
                  type="button"
                  className={styles.sliderReset}
                  title="איפוס להצעת ProGrapher"
                  aria-label="איפוס חשיפה להצעת ProGrapher"
                  disabled={!ready || !suggestedRecipe || exposure === suggestedRecipe.exposure}
                  onClick={() => suggestedRecipe && applyRecipe({ ...current, exposure: suggestedRecipe.exposure }, true)}
                >
                  ↶
                </button>
              </span>
            </div>
            <input
              className={`${styles.range} ${styles.exposureRange}`}
              type="range"
              min={-5}
              max={5}
              step={0.01}
              value={exposure}
              disabled={!ready}
              aria-label="חשיפה"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => {
                const value = Number(event.target.value);
                const recipe = { ...current, exposure: value };
                setExposure(value);
                if (selection && file) {
                  setDraft(selection.eventId, file.fingerprint, recipe);
                }
                setDirty(true);
              }}
            />
            <div className={styles.rangeHint} aria-hidden="true">
              <span>כהה</span><span>ניטרלי</span><span>בהיר</span>
            </div>
          </div>
            </div>
          </details>
          <details className={styles.group} open>
            <summary>צבע</summary>
            <div className={styles.groupBody}>
          <div className={styles.slider}>
            <div className={styles.sliderHeader}>
              <span>טמפרטורה</span>
              <span className={styles.sliderControls}>
                <bdi className={styles.sliderValue}>{temperature} K</bdi>
                <button
                  type="button"
                  className={styles.sliderReset}
                  title="איפוס להצעת ProGrapher"
                  aria-label="איפוס טמפרטורה להצעת ProGrapher"
                  disabled={!ready || !suggestedRecipe || temperature === suggestedRecipe.temperature}
                  onClick={() => suggestedRecipe && applyRecipe({ ...current, temperature: suggestedRecipe.temperature }, true)}
                >
                  ↶
                </button>
              </span>
            </div>
            <input
              className={`${styles.range} ${styles.temperatureRange}`}
              type="range"
              min={2000}
              max={50000}
              step={50}
              value={temperature}
              disabled={!ready}
              aria-label="טמפרטורה"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => {
                const value = Number(event.target.value);
                const recipe = { ...current, temperature: value };
                setTemperature(value);
                if (selection && file) {
                  setDraft(selection.eventId, file.fingerprint, recipe);
                }
                setDirty(true);
              }}
            />
            <div className={styles.rangeHint} aria-hidden="true">
              <span>קר</span><span>ניטרלי</span><span>חם</span>
            </div>
          </div>
          <div className={styles.slider}>
            <div className={styles.sliderHeader}>
              <span>גוון</span>
              <span className={styles.sliderControls}>
                <bdi className={styles.sliderValue}>{tint >= 0 ? "+" : ""}{tint}</bdi>
                <button
                  type="button"
                  className={styles.sliderReset}
                  title="איפוס להצעת ProGrapher"
                  aria-label="איפוס גוון להצעת ProGrapher"
                  disabled={!ready || !suggestedRecipe || tint === suggestedRecipe.tint}
                  onClick={() => suggestedRecipe && applyRecipe({ ...current, tint: suggestedRecipe.tint }, true)}
                >
                  ↶
                </button>
              </span>
            </div>
            <input
              className={`${styles.range} ${styles.tintRange}`}
              type="range"
              min={-150}
              max={150}
              step={1}
              value={tint}
              disabled={!ready}
              aria-label="גוון"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => {
                const value = Number(event.target.value);
                const recipe = { ...current, tint: value };
                setTint(value);
                if (selection && file) {
                  setDraft(selection.eventId, file.fingerprint, recipe);
                }
                setDirty(true);
              }}
            />
            <div className={styles.rangeHint} aria-hidden="true">
              <span>ירוק</span><span>ניטרלי</span><span>מג׳נטה</span>
            </div>
          </div>
            </div>
          </details>
          {["נוכחות", "עקומת טון", "HSL / Color Mixer", "פירוט", "עדשה", "טרנספורם", "אפקטים"].map((group) => (
            <details key={group} className={styles.group}>
              <summary>{group}</summary>
              <p className={styles.groupPending}>הקבוצה שמורה למבנה Lightroom. אין בה ערכים כל עוד אין מתכון אמיתי.</p>
            </details>
          ))}

          <p className={styles.keys}>חצים למעבר · Enter לייצוא · שינויים שלא נשמרו נשמרים כטיוטה במעבר · ⌘Z או Ctrl+Z לביטול · B להחזיק את המקור</p>
          {message && <p className={`${styles.status} ${styles.ok}`} role="status">{message}</p>}
          {error && <p className={`${styles.status} ${styles.error}`} role="alert">{error}</p>}
        </div>
        )}

        {learningSource === "jpeg" && (
        <div className={styles.actions}>
          <button
            className={styles.primary}
            type="button"
            onClick={returnToGallery}
          >
            חזרה לגלריה
          </button>
        </div>
        )}

      </aside>
      </div>
    </div>
  );
}
