"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import CameraPreview from "@/features/review/CameraPreview";
import {
  exportRecipes,
  getReviewSheet,
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
  return `${recipe.exposure.toFixed(2)} / ${recipe.temperature} K / ${recipe.tint}`;
}

function illustrationStyle(recipe: Recipe, enabled: boolean): CSSProperties {
  if (!enabled) return {};
  const brightness = Math.min(1.8, Math.max(0.45, 1 + recipe.exposure * 0.18));
  const warmth = Math.max(-40, Math.min(40, (recipe.temperature - 5500) / 80));
  return {
    ["--preview-brightness" as string]: String(brightness),
    ["--preview-sepia" as string]: warmth > 0 ? "0.25" : "0",
    ["--preview-saturate" as string]: "1.05",
    ["--preview-hue" as string]: `${-warmth * 0.35}deg`,
  };
}

export default function DarkroomScreen() {
  const { selection, outputDir, setOutputDir, openPhoto, openGallery } = useTestingNav();
  const frameRef = useRef<HTMLDivElement>(null);
  const [files, setFiles] = useState<ReviewFile[]>([]);
  const [learningSource, setLearningSource] = useState<LearningSource>("raw");
  const [sheetNote, setSheetNote] = useState("");
  const [exposure, setExposure] = useState(0);
  const [temperature, setTemperature] = useState(5500);
  const [tint, setTint] = useState(0);
  const [ready, setReady] = useState(false);
  const [compare, setCompare] = useState(62);
  const [showIllustration, setShowIllustration] = useState(false);
  const [holdOriginal, setHoldOriginal] = useState(false);
  const [history, setHistory] = useState<Recipe[]>([]);
  const [future, setFuture] = useState<Recipe[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dragOrigin = useRef<Recipe | null>(null);

  const file = files.find((item) => item.fingerprint === selection?.fingerprint) ?? null;
  const index = file ? files.findIndex((item) => item.fingerprint === file.fingerprint) : -1;
  const current = useMemo<Recipe>(
    () => ({ exposure, temperature, tint }),
    [exposure, temperature, tint],
  );

  const suggestion = file?.saved_review ?? file?.suggested ?? null;
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
  }, [current]);

  useEffect(() => {
    if (!selection) {
      setFiles([]);
      setReady(false);
      return;
    }

    void getReviewSheet(selection.eventId)
      .then((sheet) => {
        setFiles(sheet.files);
        setLearningSource(sheet.learning_source ?? "raw");
        setSheetNote(sheet.note);
        const match = sheet.files.find(
          (item) => item.fingerprint === selection.fingerprint,
        );
        const source = match?.saved_review ?? match?.suggested;
        if (
          source?.exposure != null &&
          source.temperature != null &&
          source.tint != null
        ) {
          setExposure(source.exposure);
          setTemperature(source.temperature);
          setTint(source.tint);
          setReady(true);
        } else {
          setReady(false);
        }
        setHistory([]);
        setFuture([]);
        setError("");
        setMessage("");
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "טעינת התמונה נכשלה.");
      });
  }, [selection]);

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

  async function save() {
    if (!selection || !file || !ready) return;
    const folder = outputDir || (await chooseOutput());
    if (!folder) return;
    const decision =
      suggestedRecipe && sameRecipe(current, suggestedRecipe) ? "approved" : "corrected";
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
        setMessage(decision === "approved" ? "המתכון אושר ונכתב." : "התיקון נכתב.");
      } else {
        setError(item?.reason || "הייצוא לא נכתב.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "הייצוא נכשל.");
    } finally {
      setBusy(false);
    }
  }

  function move(step: number) {
    if (!selection || index < 0) return;
    const next = files[index + step];
    if (!next) return;
    openPhoto(selection.eventId, next.fingerprint);
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
        openGallery();
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
        void save();
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

  if (!selection || !file) {
    return (
      <div className={styles.empty}>
        <div>
          <h2>חדר עריכה</h2>
          <p>בוחרים תמונה מהגלריה. כאן מאשרים או מתקנים, ואז מייצאים ל-Lightroom.</p>
          <button className={styles.primary} type="button" onClick={openGallery}>
            אל הגלריה
          </button>
        </div>
      </div>
    );
  }

  const split = holdOriginal ? 100 : showIllustration ? compare : 0;
  const previewStyle = illustrationStyle(current, showIllustration && !holdOriginal);

  return (
    <div className={styles.room}>
      <section className={styles.stage}>
        <div
          ref={frameRef}
          className={styles.frame}
          onPointerDown={(event) => {
            if (!showIllustration) return;
            updateCompare(event.clientX);
          }}
        >
          <CameraPreview
            eventId={selection.eventId}
            fingerprint={file.fingerprint}
            alt={`מקור ${file.filename}`}
            className={styles.photo}
          />
          {showIllustration && (
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
          )}
          <span className={`${styles.badge} ${styles.beforeBadge}`}>מקור</span>
          {showIllustration && (
            <span className={`${styles.badge} ${styles.afterBadge}`}>המחשה</span>
          )}
          {showIllustration && (
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
          {showIllustration && (
            <p className={styles.truth}>המחשה גסה בלבד. הצבע הסופי נקבע ב-Lightroom.</p>
          )}
        </div>

        <div className={styles.meta}>
          <p className={styles.fileName}>{file.filename}</p>
          <p className={styles.metaNote}>
            {index + 1} / {files.length}
          </p>
        </div>

        <div className={styles.filmstrip} aria-label="תמונות האירוע">
          {files.map((item, itemIndex) => (
            <button
              key={item.fingerprint}
              type="button"
              className={item.fingerprint === file.fingerprint ? `${styles.thumb} ${styles.thumbActive}` : styles.thumb}
              onClick={() => openPhoto(selection.eventId, item.fingerprint)}
              aria-label={item.filename}
            >
              {Math.abs(itemIndex - index) <= 12 && (
                <CameraPreview
                  eventId={selection.eventId}
                  fingerprint={item.fingerprint}
                  alt=""
                />
              )}
            </button>
          ))}
        </div>
      </section>

      <aside className={styles.panel}>
        {learningSource === "jpeg" ? (
          <div className={styles.panelBody}>
            <h2 className={styles.panelTitle}>פרופיל JPEG</h2>
            <p className={styles.keys}>{sheetNote}</p>
            <p className={styles.keys}>
              לפרופיל הזה אין סליידרים של Lightroom ואין ייצוא XMP.
            </p>
          </div>
        ) : (
        <div className={styles.panelBody}>
          <h2 className={styles.panelTitle}>המתכון</h2>
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
              <span>הצעת הבסיס</span>
              <bdi>{formatRecipe(file.baseline && file.baseline.exposure != null && file.baseline.temperature != null && file.baseline.tint != null ? {
                exposure: file.baseline.exposure,
                temperature: file.baseline.temperature,
                tint: file.baseline.tint,
              } : null)}</bdi>
            </div>
          </div>

          <label className={styles.slider}>
            <span className={styles.sliderHeader}>
              חשיפה
              <bdi>{exposure.toFixed(2)}</bdi>
            </span>
            <input
              type="range"
              min={-5}
              max={5}
              step={0.01}
              value={exposure}
              disabled={!ready}
              aria-label="חשיפה"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => setExposure(Number(event.target.value))}
            />
          </label>
          <label className={`${styles.slider} ${styles.temperature}`}>
            <span className={styles.sliderHeader}>
              טמפרטורה
              <bdi>{temperature} K</bdi>
            </span>
            <input
              type="range"
              min={2000}
              max={50000}
              step={50}
              value={temperature}
              disabled={!ready}
              aria-label="טמפרטורה"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => setTemperature(Number(event.target.value))}
            />
          </label>
          <label className={styles.slider}>
            <span className={styles.sliderHeader}>
              גוון
              <bdi>{tint}</bdi>
            </span>
            <input
              type="range"
              min={-150}
              max={150}
              step={1}
              value={tint}
              disabled={!ready}
              aria-label="גוון"
              onPointerDown={rememberBeforeDrag}
              onPointerUp={commitDrag}
              onChange={(event) => setTint(Number(event.target.value))}
            />
          </label>

          <button
            type="button"
            className={showIllustration ? `${styles.toggle} ${styles.toggleOn}` : styles.toggle}
            onClick={() => setShowIllustration((value) => !value)}
          >
            {showIllustration ? "ההמחשה הגסה פעילה" : "הצג המחשה גסה"}
          </button>
          <p className={styles.keys}>חצים למעבר · Enter לייצוא · ⌘Z או Ctrl+Z לביטול · B להחזיק את המקור</p>
          {message && <p className={`${styles.status} ${styles.ok}`} role="status">{message}</p>}
          {error && <p className={`${styles.status} ${styles.error}`} role="alert">{error}</p>}
        </div>
        )}

        {learningSource !== "jpeg" && (
        <div className={styles.actions}>
          <button className={styles.secondary} type="button" onClick={() => void chooseOutput()}>
            {outputDir ? "החלפת תיקיית ייצוא" : "בחירת תיקיית ייצוא"}
          </button>
          <button
            className={styles.secondary}
            type="button"
            disabled={!suggestedRecipe}
            onClick={() => suggestedRecipe && applyRecipe(suggestedRecipe, true)}
          >
            איפוס להצעה
          </button>
          <button
            className={styles.secondary}
            type="button"
            disabled={history.length === 0}
            onClick={undo}
          >
            ביטול
          </button>
          <button
            className={styles.primary}
            type="button"
            disabled={!ready || busy}
            onClick={() => void save()}
          >
            {busy ? "כותב…" : suggestedRecipe && sameRecipe(current, suggestedRecipe) ? "אשר וייצא" : "תקן וייצא"}
          </button>
        </div>
        )}
      </aside>
    </div>
  );
}
