"use client";

import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  selectLightroomCatalog,
} from "@/features/profile/profile.api";
import {
  createTestingProfile,
  getTestingProfile,
  type LearningSource,
  type TestingProfile,
} from "@/features/testing/testing.api";
import {
  consumeTrainingEntry,
  loadCatalogBindings,
  saveCatalogBinding,
  type LearningMedia,
  type LearningMethod,
} from "@/features/training/learning-state";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import styles from "@/features/testing/testing.module.css";

function profileSource(media: LearningMedia): LearningSource {
  return media === "jpeg" ? "jpeg" : "raw";
}

function mediaLabel(media: LearningMedia) {
  return media === "jpeg" ? "JPEG" : "RAW";
}

async function fetchExistingProfile(
  nextMedia: LearningMedia,
): Promise<TestingProfile | null> {
  try {
    return await getTestingProfile(profileSource(nextMedia));
  } catch {
    return null;
  }
}

export default function TrainingScreen() {
  const openView = useWorkspaceNav();

  const [media, setMedia] = useState<LearningMedia | null>(null);
  const [method, setMethod] = useState<LearningMethod | null>(null);
  const [profile, setProfile] = useState<TestingProfile | null>(null);

  const [sourceRoot, setSourceRoot] = useState("");
  const [editsRoot, setEditsRoot] = useState("");
  const [catalogPath, setCatalogPath] = useState("");
  const [catalogRecords, setCatalogRecords] = useState<number | null>(null);

  const [checkedNow, setCheckedNow] = useState(false);
  const [catalogSaved, setCatalogSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const entry = consumeTrainingEntry();
    if (!entry) return;

    let cancelled = false;

    void fetchExistingProfile(entry.media).then((existing) => {
      if (cancelled) return;

      setProfile(existing);
      setMedia(entry.media);
      setMethod(entry.method ?? null);

      if (entry.method === "pairs" && existing) {
        setSourceRoot(existing.raw_root);
        setEditsRoot(existing.edits_root);
      }

      if (entry.method === "catalog") {
        const binding = loadCatalogBindings()[entry.media];
        if (binding) {
          setSourceRoot(binding.sourceRoot);
          setCatalogPath(binding.catalogPath);
          setCatalogRecords(binding.catalogPhotoRecords);
          setCatalogSaved(true);
        }
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  async function chooseMedia(nextMedia: LearningMedia) {
    setMedia(nextMedia);
    setMethod(null);
    setSourceRoot("");
    setEditsRoot("");
    setCatalogPath("");
    setCatalogRecords(null);
    setCheckedNow(false);
    setCatalogSaved(false);
    setError("");
    setProfile(await fetchExistingProfile(nextMedia));
  }

  function chooseMethod(nextMethod: LearningMethod) {
    if (!media) return;

    setMethod(nextMethod);
    setError("");
    setCheckedNow(false);

    if (nextMethod === "pairs") {
      setSourceRoot(profile?.raw_root ?? "");
      setEditsRoot(profile?.edits_root ?? "");
      setCatalogPath("");
      setCatalogRecords(null);
      setCatalogSaved(false);
      return;
    }

    const binding = loadCatalogBindings()[media];
    setSourceRoot(binding?.sourceRoot ?? "");
    setEditsRoot("");
    setCatalogPath(binding?.catalogPath ?? "");
    setCatalogRecords(binding?.catalogPhotoRecords ?? null);
    setCatalogSaved(Boolean(binding));
  }

  function backOneStep() {
    setError("");
    setCheckedNow(false);

    if (method) {
      setMethod(null);
      setSourceRoot("");
      setEditsRoot("");
      setCatalogPath("");
      setCatalogRecords(null);
      setCatalogSaved(false);
      return;
    }

    if (media) {
      setMedia(null);
      setProfile(null);
      return;
    }

    openView("profile");
  }

  async function chooseFolder(target: "source" | "edits") {
    if (!media || !method) return;

    const selected = await open({
      directory: true,
      multiple: false,
      title:
        target === "source"
          ? media === "jpeg"
            ? "בחר תיקיית JPEG מקור"
            : "בחר תיקיית RAW מקור"
          : media === "jpeg"
            ? "בחר תיקיית JPEG ערוך"
            : "בחר תיקיית XMP / עריכות Lightroom",
    });

    if (!selected || Array.isArray(selected)) return;

    setError("");
    setCheckedNow(false);
    setCatalogSaved(false);

    if (target === "source") {
      setSourceRoot(selected);
    } else {
      setEditsRoot(selected);
    }
  }

  async function chooseCatalog() {
    if (!media) return;

    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר Lightroom Catalog",
      filters: [{ name: "Lightroom Catalog", extensions: ["lrcat"] }],
    });

    if (!selected || Array.isArray(selected)) return;

    setBusy(true);
    setError("");
    setCatalogSaved(false);

    try {
      const result = await selectLightroomCatalog(selected);
      setCatalogPath(selected);
      setCatalogRecords(
        result.selected_catalog?.catalog_photo_records ?? null,
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "לא ניתן לקרוא את קטלוג Lightroom.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function checkPairs() {
    if (!media || method !== "pairs") return;

    setBusy(true);
    setError("");
    setCheckedNow(false);

    try {
      const result = await createTestingProfile({
        raw_root: sourceRoot,
        edits_root: editsRoot,
        photographer_id: "local-photographer",
        event_label: "profile-learning",
        learning_source: profileSource(media),
      });
      setProfile(result);
      setCheckedNow(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לבדוק את החומר.",
      );
    } finally {
      setBusy(false);
    }
  }

  function saveCatalogMaterial() {
    if (!media || method !== "catalog" || !sourceRoot || !catalogPath) return;

    saveCatalogBinding(media, {
      sourceRoot,
      catalogPath,
      catalogPhotoRecords: catalogRecords,
      updatedAt: new Date().toISOString(),
    });

    setCatalogSaved(true);
  }

  const currentStep = !media ? 1 : !method ? 2 : 3;

  const materialReady =
    method === "pairs"
      ? Boolean(sourceRoot && editsRoot)
      : Boolean(sourceRoot && catalogPath);

  const methodOptions = useMemo(() => {
    if (!media) return null;

    if (media === "jpeg") {
      return {
        pairs: {
          title: "זוגות לפני + אחרי",
          copy: "JPEG מקור מול JPEG סופי שכבר ערכת.",
          tag: "PAIRS",
        },
        catalog: {
          title: "Lightroom Catalog",
          copy: "תיקיית JPEG מקור יחד עם קובץ LRCAT.",
          tag: "LRCAT",
        },
      };
    }

    return {
      pairs: {
        title: "RAW + עריכות Lightroom",
        copy: "RAW מקור יחד עם XMP / עריכות תואמות.",
        tag: "XMP",
      },
      catalog: {
        title: "Lightroom Catalog",
        copy: "תיקיית RAW מקור יחד עם קובץ LRCAT.",
        tag: "LRCAT",
      },
    };
  }, [media]);

  return (
    <main className={styles.screen}>
      <header className={styles.header}>
        <button
          className={styles.backButton}
          type="button"
          onClick={backOneStep}
        >
          → {currentStep === 1 ? "חזרה לפרופיל" : "חזרה"}
        </button>

        <div>
          <span className={styles.eyebrow}>בניית הפרופיל</span>
          <h1>
            {media
              ? `למידה לפי ${mediaLabel(media)}`
              : "איך נלמד את העריכה שלך?"}
          </h1>
          <p>
            בכל שלב מוצגת רק הבחירה שצריך לקבל עכשיו.
          </p>
        </div>
      </header>

      <nav className={styles.progress} aria-label="שלבי הגדרת הלמידה">
        <div className={currentStep >= 1 ? styles.progressActive : styles.progressItem}>
          <span>1</span>
          <strong>סוג קובץ</strong>
        </div>
        <div className={currentStep >= 2 ? styles.progressActive : styles.progressItem}>
          <span>2</span>
          <strong>שיטת למידה</strong>
        </div>
        <div className={currentStep >= 3 ? styles.progressActive : styles.progressItem}>
          <span>3</span>
          <strong>בחירת חומר</strong>
        </div>
      </nav>

      {currentStep === 1 ? (
        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>שלב 1</span>
            <h2>בחר סוג קובץ</h2>
            <p>זו הבחירה היחידה שצריך לעשות כרגע.</p>
          </div>

          <div className={styles.mediaGrid}>
            <button
              className={styles.mediaCard}
              type="button"
              onClick={() => void chooseMedia("jpeg")}
            >
              <span className={styles.mediaMark}>JPEG</span>
              <div>
                <h3>למידה לפי JPEG</h3>
                <p>מתאים לזוגות לפני/אחרי או ל־Lightroom Catalog.</p>
              </div>
              <span className={styles.cardArrow} aria-hidden="true">←</span>
            </button>

            <button
              className={styles.mediaCard}
              type="button"
              onClick={() => void chooseMedia("raw")}
            >
              <span className={styles.mediaMark}>RAW</span>
              <div>
                <h3>למידה לפי RAW</h3>
                <p>מתאים לעריכות Lightroom/XMP או ל־Lightroom Catalog.</p>
              </div>
              <span className={styles.cardArrow} aria-hidden="true">←</span>
            </button>
          </div>
        </section>
      ) : null}

      {currentStep === 2 && media && methodOptions ? (
        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>שלב 2 · {mediaLabel(media)}</span>
            <h2>איך נלמד?</h2>
            <p>בחר את סוג החומר שכבר קיים אצלך.</p>
          </div>

          <div className={styles.methodGrid}>
            <button
              className={styles.methodCard}
              type="button"
              onClick={() => chooseMethod("pairs")}
            >
              <span className={styles.methodTag}>{methodOptions.pairs.tag}</span>
              <div>
                <h3>{methodOptions.pairs.title}</h3>
                <p>{methodOptions.pairs.copy}</p>
              </div>
              <span className={styles.cardArrow} aria-hidden="true">←</span>
            </button>

            <button
              className={styles.methodCard}
              type="button"
              onClick={() => chooseMethod("catalog")}
            >
              <span className={styles.methodTag}>{methodOptions.catalog.tag}</span>
              <div>
                <h3>{methodOptions.catalog.title}</h3>
                <p>{methodOptions.catalog.copy}</p>
              </div>
              <span className={styles.cardArrow} aria-hidden="true">←</span>
            </button>
          </div>
        </section>
      ) : null}

      {currentStep === 3 && media && method ? (
        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>
              שלב 3 · {mediaLabel(media)} ·{" "}
              {method === "pairs" ? "קבצי עריכה" : "Lightroom Catalog"}
            </span>
            <h2>בחר את החומר</h2>
            <p>שני מקורות בלבד. כל השאר נשאר מאחורי הקלעים.</p>
          </div>

          <div className={styles.materialGrid}>
            <button
              className={
                sourceRoot
                  ? `${styles.materialCard} ${styles.materialSelected}`
                  : styles.materialCard
              }
              type="button"
              onClick={() => void chooseFolder("source")}
            >
              <span className={styles.materialIcon} aria-hidden="true">
                {sourceRoot ? "✓" : "＋"}
              </span>
              <div>
                <span className={styles.materialLabel}>
                  {media === "jpeg" ? "JPEG מקור" : "RAW מקור"}
                </span>
                <strong>
                  {sourceRoot ? "תיקיית המקור נבחרה" : "בחר תיקיית מקור"}
                </strong>
                <small>{sourceRoot || "לא נבחרה תיקייה"}</small>
              </div>
            </button>

            {method === "pairs" ? (
              <button
                className={
                  editsRoot
                    ? `${styles.materialCard} ${styles.materialSelected}`
                    : styles.materialCard
                }
                type="button"
                onClick={() => void chooseFolder("edits")}
              >
                <span className={styles.materialIcon} aria-hidden="true">
                  {editsRoot ? "✓" : "＋"}
                </span>
                <div>
                  <span className={styles.materialLabel}>
                    {media === "jpeg" ? "JPEG ערוך" : "עריכות Lightroom / XMP"}
                  </span>
                  <strong>
                    {editsRoot ? "תיקיית העריכות נבחרה" : "בחר תיקיית עריכות"}
                  </strong>
                  <small>{editsRoot || "לא נבחרה תיקייה"}</small>
                </div>
              </button>
            ) : (
              <button
                className={
                  catalogPath
                    ? `${styles.materialCard} ${styles.materialSelected}`
                    : styles.materialCard
                }
                type="button"
                onClick={() => void chooseCatalog()}
                disabled={busy}
              >
                <span className={styles.materialIcon} aria-hidden="true">
                  {catalogPath ? "✓" : "＋"}
                </span>
                <div>
                  <span className={styles.materialLabel}>Lightroom Catalog</span>
                  <strong>
                    {catalogPath ? "הקטלוג נבחר" : "בחר קובץ LRCAT"}
                  </strong>
                  <small>{catalogPath || "לא נבחר קטלוג"}</small>
                </div>
              </button>
            )}
          </div>

          {error ? <div className={styles.error}>{error}</div> : null}

          <div className={styles.stageActions}>
            <button
              className={styles.secondaryButton}
              type="button"
              onClick={() => setMethod(null)}
            >
              שנה שיטת למידה
            </button>

            {method === "pairs" ? (
              <button
                className={styles.primaryButton}
                type="button"
                disabled={busy || !materialReady}
                onClick={() => void checkPairs()}
              >
                {busy ? "בודק…" : profile ? "בדוק מחדש" : "בדוק את החומר"}
              </button>
            ) : (
              <button
                className={styles.primaryButton}
                type="button"
                disabled={!materialReady}
                onClick={saveCatalogMaterial}
              >
                {catalogSaved ? "החומר נשמר" : "שמור את החומר"}
              </button>
            )}
          </div>

          {method === "pairs" && checkedNow && profile ? (
            <section className={styles.result}>
              <span className={styles.resultIcon} aria-hidden="true">✓</span>
              <div>
                <span className={styles.resultLabel}>בדיקת החומר הסתיימה</span>
                <h3>
                  {profile.usable_pairs.toLocaleString("he-IL")} זוגות מוכנים
                </h3>
                <p>
                  {profile.usable_pairs > 0
                    ? "החומר הוגדר למסלול ויופיע עכשיו בעמוד הפרופיל."
                    : "לא נמצאו עדיין זוגות שמישים. אפשר להחליף את החומר ולבדוק שוב."}
                </p>
              </div>
              <button type="button" onClick={() => openView("profile")}>
                חזרה לפרופיל
              </button>
            </section>
          ) : null}

          {method === "catalog" && catalogSaved ? (
            <section className={styles.result}>
              <span className={styles.resultIcon} aria-hidden="true">✓</span>
              <div>
                <span className={styles.resultLabel}>החומר הוגדר</span>
                <h3>
                  {catalogRecords !== null
                    ? `${catalogRecords.toLocaleString("he-IL")} רשומות בקטלוג`
                    : "Lightroom Catalog מוכן"}
                </h3>
                <p>
                  המקור והקטלוג נשמרו למסלול {mediaLabel(media)}. לא מוצג כאן
                  סטטוס אימון עד שקיים Brain מאומן בפועל.
                </p>
              </div>
              <button type="button" onClick={() => openView("profile")}>
                חזרה לפרופיל
              </button>
            </section>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
