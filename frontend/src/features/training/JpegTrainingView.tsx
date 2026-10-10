"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import type { TestingProfile } from "@/features/testing/testing.api";
import styles from "./JpegTrainingView.module.css";

type LearningChoice = "pairs" | "catalog";

type Props = {
  method: LearningChoice | null;
  sourceRoot: string;
  editsRoot: string;
  catalogPath: string;
  catalogRecords: number | null;
  catalogSaved: boolean;
  busy: boolean;
  error: string;
  checkedNow: boolean;
  profile: TestingProfile | null;
  onBack: () => void;
  onChooseMethod: (method: LearningChoice) => void;
  onChooseSource: () => void;
  onChooseEdits: () => void;
  onChooseCatalog: () => void;
  onCheckMaterial: () => void;
  onSaveCatalog: () => void;
  onReturnProfile: () => void;
};

type GlyphName = "arrow" | "house" | "star" | "target" | "monitor" | "bolt" | "book" | "info" | "folder" | "check";

function Glyph({ name, size = 21 }: { name: GlyphName; size?: number }) {
  const paths: Record<GlyphName, ReactNode> = {
    arrow: <><path d="M19 12H5m7-7-7 7 7 7" /></>,
    house: <><path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7" /></>,
    star: <><path d="m12 2 3 6 6.5.9-4.7 4.6 1.1 6.5L12 17l-5.9 3 1.1-6.5L2.5 9 9 8z" /></>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
    monitor: <><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></>,
    bolt: <><path d="m13 2-9 12h7l-1 8 10-13h-7z"/></>,
    book: <><path d="M12 6c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v15"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></>,
    folder: <><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/></>,
    check: <><path d="m5 12 5 5L20 7"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function MethodCard({
  kind,
  onSelect,
}: {
  kind: LearningChoice;
  onSelect: () => void;
}) {
  const pairs = kind === "pairs";
  return (
    <button
      type="button"
      className={`${styles.methodCard} ${pairs ? styles.recommended : ""}`}
      onClick={onSelect}
      aria-label={pairs ? "בחירת שיטת זוגות לפני ואחרי" : "בחירת שיטת Lightroom Catalog"}
    >
      <span className={styles.methodTag} dir="ltr">{pairs ? "PAIRS" : "LRCAT"}</span>
      {pairs ? (
        <span className={styles.recommendation}><Glyph name="star" size={16} /> מומלץ</span>
      ) : null}
      <span className={styles.methodCopy}>
        <strong>{pairs ? "זוגות לפני + אחרי" : <span dir="ltr">Lightroom Catalog</span>}</strong>
        <span>
          {pairs
            ? "בחר קובצי JPEG מקוריים ואת הגרסאות הסופיות שערכת, כדי לבדוק את השינויים שביצעת."
            : "בחר קובצי JPEG מקור וקטלוג Lightroom קיים שמכיל את נתוני העריכה שלהם."}
        </span>
      </span>
      <span className={styles.methodArt} aria-hidden="true">
        <Image
          src={pairs ? "/training-jpeg-pairs.png" : "/training-jpeg-lrcat.png"}
          alt=""
          width={1448}
          height={1086}
          unoptimized
          priority={pairs}
          sizes="(max-width: 1080px) 38vw, 260px"
        />
      </span>
      <span className={styles.methodBenefits}>
        {pairs ? (
          <>
            <span><Glyph name="monitor" size={19} /> מתאים לכל תוכנת עריכה</span>
            <i aria-hidden="true" />
            <span><Glyph name="target" size={19} /> השוואת מקור ותוצאה</span>
          </>
        ) : (
          <>
            <span><Glyph name="bolt" size={19} /> מתאים לאוסף תמונות גדול</span>
            <i aria-hidden="true" />
            <span><Glyph name="book" size={19} /> דורש קטלוג Lightroom</span>
          </>
        )}
      </span>
      <span className={styles.arrowCircle} aria-hidden="true"><Glyph name="arrow" size={22} /></span>
    </button>
  );
}

function MaterialOption({
  title,
  selected,
  value,
  busy,
  onClick,
}: {
  title: string;
  selected: boolean;
  value: string;
  busy?: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" disabled={busy} onClick={onClick}
      className={`${styles.materialOption} ${selected ? styles.materialSelected : ""}`}>
      <span className={styles.materialIcon}><Glyph name={selected ? "check" : "folder"} size={28} /></span>
      <span className={styles.materialText}>
        <span>{title}</span>
        <strong>{selected ? "נבחר" : "לחץ לבחירת קובץ או תיקייה"}</strong>
        <small dir="ltr" title={value || undefined}>{value || "טרם נבחר חומר"}</small>
      </span>
      <span className={styles.materialAction}>{selected ? "שנה" : "בחר"} <Glyph name="arrow" size={17}/></span>
    </button>
  );
}

export default function JpegTrainingView({
  method,
  sourceRoot,
  editsRoot,
  catalogPath,
  catalogRecords,
  catalogSaved,
  busy,
  error,
  checkedNow,
  profile,
  onBack,
  onChooseMethod,
  onChooseSource,
  onChooseEdits,
  onChooseCatalog,
  onCheckMaterial,
  onSaveCatalog,
  onReturnProfile,
}: Props) {
  const secondStep = method !== null;
  const paired = method === "pairs";
  const ready = Boolean(sourceRoot && (paired ? editsRoot : catalogPath));

  return (
    <main className={styles.screen} dir="rtl">
      <section className={styles.frame}>
        <header className={styles.topArea}>
          <div className={styles.topLine}>
            <div className={styles.crumbs} aria-label="מיקום נוכחי">
              <Glyph name="house" size={20} />
              <span>הפרופיל שלי</span><span className={styles.slash}>/</span>
              <span>בניית פרופיל</span><span className={styles.slash}>/</span>
              <b dir="ltr">JPEG</b>
            </div>
            <button type="button" className={styles.back} onClick={onBack}>
              <Glyph name="arrow" size={22} /> {secondStep ? "חזרה לשיטת למידה" : "חזרה לפרופיל"}
            </button>
          </div>
          <div className={styles.titleBlock}>
            <span className={styles.eyebrow}>בניית הפרופיל</span>
            <h1>למידה לפי <bdi>JPEG</bdi></h1>
            <p>למד את ProGrapher את סגנון העריכה שלך מהתמונות שכבר ערכת.</p>
          </div>
        </header>

        <nav className={styles.steps} aria-label="שלבי הגדרת הלמידה">
          <div className={`${styles.step} ${!secondStep ? styles.stepActive : styles.stepCompleted}`} aria-current={!secondStep ? "step" : undefined}>
            <span className={styles.stepNumber}>{secondStep ? <Glyph name="check" size={16}/> : "1"}</span>
            <strong>שיטת למידה</strong>
          </div>
          <span className={styles.stepConnector} aria-hidden="true" />
          <div className={`${styles.step} ${secondStep ? styles.stepActive : ""}`} aria-current={secondStep ? "step" : undefined}>
            <span className={styles.stepNumber}>2</span>
            <strong>בחירת חומר</strong>
          </div>
        </nav>

        <section className={styles.innerStage} aria-label={secondStep ? "בחירת חומר" : "בחירת שיטת למידה"}>
          <div className={styles.stageHeader}>
            <span className={styles.stageEyebrow}>שלב {secondStep ? "2" : "1"} · JPEG</span>
            <h2>{secondStep
              ? paired ? "בחר את התמונות המקוריות והערוכות" : "בחר את תמונות המקור וקטלוג Lightroom"
              : "איך תרצה ש־ProGrapher ילמד את סגנון העריכה שלך?"}
            </h2>
            <p>{secondStep
              ? "החומר ייבדק או יישמר כהגדרה בלבד. לא מתחיל אימון מודל בשלב הזה."
              : "בחר את מקור התמונות הערוכות שנשתמש בו כדי להכין את פרופיל העריכה האישי שלך."}
            </p>
          </div>

          {!secondStep ? (
            <div className={styles.cards}>
              <MethodCard kind="pairs" onSelect={() => onChooseMethod("pairs")} />
              <MethodCard kind="catalog" onSelect={() => onChooseMethod("catalog")} />
            </div>
          ) : (
            <div className={styles.materialSection}>
              <div className={styles.materials}>
                <MaterialOption title="תיקיית JPEG מקור" selected={Boolean(sourceRoot)} value={sourceRoot} onClick={onChooseSource} />
                {paired ? (
                  <MaterialOption title="תיקיית JPEG ערוך" selected={Boolean(editsRoot)} value={editsRoot} onClick={onChooseEdits} />
                ) : (
                  <MaterialOption title="קובץ Lightroom Catalog (LRCAT)" selected={Boolean(catalogPath)} value={catalogPath} onClick={onChooseCatalog} busy={busy} />
                )}
              </div>
              {error ? <div className={styles.error} role="alert">{error}</div> : null}
              <div className={styles.actions}>
                <button type="button" className={styles.secondary} onClick={onBack}>שנה שיטת למידה</button>
                {paired ? (
                  <button type="button" className={styles.primary} disabled={busy || !ready} onClick={onCheckMaterial}>
                    {busy ? "בודק חומר…" : profile ? "בדוק מחדש" : "בדוק את החומר"}
                  </button>
                ) : (
                  <button type="button" className={styles.primary} disabled={!ready || busy} onClick={onSaveCatalog}>
                    {catalogSaved ? "שמור שוב" : "שמור את החומר"}
                  </button>
                )}
              </div>
              {paired && checkedNow && profile ? (
                <div className={styles.result} role="status">
                  <Glyph name="check" size={24} />
                  <div>
                    <strong>{profile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים נמצאו</strong>
                    <p>{profile.usable_pairs > 0
                      ? "החומר נבדק ונרשם בפרופיל. לא התחיל אימון Brain."
                      : "לא נמצאו זוגות שמישים. בדוק את המקורות ונסה שוב."}</p>
                  </div>
                  <button type="button" onClick={onReturnProfile}>חזרה לפרופיל</button>
                </div>
              ) : null}
              {!paired && catalogSaved ? (
                <div className={styles.result} role="status">
                  <Glyph name="check" size={24} />
                  <div>
                    <strong>{catalogRecords === null ? "הקטלוג הוגדר" : `${catalogRecords.toLocaleString("he-IL")} רשומות בקטלוג`}</strong>
                    <p>נתיב המקור והקטלוג נשמרו. זה עדיין לא סטטוס אימון Brain.</p>
                  </div>
                  <button type="button" onClick={onReturnProfile}>חזרה לפרופיל</button>
                </div>
              ) : null}
            </div>
          )}
        </section>

        <footer className={styles.footnote}>
          <Glyph name="info" size={20}/>
          {secondStep ? "אפשר להחליף את המקורות ולבדוק שוב לפני התחלת הלמידה." : "ניתן לשנות את שיטת הלמידה גם בהמשך."}
        </footer>
      </section>
    </main>
  );
}
