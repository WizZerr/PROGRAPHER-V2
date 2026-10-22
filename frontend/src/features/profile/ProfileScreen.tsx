"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useAccountIdentity } from "@/features/account/AccountIdentity";
import {
  getTestingProfile,
  type TestingProfile,
} from "@/features/testing/testing.api";
import {
  loadCatalogBindings,
  writeTrainingEntry,
  type CatalogBinding,
  type LearningMedia,
} from "@/features/training/learning-state";
import { useWorkspaceNav } from "@/features/workspace/workspace-nav";
import {
  getPhotographerSetup,
  saveStylePreferences,
  type PhotographerSetupOverview,
} from "./profile.api";
import styles from "./ProfileScreen.module.css";

type RouteState = "idle" | "pending" | "ready";

function routeState(profile: TestingProfile | null): RouteState {
  if (!profile) return "idle";
  return profile.usable_pairs > 0 ? "ready" : "pending";
}

function jpegPairStatus(profile: TestingProfile | null): string {
  if (!profile) return "לא הוגדר";
  if (profile.usable_pairs <= 0) return "נבדק · אין חומר שמיש";
  return `${profile.usable_pairs.toLocaleString("he-IL")} זוגות מוכנים`;
}

function catalogStatus(binding?: CatalogBinding): string {
  if (!binding) return "לא הוגדר";
  return binding.catalogPhotoRecords !== null
    ? `${binding.catalogPhotoRecords.toLocaleString("he-IL")} רשומות בקטלוג`
    : "קטלוג הוגדר";
}

function rawStatus(
  profile: TestingProfile | null,
  catalog?: CatalogBinding,
): { state: RouteState; label: string; source: string } {
  if (profile?.usable_pairs && profile.usable_pairs > 0) {
    return {
      state: "ready",
      label: `${profile.usable_pairs.toLocaleString("he-IL")} זוגות RAW/XMP`,
      source: "עריכות דרך XMP",
    };
  }

  if (catalog) {
    return {
      state: "ready",
      label: catalogStatus(catalog),
      source: "עריכות דרך Lightroom Catalog",
    };
  }

  if (profile) {
    return {
      state: "pending",
      label: "נבדק · אין חומר שמיש",
      source: "עריכות דרך XMP",
    };
  }

  return {
    state: "idle",
    label: "לא הוגדר",
    source: "XMP או Lightroom Catalog",
  };
}

function StatusPill({
  state,
  children,
}: {
  state: RouteState;
  children: ReactNode;
}) {
  const className =
    state === "ready"
      ? styles.statusReady
      : state === "pending"
        ? styles.statusPending
        : styles.statusIdle;

  return (
    <span className={className}>
      <span aria-hidden="true" />
      {children}
    </span>
  );
}

type VisualIcon =
  | "sliders"
  | "camera"
  | "layers"
  | "database"
  | "chart"
  | "settings";

function VisualGlyph({ kind }: { kind: VisualIcon }) {
  const common = {
    width: 28,
    height: 28,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (kind === "sliders") {
    return (
      <svg {...common}>
        <path d="M4 6h16M4 12h16M4 18h16" />
        <circle cx="9" cy="6" r="2" />
        <circle cx="15" cy="12" r="2" />
        <circle cx="11" cy="18" r="2" />
      </svg>
    );
  }

  if (kind === "camera") {
    return (
      <svg {...common}>
        <path d="M4 8.5h16v10H4z" />
        <path d="M8 8.5 9.5 5.5h5L16 8.5" />
        <circle cx="12" cy="13.5" r="3.2" />
      </svg>
    );
  }

  if (kind === "layers") {
    return (
      <svg {...common}>
        <path d="m12 4 7 4-7 4-7-4 7-4Z" />
        <path d="m5 12 7 4 7-4" />
        <path d="m5 16 7 4 7-4" />
      </svg>
    );
  }

  if (kind === "database") {
    return (
      <svg {...common}>
        <ellipse cx="12" cy="5.5" rx="6.5" ry="3" />
        <path d="M5.5 5.5v6c0 1.7 2.9 3 6.5 3s6.5-1.3 6.5-3v-6" />
        <path d="M5.5 11.5v6c0 1.7 2.9 3 6.5 3s6.5-1.3 6.5-3v-6" />
      </svg>
    );
  }

  if (kind === "chart") {
    return (
      <svg {...common}>
        <path d="M5 19V7M5 19h14" />
        <path d="m8 15 3-4 3 2 3-5" />
        <path d="M17 8h2v2" />
      </svg>
    );
  }

  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19 13.6v-3.2l-2.1-.6a7.3 7.3 0 0 0-.7-1.6l1-1.9-2.3-2.3-1.9 1a7.3 7.3 0 0 0-1.6-.7L10.8 2H7.6L7 4.2a7.3 7.3 0 0 0-1.6.7l-1.9-1-2.3 2.3 1 1.9a7.3 7.3 0 0 0-.7 1.6l-2.1.6v3.2l2.1.6c.2.6.4 1.1.7 1.6l-1 1.9 2.3 2.3 1.9-1c.5.3 1 .5 1.6.7l.6 2.1h3.2l.6-2.1c.6-.2 1.1-.4 1.6-.7l1.9 1 2.3-2.3-1-1.9c.3-.5.5-1 .7-1.6l2.1-.6Z" />
    </svg>
  );
}

function HeroLandscape() {
  return (
    <svg
      className={styles.heroLandscape}
      viewBox="0 0 1200 220"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="pg-sky" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#111a34" />
          <stop offset=".46" stopColor="#1b244b" />
          <stop offset=".7" stopColor="#243b68" />
          <stop offset="1" stopColor="#080d18" />
        </linearGradient>
        <radialGradient id="pg-glow" cx="68%" cy="20%" r="42%">
          <stop offset="0" stopColor="#5d67ff" stopOpacity=".5" />
          <stop offset=".48" stopColor="#3f4ea5" stopOpacity=".17" />
          <stop offset="1" stopColor="#0b1020" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="pg-m1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#14233d" />
          <stop offset="1" stopColor="#08101c" />
        </linearGradient>
        <linearGradient id="pg-m2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#101a2e" />
          <stop offset="1" stopColor="#050a12" />
        </linearGradient>
      </defs>
      <rect width="1200" height="220" fill="url(#pg-sky)" />
      <rect width="1200" height="220" fill="url(#pg-glow)" />
      <path d="M0 92 140 48 252 84 356 42 500 99 632 55 760 93 892 48 1020 82 1200 32V220H0Z" fill="url(#pg-m1)" opacity=".82" />
      <path d="M0 138 128 108 236 132 346 91 448 128 566 102 704 144 842 92 942 125 1064 86 1200 126V220H0Z" fill="url(#pg-m2)" />
      <path d="M0 170 132 147 250 163 364 137 482 166 620 143 748 176 864 139 1004 171 1200 136V220H0Z" fill="#050910" />
      <path d="M160 187c165-35 277 5 430-7 143-11 228-57 450-37" fill="none" stroke="#4e71b9" strokeOpacity=".17" strokeWidth="7" />
      <circle cx="854" cy="69" r="2.8" fill="#d8ddff" opacity=".72" />
      <path d="m850 76-8 18h16Z" fill="#080c13" />
      <rect x="848.5" y="72" width="3" height="10" rx="1.5" fill="#080c13" />
    </svg>
  );
}

function CoverageRing({ value, total }: { value: number; total: number }) {
  const radius = 27;
  const circumference = Math.PI * 2 * radius;
  const ratio = total > 0 ? Math.min(value / total, 1) : 0;

  return (
    <svg className={styles.coverageRing} viewBox="0 0 72 72" aria-hidden="true">
      <circle className={styles.coverageRingTrack} cx="36" cy="36" r={radius} />
      <circle
        className={styles.coverageRingValue}
        cx="36"
        cy="36"
        r={radius}
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - ratio)}
      />
    </svg>
  );
}

export default function ProfileScreen() {
  const openView = useWorkspaceNav();
  const {
    identity,
    firstNameLabel,
    profileOwnerLabel,
    updateIdentity,
  } = useAccountIdentity();

  const [jpegProfile, setJpegProfile] = useState<TestingProfile | null>(null);
  const [rawProfile, setRawProfile] = useState<TestingProfile | null>(null);
  const [catalogBindings, setCatalogBindings] = useState<
    Partial<Record<LearningMedia, CatalogBinding>>
  >({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [firstNameDraft, setFirstNameDraft] = useState(identity.firstName);
  const [profileNameDraft, setProfileNameDraft] = useState(
    identity.profileName ?? "",
  );
  const [styleName, setStyleName] = useState("");
  const [presetPath, setPresetPath] = useState<string | null>(null);
  const [profileMode, setProfileMode] =
    useState<"from_source" | "explicit">("from_source");
  const [cameraProfile, setCameraProfile] = useState("");

  const applyOverview = useCallback((value: PhotographerSetupOverview) => {
    setStyleName(value.setup.style_name ?? "");
    setPresetPath(value.setup.preset_path);
    setProfileMode(value.setup.color_profile_mode);
    setCameraProfile(value.setup.camera_profile ?? "");
  }, []);

  const refresh = useCallback(async () => {
    setError("");

    try {
      const [setup, jpeg, raw] = await Promise.all([
        getPhotographerSetup(),
        getTestingProfile("jpeg").catch(() => null),
        getTestingProfile("raw").catch(() => null),
      ]);

      applyOverview(setup);
      setJpegProfile(jpeg);
      setRawProfile(raw);
      setCatalogBindings(loadCatalogBindings());
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לטעון את הפרופיל.",
      );
    }
  }, [applyOverview]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function openLearning(media: LearningMedia) {
    if (media === "raw") {
      openView("learning-intake");
      return;
    }
    writeTrainingEntry({ media });
    openView("training");
  }

  function openSettings() {
    setFirstNameDraft(identity.firstName);
    setProfileNameDraft(identity.profileName ?? "");
    setSettingsOpen(true);
  }

  async function choosePreset() {
    const selected = await open({
      multiple: false,
      directory: false,
      title: "בחר פריסט Lightroom",
      filters: [{ name: "Lightroom Preset", extensions: ["xmp"] }],
    });

    if (!selected || Array.isArray(selected)) return;
    setPresetPath(selected);
  }

  async function saveSettings() {
    setBusy(true);
    setError("");
    setSaved("");

    try {
      const nextFirstName = firstNameDraft.trim();
      const nextProfileName = profileNameDraft.trim();

      updateIdentity({
        firstName: nextFirstName,
        displayName: nextFirstName,
        profileName: nextProfileName || null,
      });

      const result = await saveStylePreferences({
        style_name: styleName.trim() || null,
        preset_path: presetPath,
        color_profile_mode: profileMode,
        camera_profile:
          profileMode === "explicit" ? cameraProfile.trim() || null : null,
      });

      applyOverview(result);
      setSaved("הפרופיל עודכן.");
      setSettingsOpen(false);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "לא ניתן לשמור את הפרופיל.",
      );
    } finally {
      setBusy(false);
    }
  }

  const jpegCatalog = catalogBindings.jpeg;
  const rawCatalog = catalogBindings.raw;
  const rawLearning = rawStatus(rawProfile, rawCatalog);

  const jpegConfigured =
    Number(Boolean(jpegProfile)) + Number(Boolean(jpegCatalog));
  const rawConfigured = Number(Boolean(rawProfile) || Boolean(rawCatalog));
  const totalConfigured = jpegConfigured + rawConfigured;

  const profileStatus = useMemo(() => {
    if (totalConfigured === 0) return "עדיין לא הוגדר";
    if (jpegConfigured === 2 && rawConfigured === 1) {
      return "כל מסלולי הלמידה הוגדרו";
    }
    return "בתהליך בנייה";
  }, [jpegConfigured, rawConfigured, totalConfigured]);

  return (
    <section className={styles.screen}>
      <header className={styles.profileHeader}>
        <HeroLandscape />
        <div className={styles.heroShade} aria-hidden="true" />

        <div className={styles.profileIdentity}>
          <span className={styles.eyebrow}>הפרופיל שלי</span>
          <h1>סגנון העריכה של {profileOwnerLabel}</h1>
          <p>
            כאן רואים את מצב הלמידה שלך. JPEG ו־RAW נשמרים בנפרד,
            וכל מסלול מציג רק מידע שבאמת נמדד.
          </p>
        </div>

        <div className={styles.headerControls}>
          <button
            className={styles.settingsButton}
            type="button"
            aria-label="הגדרות הפרופיל"
            title="הגדרות הפרופיל"
            onClick={openSettings}
          >
            <VisualGlyph kind="settings" />
          </button>

          <div className={styles.headerDivider} aria-hidden="true" />

          <div className={styles.profileStatus}>
            <div>
              <small>מצב הפרופיל</small>
              <strong>{profileStatus}</strong>
            </div>
            <span
              className={totalConfigured > 0 ? styles.readyDot : styles.pendingDot}
              aria-hidden="true"
            />
          </div>
        </div>
      </header>

      {error ? <div className={styles.error}>{error}</div> : null}
      {saved ? <div className={styles.success}>{saved}</div> : null}

      <section className={styles.coveragePanel} aria-label="מצב מסלולי הלמידה">
        <div className={styles.coverageSummary}>
          <div className={styles.coverageSummaryCopy}>
            <span className={styles.sectionKicker}>LEARNING COVERAGE</span>
            <div className={styles.coverageValue}>
              <strong>{totalConfigured}</strong>
              <span>/ 3</span>
            </div>
            <small>יכולות למידה הוגדרו</small>
          </div>
          <CoverageRing value={totalConfigured} total={3} />
        </div>

        <div className={styles.coverageRail}>
          <div
            className={
              routeState(jpegProfile) === "ready"
                ? styles.coverageItemReady
                : styles.coverageItem
            }
          >
            <span className={styles.coverageIcon}>
              <VisualGlyph kind="sliders" />
            </span>
            <div className={styles.coverageText}>
              <div>
                <strong>JPEG · לפני + אחרי</strong>
                <span className={styles.coverageIndex}>01</span>
              </div>
              <small>{jpegPairStatus(jpegProfile)}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>

          <div
            className={
              jpegCatalog ? styles.coverageItemReady : styles.coverageItem
            }
          >
            <span className={styles.coverageIcon}>
              <VisualGlyph kind="camera" />
            </span>
            <div className={styles.coverageText}>
              <div>
                <strong>JPEG · Lightroom</strong>
                <span className={styles.coverageIndex}>02</span>
              </div>
              <small>{catalogStatus(jpegCatalog)}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>

          <div
            className={
              rawLearning.state === "ready"
                ? styles.coverageItemReady
                : styles.coverageItem
            }
          >
            <span className={styles.coverageIcon}>
              <VisualGlyph kind="layers" />
            </span>
            <div className={styles.coverageText}>
              <div>
                <strong>RAW · Lightroom</strong>
                <span className={styles.coverageIndex}>03</span>
              </div>
              <small>{rawLearning.label}</small>
            </div>
            <span className={styles.coverageDot} aria-hidden="true" />
          </div>
        </div>
      </section>

      <section className={styles.learningSurface}>
        <article className={`${styles.learningPane} ${styles.jpegPane}`}>
          <header className={styles.paneHeader}>
            <div className={styles.paneIdentity}>
              <span className={styles.mediaMonogram}>J</span>
              <div>
                <span className={styles.paneEyebrow}>JPEG LEARNING</span>
                <h2>למידה לפי JPEG</h2>
                <p>שני מנגנוני למידה עצמאיים לאותו workflow.</p>
              </div>
            </div>

            <button
              className={styles.paneAction}
              type="button"
              onClick={() => openLearning("jpeg")}
            >
              <span>{jpegConfigured > 0 ? "המשך הגדרה" : "התחל הגדרה"}</span>
              <span aria-hidden="true">←</span>
            </button>
          </header>

          <div className={styles.capabilityTable}>
            <div className={styles.capabilityRow}>
              <span className={styles.capabilityIcon}>
                <VisualGlyph kind="sliders" />
              </span>
              <div className={styles.capabilityMain}>
                <div>
                  <strong>זוגות לפני + אחרי</strong>
                  <span className={styles.capabilityNumber}>01</span>
                </div>
                <small>JPEG מקור מול JPEG סופי ערוך</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>PAIRS</span>
                <StatusPill state={routeState(jpegProfile)}>
                  {jpegPairStatus(jpegProfile)}
                </StatusPill>
              </div>
            </div>

            <div className={styles.capabilityRow}>
              <span className={styles.capabilityIcon}>
                <VisualGlyph kind="database" />
              </span>
              <div className={styles.capabilityMain}>
                <div>
                  <strong>Lightroom Catalog</strong>
                  <span className={styles.capabilityNumber}>02</span>
                </div>
                <small>JPEG מקור + החלטות עריכה מתוך LRCAT</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>LRCAT</span>
                <StatusPill state={jpegCatalog ? "ready" : "idle"}>
                  {catalogStatus(jpegCatalog)}
                </StatusPill>
              </div>
            </div>
          </div>

          <footer className={styles.paneFooter}>
            <div className={styles.footerMetric}>
              <strong>{jpegConfigured}/2</strong>
              <small>מסלולים הוגדרו</small>
            </div>
            <div className={styles.footerNote}>
              <span className={styles.footerIcon}><VisualGlyph kind="chart" /></span>
              <small>כל מסלול נשמר ונמדד בנפרד</small>
            </div>
          </footer>
        </article>

        <article className={`${styles.learningPane} ${styles.rawPane}`}>
          <header className={styles.paneHeader}>
            <div className={styles.paneIdentity}>
              <span className={styles.mediaMonogram}>R</span>
              <div>
                <span className={styles.paneEyebrow}>RAW LEARNING</span>
                <h2>למידה לפי RAW</h2>
                <p>Brain אחד שמתבסס על החלטות Lightroom.</p>
              </div>
            </div>

            <button
              className={styles.paneAction}
              type="button"
              onClick={() => openLearning("raw")}
            >
              <span>{rawConfigured ? "המשך הגדרה" : "התחל הגדרה"}</span>
              <span aria-hidden="true">←</span>
            </button>
          </header>

          <div className={styles.capabilityTable}>
            <div className={styles.capabilityRow}>
              <span className={styles.capabilityIcon}>
                <VisualGlyph kind="layers" />
              </span>
              <div className={styles.capabilityMain}>
                <div>
                  <strong>RAW + Lightroom</strong>
                  <span className={styles.capabilityNumber}>01</span>
                </div>
                <small>{rawLearning.source}</small>
              </div>
              <div className={styles.capabilityStatus}>
                <span>RAW</span>
                <StatusPill state={rawLearning.state}>
                  {rawLearning.label}
                </StatusPill>
              </div>
            </div>
          </div>

          <div className={styles.sourceStrip}>
            <span className={styles.sourceLabel}>מקורות עריכה</span>
            <span className={rawProfile ? styles.sourceActive : styles.sourceChip}>
              XMP
            </span>
            <span className={rawCatalog ? styles.sourceActive : styles.sourceChip}>
              LRCAT
            </span>
          </div>

          <footer className={styles.paneFooter}>
            <div className={styles.footerMetric}>
              <strong>{rawConfigured}/1</strong>
              <small>מסלול הוגדר</small>
            </div>
            <div className={styles.footerNote}>
              <span className={styles.footerIcon}><VisualGlyph kind="chart" /></span>
              <small>XMP ו־LRCAT הם מקורות לאותו Brain</small>
            </div>
          </footer>
        </article>
      </section>

      {settingsOpen ? (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setSettingsOpen(false);
          }}
        >
          <section
            className={styles.settingsModal}
            role="dialog"
            aria-modal="true"
            aria-label="הגדרות הפרופיל"
          >
            <header className={styles.modalHeader}>
              <div>
                <span className={styles.eyebrow}>הגדרות פרופיל</span>
                <h2>החשבון והסגנון שלך</h2>
              </div>
              <button
                type="button"
                aria-label="סגור"
                onClick={() => setSettingsOpen(false)}
              >
                ×
              </button>
            </header>

            <div className={styles.settingsScroll}>
              <section className={styles.settingsGroup}>
                <div className={styles.settingsGroupHead}>
                  <strong>זהות</strong>
                  <small>
                    השדות האלה כבר משתמשים ב־Account Identity שמוכן לחיבור לחשבון עתידי.
                  </small>
                </div>

                <div className={styles.formGrid}>
                  <label>
                    <span>שם פרטי</span>
                    <input
                      value={firstNameDraft}
                      onChange={(event) => setFirstNameDraft(event.target.value)}
                      placeholder="לדוגמה: מתן"
                    />
                  </label>

                  <label>
                    <span>שם הפרופיל</span>
                    <input
                      value={profileNameDraft}
                      onChange={(event) => setProfileNameDraft(event.target.value)}
                      placeholder={`${firstNameLabel} Weddings`}
                    />
                    <small>
                      אם ריק, יוצג השם הפרטי: {firstNameLabel}
                    </small>
                  </label>
                </div>
              </section>

              <details className={styles.advancedSettings}>
                <summary>
                  <span>
                    <strong>הגדרות מתקדמות</strong>
                    <small>סגנון, פריסט ופרופיל צבע</small>
                  </span>
                  <span aria-hidden="true">⌄</span>
                </summary>

                <div className={styles.advancedBody}>
                  <div className={styles.formGrid}>
                    <label>
                      <span>שם הסגנון</span>
                      <input
                        value={styleName}
                        onChange={(event) => setStyleName(event.target.value)}
                        placeholder="לדוגמה: טבעי וחם"
                      />
                    </label>

                    <div className={styles.fieldButton}>
                      <span>פריסט Lightroom</span>
                      <button
                        type="button"
                        onClick={() => void choosePreset()}
                        disabled={busy}
                      >
                        {presetPath ? "החלף פריסט" : "בחר פריסט"}
                      </button>
                    </div>
                  </div>

                  <div className={styles.profileModes}>
                    <label>
                      <input
                        type="radio"
                        name="profile-mode"
                        checked={profileMode === "from_source"}
                        onChange={() => setProfileMode("from_source")}
                      />
                      <span>קבע פרופיל צבע מתוך החומר</span>
                    </label>

                    <label>
                      <input
                        type="radio"
                        name="profile-mode"
                        checked={profileMode === "explicit"}
                        onChange={() => setProfileMode("explicit")}
                      />
                      <span>הגדר פרופיל צבע ידנית</span>
                    </label>

                    {profileMode === "explicit" ? (
                      <input
                        value={cameraProfile}
                        onChange={(event) => setCameraProfile(event.target.value)}
                        placeholder="לדוגמה: Adobe Color"
                      />
                    ) : null}
                  </div>
                </div>
              </details>
            </div>

            <footer className={styles.modalFooter}>
              <span>
                שלום {firstNameDraft.trim() || "צלם"}, · סגנון העריכה של{" "}
                {profileNameDraft.trim() || firstNameDraft.trim() || "צלם"}
              </span>
              <div>
                <button
                  className={styles.cancelButton}
                  type="button"
                  onClick={() => setSettingsOpen(false)}
                >
                  ביטול
                </button>
                <button
                  className={styles.saveButton}
                  type="button"
                  onClick={() => void saveSettings()}
                  disabled={busy}
                >
                  {busy ? "שומר…" : "שמור"}
                </button>
              </div>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
