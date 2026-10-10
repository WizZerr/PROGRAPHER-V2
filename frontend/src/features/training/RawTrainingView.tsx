"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import type { TestingProfile } from "@/features/testing/testing.api";
import styles from "./RawTrainingView.module.css";
import TrainingBreadcrumbs from "./TrainingBreadcrumbs";

type RawMethod = "catalog" | "xmp";

type Props = {
  method: RawMethod | null;
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
  onChooseMethod: (method: RawMethod) => void;
  onChooseSource: () => void;
  onChooseEdits: () => void;
  onChooseCatalog: () => void;
  onCheckMaterial: () => void;
  onSaveCatalog: () => void;
  onReturnProfile: () => void;
};

type IconName = "arrow" | "folder" | "sliders" | "database" | "file" | "check" | "star" | "image" | "info" | "layers";

function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  const shapes: Record<IconName, ReactNode> = {
    arrow: <path d="M19 12H5m7-7-7 7 7 7" />,
    folder: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z" />,
    sliders: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none"/><circle cx="8" cy="18" r="2" fill="currentColor" stroke="none"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></>,
    file: <><path d="M5 3h9l5 5v13H5zM14 3v5h5"/><path d="M8 14h8M8 18h6"/></>,
    check: <path d="m5 12 5 5L20 7" />,
    star: <path d="m12 2 3 6 6.5.9-4.7 4.6 1.1 6.5L12 17l-5.9 3 1.1-6.5L2.5 9 9 8z" />,
    image: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m4 17 6-6 5 5 3-3 3 3"/><circle cx="16" cy="8" r="1"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

function MethodCard({ kind, onSelect }: { kind: RawMethod; onSelect: () => void }) {
  const catalog = kind === "catalog";
  return (
    <button type="button" className={`${styles.choiceCard} ${catalog ? styles.recommended : ""}`} onClick={onSelect}
      aria-label={catalog ? "בחירת מקור עריכה: Lightroom Catalog" : "בחירת מקור עריכה: קובצי XMP"}>
      <span className={styles.choiceTag} dir="ltr">{catalog ? "LRCAT" : "XMP"}</span>
      {catalog && <span className={styles.recommendation}><Icon name="star" size={16}/> מומלץ לחומר שבידך</span>}
      <span className={styles.choiceBody}>
        <span className={styles.choiceText}>
          <strong>{catalog ? <span dir="ltr">Lightroom Catalog</span> : "קובצי XMP"}</strong>
          <span>{catalog
            ? "בחירת קטלוג Lightroom קיים המכיל את הוראות העריכה של הצלם, לצד קובצי RAW מקוריים."
            : "בחירת קובצי XMP נלווים ל־RAW כדי לקרוא את הוראות העריכה השמורות בהם."}</span>
        </span>
        <span className={styles.choiceArt} aria-hidden="true">
          <Image src={catalog ? "/training-raw-lrcat.png" : "/training-raw-xmp.png"} alt=""
            width={catalog ? 274 : 221} height={182} unoptimized priority={catalog} />
        </span>
      </span>
      <span className={styles.benefitRail}>
        <span><Icon name={catalog ? "database" : "folder"} size={19}/>{catalog ? "קובץ ‎.lrcat" : "קובצי צד XMP"}</span>
        <span><Icon name="sliders" size={19}/>הגדרות עריכה קיימות</span>
        <span><Icon name={catalog ? "layers" : "image"} size={19}/>לצד תמונות RAW</span>
      </span>
      <span className={styles.cardBottom}>
        <span className={styles.roundArrow}><Icon name="arrow" size={24}/></span>
        <span>{catalog ? "המשך עם Lightroom Catalog" : "המשך עם קובצי XMP"}</span>
      </span>
    </button>
  );
}

function MaterialCard({ label, value, onClick, busy = false }: { label: string; value: string; onClick: () => void; busy?: boolean }) {
  return (
    <button className={`${styles.materialCard} ${value ? styles.materialSelected : ""}`} type="button"
      onClick={onClick} disabled={busy}>
      <span className={styles.materialGlyph}><Icon name={value ? "check" : "folder"} size={27}/></span>
      <span className={styles.materialText}>
        <span>{label}</span>
        <strong>{value ? "החומר נבחר" : "לחץ לבחירת חומר"}</strong>
        <small title={value || undefined} dir="ltr">{value || "טרם נבחר קובץ או תיקייה"}</small>
      </span>
      <span className={styles.materialAction}>{value ? "שנה" : "בחר"}<Icon name="arrow" size={17}/></span>
    </button>
  );
}

export default function RawTrainingView({
  method, sourceRoot, editsRoot, catalogPath, catalogRecords, catalogSaved, busy, error,
  checkedNow, profile, onBack, onChooseMethod, onChooseSource, onChooseEdits, onChooseCatalog,
  onCheckMaterial, onSaveCatalog, onReturnProfile,
}: Props) {
  const onStepTwo = method !== null;
  const sourceReady = Boolean(sourceRoot && (method === "catalog" ? catalogPath : editsRoot));
  return (
    <main className={styles.screen} dir="rtl">
      <header className={styles.hero}>
        <div className={styles.breadcrumbs}>
          <TrainingBreadcrumbs media="raw" />
        </div>
        <button className={styles.backButton} type="button" onClick={onBack}>
          <Icon name="arrow" size={21}/>{onStepTwo ? "חזרה למקור העריכה" : "חזרה לפרופיל"}
        </button>
        <div className={styles.heroCopy}>
          <span className={styles.kicker}>בניית הפרופיל</span>
          <h1>למידה לפי <bdi>RAW</bdi></h1>
          <p>מסלול RAW אחד. בוחרים מקור להוראות העריכה של Lightroom, ואז את הקבצים המתאימים.</p>
        </div>
        <div className={styles.heroArt} aria-hidden="true">
          <Image src="/training-raw-hero.png" alt="" width={500} height={249} unoptimized priority />
        </div>
      </header>

      <nav className={styles.stepper} aria-label="שלבי הגדרת הלמידה">
        <div className={`${styles.step} ${!onStepTwo ? styles.activeStep : styles.completedStep}`} aria-current={!onStepTwo ? "step" : undefined}>
          <span className={styles.stepCircle}>{onStepTwo ? <Icon name="check" size={18}/> : "1"}</span>
          <span><strong>מקור עריכה</strong><small>בחירת מקור עריכות Lightroom</small></span>
        </div>
        <span className={`${styles.stepConnector} ${onStepTwo ? styles.stepConnectorDone : ""}`} aria-hidden="true" />
        <div className={`${styles.step} ${onStepTwo ? styles.activeStep : ""}`} aria-current={onStepTwo ? "step" : undefined}>
          <span className={styles.stepCircle}>2</span>
          <span><strong>בחירת חומר</strong><small>בחירת קובצי RAW ללמידה</small></span>
        </div>
      </nav>

      <section className={styles.stage} aria-label={onStepTwo ? "בחירת חומר" : "בחירת מקור עריכות"}>
        <div className={styles.stageHeading}>
          <h2>{onStepTwo ? method === "catalog" ? "בחר את ה־RAW וקטלוג Lightroom" : "בחר את ה־RAW וקובצי XMP" : "איך נקרא את עריכות Lightroom?"}</h2>
          <p>{onStepTwo
            ? "בחר את החומר הקיים. בחירה ושמירה אינן מפעילות אימון AI או משנות את קובצי המקור."
            : "יש לנו מסלול RAW אחד. כעת בוחרים מאיזה מקור נקרא את הגדרות העריכה שכבר קיימות."}</p>
        </div>

        {!onStepTwo ? (
          <div className={styles.choiceGrid}>
            <MethodCard kind="catalog" onSelect={() => onChooseMethod("catalog")}/>
            <MethodCard kind="xmp" onSelect={() => onChooseMethod("xmp")}/>
          </div>
        ) : (
          <div className={styles.materialStage}>
            <div className={styles.materialGrid}>
              <MaterialCard label="תיקיית RAW מקור" value={sourceRoot} onClick={onChooseSource} busy={busy}/>
              <MaterialCard label={method === "catalog" ? "Lightroom Catalog (.lrcat)" : "תיקיית עריכות XMP"}
                value={method === "catalog" ? catalogPath : editsRoot}
                onClick={method === "catalog" ? onChooseCatalog : onChooseEdits} busy={busy}/>
            </div>
            {error && <div className={styles.error} role="alert">{error}</div>}
            <div className={styles.stageActions}>
              <button className={styles.ghostButton} type="button" onClick={onBack}>שנה מקור עריכה</button>
              {method === "catalog" ? (
                <button className={styles.primaryButton} type="button" onClick={onSaveCatalog} disabled={!sourceReady || busy}>
                  {catalogSaved ? "שמור שוב את הגדרת החומר" : "שמור הגדרת חומר"}
                </button>
              ) : (
                <button className={styles.primaryButton} type="button" onClick={onCheckMaterial} disabled={!sourceReady || busy}>
                  {busy ? "בודק…" : profile ? "בדוק שוב את החומר" : "בדוק את החומר"}
                </button>
              )}
            </div>
            {method === "catalog" && catalogSaved && (
              <div className={styles.result} role="status">
                <Icon name="check" size={24}/>
                <span><strong>נתיבי החומר נשמרו</strong><small>{catalogRecords === null ? "Lightroom Catalog נבחר" : `${catalogRecords.toLocaleString("he-IL")} רשומות בקטלוג`}. עדיין לא בוצע אימון Brain.</small></span>
                <button type="button" onClick={onReturnProfile}>חזרה לפרופיל</button>
              </div>
            )}
            {method === "xmp" && checkedNow && profile && (
              <div className={styles.result} role="status">
                <Icon name="check" size={24}/>
                <span><strong>בדיקת החומר הסתיימה</strong><small>{profile.usable_pairs.toLocaleString("he-IL")} זוגות שמישים נמצאו. עדיין לא בוצע אימון Brain.</small></span>
                <button type="button" onClick={onReturnProfile}>חזרה לפרופיל</button>
              </div>
            )}
          </div>
        )}
        <p className={styles.truthNote}><Icon name="info" size={17}/> בחירת מקור העריכות מכינה את הנתונים. הלמידה עצמה תתחיל רק לאחר אימות החומר.</p>
      </section>
    </main>
  );
}
