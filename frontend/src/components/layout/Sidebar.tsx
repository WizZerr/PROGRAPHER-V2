import styles from "./AppShell.module.css";
import type { WorkspaceView } from "@/features/workspace/workspace.types";

type SidebarProps = {
  activeView: WorkspaceView;
  onSelect: (view: WorkspaceView) => void;
};

const items: Array<{ id: WorkspaceView; label: string }> = [
  { id: "dashboard", label: "לוח בקרה" },
  { id: "events", label: "אירועים" },
  { id: "gallery", label: "גלריה" },
  { id: "darkroom", label: "חדר עריכה" },
  { id: "profile", label: "הפרופיל שלי" },
  { id: "training", label: "מעבדת למידה" },
];

export default function Sidebar({ activeView, onSelect }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>ProGrapher</div>

      <nav className={styles.nav} aria-label="ניווט ראשי">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`${styles.navItem} ${
              activeView === item.id ? styles.active : ""
            }`}
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className={styles.sidebarFooter}>PROGRAPHER V2</div>
    </aside>
  );
}
