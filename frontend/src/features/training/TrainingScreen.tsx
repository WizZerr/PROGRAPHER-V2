"use client";

import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { selectLightroomCatalog } from "@/features/profile/profile.api";
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
import RawTrainingView from "./RawTrainingView";
import JpegTrainingView from "./JpegTrainingView";

function profileSource(media: LearningMedia): LearningSource {
  return media === "jpeg" ? "jpeg" : "raw";
}

function mediaLabel(media: LearningMedia) {
  return media === "jpeg" ? "JPEG" : "RAW";
}

async function fetchExistingProfile(
  media: LearningMedia,
): Promise<TestingProfile | null> {
  try {
    return await getTestingProfile(profileSource(media));
  } catch {
    return null;
  }
}

export default function TrainingScreen() {
  const openView = useWorkspaceNav();
  const [entry] = useState(() => consumeTrainingEntry());
  const media = entry?.media ?? null;

  const [method, setMethod] = useState<LearningMethod | null>(
    entry?.method ?? null,
  );
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
    if (!media) return;

    let cancelled = false;

    void fetchExistingProfile(media).then((existing) => {
      if (cancelled) return;

      setProfile(existing);

      if ((method === "pairs" || method === "xmp") && existing) {
        setSourceRoot(existing.raw_root);
        setEditsRoot(existing.edits_root);
      }

      if (method === "catalog") {
        const binding = loadCatalogBindings()[media];
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
  }, [media, method]);

  function chooseMethod(nextMethod: LearningMethod) {
    if (!media) return;

    setMethod(nextMethod);
    setError("");
    setCheckedNow(false);

    if (nextMethod === "pairs" || nextMethod === "xmp") {
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

  async function checkPairedMaterial() {
    if (!media || (method !== "pairs" && method !== "xmp")) return;

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

  const methodOptions = useMemo(() => {
    if (!media) return null;

    if (media === "jpeg") {
      return {
        heading: "איך נלמד את ה־JPEG?",
        copy: "בחר את מסלול הלמידה שמתאים לחומר שכבר יש לך.",
        first: {
          method: "pairs" as const,
          tag: "PAIRS",
          title: "זוגות לפני + אחרי",
          copy: "JPEG מקור מול JPEG סופי שכבר ערכת.",
        },
        second: {
          method: "catalog" as const,
          tag: "LRCAT",
          title: "Lightroom Catalog",
          copy: "JPEG מקור יחד עם קטלוג Lightroom.",
        },
      };
    }

    return {
      heading: "איך נקרא את עריכות Lightroom?",
      copy: "זה עדיין מסלול RAW אחד. כאן בוחרים רק מאיפה לקרוא את העריכות.",
      first: {
        method: "xmp" as const,
        tag: "XMP",
        title: "קובצי XMP",
        copy: "RAW מקור יחד עם קובצי XMP תואמים.",
      },
      second: {
        method: "catalog" as const,
        tag: "LRCAT",
        title: "Lightroom Catalog",
        copy: "RAW מקור יחד עם קטלוג Lightroom.",
      },
    };
  }, [media]);

  if (!media || !methodOptions) {
    return (
      <main className={styles.screen}>
        <header className={styles.header}>
          <button
            className={styles.backButton}
            type="button"
            onClick={() => openView("profile")}
          >
            → חזרה לפרופיל
          </button>
          <div>
            <span className={styles.eyebrow}>בניית הפרופיל</span>
            <h1>בחר מסלול מהפרופיל שלך</h1>
            <p>למידת JPEG ו־RAW מתחילות מהכרטיס המתאים בעמוד הפרופיל.</p>
          </div>
        </header>

        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>לא נבחר מסלול</span>
            <h2>חזור לפרופיל ובחר JPEG או RAW</h2>
          </div>
          <div className={styles.stageActions}>
            <button
              className={styles.primaryButton}
              type="button"
              onClick={() => openView("profile")}
            >
              חזרה לפרופיל
            </button>
          </div>
        </section>
      </main>
    );
  }

  const currentStep = method ? 2 : 1;
  const pairedMethod = method === "pairs" || method === "xmp";
  const materialReady = pairedMethod
    ? Boolean(sourceRoot && editsRoot)
    : Boolean(sourceRoot && catalogPath);
  if (media === "raw" && method !== "pairs") {
    return (
      <RawTrainingView
        method={method}
        sourceRoot={sourceRoot}
        editsRoot={editsRoot}
        catalogPath={catalogPath}
        catalogRecords={catalogRecords}
        catalogSaved={catalogSaved}
        busy={busy}
        error={error}
        checkedNow={checkedNow}
        profile={profile}
        onBack={backOneStep}
        onChooseMethod={chooseMethod}
        onChooseSource={() => void chooseFolder("source")}
        onChooseEdits={() => void chooseFolder("edits")}
        onChooseCatalog={() => void chooseCatalog()}
        onCheckMaterial={() => void checkPairedMaterial()}
        onSaveCatalog={saveCatalogMaterial}
        onReturnProfile={() => openView("profile")}
      />
    );
  }

  if (media === "jpeg" && method !== "xmp") {
    return (
      <JpegTrainingView
        method={method}
        sourceRoot={sourceRoot}
        editsRoot={editsRoot}
        catalogPath={catalogPath}
        catalogRecords={catalogRecords}
        catalogSaved={catalogSaved}
        busy={busy}
        error={error}
        checkedNow={checkedNow}
        profile={profile}
        onBack={backOneStep}
        onChooseMethod={chooseMethod}
        onChooseSource={() => void chooseFolder("source")}
        onChooseEdits={() => void chooseFolder("edits")}
        onChooseCatalog={() => void chooseCatalog()}
        onCheckMaterial={() => void checkPairedMaterial()}
        onSaveCatalog={saveCatalogMaterial}
        onReturnProfile={() => openView("profile")}
      />
    );
  }

  return (
    <main className={styles.screen}>
      <header className={styles.header}>
        <button
          className={styles.backButton}
          type="button"
          onClick={backOneStep}
        >
          → {method ? "חזרה" : "חזרה לפרופיל"}
        </button>

        <div>
          <span className={styles.eyebrow}>בניית הפרופיל</span>
          <h1>למידה לפי {mediaLabel(media)}</h1>
          <p>
            {media === "jpeg"
              ? "בחר מסלול למידה, ואז את החומר שלו."
              : "מסלול RAW אחד. בוחרים מקור לעריכות Lightroom ואז את החומר."}
          </p>
        </div>
      </header>

      <nav className={styles.progress} aria-label="שלבי הגדרת הלמידה">
        <div className={styles.progressActive}>
          <span>1</span>
          <strong>
            {media === "jpeg" ? "שיטת למידה" : "מקור עריכות"}
          </strong>
        </div>
        <div className={currentStep >= 2 ? styles.progressActive : styles.progressItem}>
          <span>2</span>
          <strong>בחירת חומר</strong>
        </div>
      </nav>

      {!method ? (
        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>שלב 1 · {mediaLabel(media)}</span>
            <h2>{methodOptions.heading}</h2>
            <p>{methodOptions.copy}</p>
          </div>

          <div className={styles.methodGrid}>
            {[methodOptions.first, methodOptions.second].map((option) => (
              <button
                key={option.method}
                className={styles.methodCard}
                type="button"
                onClick={() => chooseMethod(option.method)}
              >
                <span className={styles.methodTag}>{option.tag}</span>
                <div>
                  <h3>{option.title}</h3>
                  <p>{option.copy}</p>
                </div>
                <span className={styles.cardArrow} aria-hidden="true">←</span>
              </button>
            ))}
          </div>
        </section>
      ) : (
        <section className={styles.stage}>
          <div className={styles.stageHeading}>
            <span>
              שלב 2 · {mediaLabel(media)} ·{" "}
              {method === "catalog"
                ? "Lightroom Catalog"
                : method === "xmp"
                  ? "XMP"
                  : "לפני + אחרי"}
            </span>
            <h2>בחר את החומר</h2>
            <p>רק שני מקורות. כל השאר נשאר מאחורי הקלעים.</p>
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

            {pairedMethod ? (
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
                    {media === "jpeg" ? "JPEG ערוך" : "עריכות XMP"}
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
              {media === "jpeg" ? "שנה שיטת למידה" : "שנה מקור עריכות"}
            </button>

            {pairedMethod ? (
              <button
                className={styles.primaryButton}
                type="button"
                disabled={busy || !materialReady}
                onClick={() => void checkPairedMaterial()}
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

          {pairedMethod && checkedNow && profile ? (
            <section className={styles.result}>
              <span className={styles.resultIcon} aria-hidden="true">✓</span>
              <div>
                <span className={styles.resultLabel}>בדיקת החומר הסתיימה</span>
                <h3>
                  {profile.usable_pairs.toLocaleString("he-IL")} זוגות מוכנים
                </h3>
                <p>
                  {profile.usable_pairs > 0
                    ? "החומר הוגדר ויופיע עכשיו בעמוד הפרופיל."
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
                  המקור והקטלוג נשמרו. לא יוצג סטטוס אימון עד שקיים Brain
                  מאומן בפועל.
                </p>
              </div>
              <button type="button" onClick={() => openView("profile")}>
                חזרה לפרופיל
              </button>
            </section>
          ) : null}
        </section>
      )}
    </main>
  );
}
