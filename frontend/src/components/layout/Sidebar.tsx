import styles from "./AppShell.module.css";
import type { WorkspaceView } from "@/features/workspace/workspace.types";

type SidebarProps = {
  activeView: WorkspaceView;
  onSelect: (view: WorkspaceView) => void;
};

const items: Array<{ id: WorkspaceView; label: string }> = [
  { id: "dashboard", label: "ראשי" },
  { id: "events", label: "אירועים" },
  { id: "gallery", label: "גלריה" },
  { id: "darkroom", label: "חדר עריכה" },
  { id: "profile", label: "הפרופיל שלי" },
  { id: "training", label: "למידה" },
];

function NavIcon({ view }: { view: WorkspaceView }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (view) {
    case "events":
      return (
        <svg {...common}>
          <path d="M4 7.5h16v11H4z" />
          <path d="M8 4.5v3M16 4.5v3M4 10.5h16" />
        </svg>
      );
    case "gallery":
      return (
        <svg {...common}>
          <rect x="4" y="4.5" width="16" height="15" rx="2.5" />
          <circle cx="9" cy="9" r="1.5" />
          <path d="m6.5 17 4.2-4.2 2.6 2.5 1.8-1.8 2.4 3.5" />
        </svg>
      );
    case "darkroom":
      return (
        <svg {...common}>
          <path d="M5 5h14v14H5z" />
          <path d="M8 8h8M8 12h8M8 16h5" />
          <circle cx="15.5" cy="16" r="1.5" />
        </svg>
      );
    case "profile":
      return (
        <svg {...common}>
          <circle cx="12" cy="8.5" r="3.2" />
          <path d="M5.8 19c.7-3.2 2.8-5 6.2-5s5.5 1.8 6.2 5" />
        </svg>
      );
    case "training":
      return (
        <svg {...common}>
          <path d="M6 17.5V13M12 17.5V9M18 17.5V5" />
          <path d="M4 19.5h16" />
        </svg>
      );
    case "dashboard":
    default:
      return (
        <svg {...common}>
          <rect x="4" y="4" width="6.5" height="6.5" rx="1.5" />
          <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5" />
          <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5" />
          <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5" />
        </svg>
      );
  }
}

export default function Sidebar({ activeView, onSelect }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.brandMark} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M4 3.5h10v11H4z" stroke="currentColor" strokeWidth="1.4" />
            <path d="M4 3.5h3.2v3.2H4z" fill="currentColor" />
            <path d="M9 7.2 13.2 14H4.8L9 7.2Z" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        </div>
        <div className={styles.brandText}>
          <span className={styles.brandName}>ProGrapher</span>
          <span className={styles.brandMeta}>סטודיו מקומי</span>
        </div>
      </div>

      <nav className={styles.nav} aria-label="ניווט ראשי">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`${styles.navItem} ${
              activeView === item.id ? styles.active : ""
            }`}
            aria-current={activeView === item.id ? "page" : undefined}
            aria-label={item.label}
            title={item.label}
            onClick={() => onSelect(item.id)}
          >
            <span className={styles.navIcon}>
              <NavIcon view={item.id} />
            </span>
            <span className={styles.navLabel}>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className={styles.sidebarFooter}>
        <div className={styles.localStatus}>
          <span className={styles.statusDot} aria-hidden="true" />
          <span>עיבוד מקומי</span>
        </div>
      </div>
    </aside>
  );
}
