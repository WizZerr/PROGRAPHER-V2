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
];

function NavIcon({ view }: { view: WorkspaceView }) {
  const common = {
    width: 23,
    height: 23,
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
          <svg width="33" height="33" viewBox="0 0 26 26" fill="none">
            <path
              d="M7 21V5.2h7.2c3.8 0 6.3 2.1 6.3 5.4 0 3.4-2.5 5.5-6.3 5.5H10.8V21H7Z"
              fill="currentColor"
            />
            <path
              d="M10.8 8.3v4.6h3.1c1.8 0 2.8-.8 2.8-2.3 0-1.5-1-2.3-2.8-2.3h-3.1Z"
              fill="#0B1018"
            />
            <path
              d="M18.9 4.7 21.6 7.4"
              stroke="rgba(255,255,255,.7)"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
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

    </aside>
  );
}
