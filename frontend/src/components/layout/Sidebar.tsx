import styles from "./AppShell.module.css";

const items = [
  "Dashboard",
  "Events",
  "Darkroom",
  "Profile",
  "Training Lab",
];

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>ProGrapher</div>

      <nav className={styles.nav} aria-label="Primary">
        {items.map((item, index) => (
          <button
            key={item}
            type="button"
            className={`${styles.navItem} ${index === 0 ? styles.active : ""}`}
          >
            {item}
          </button>
        ))}
      </nav>

      <div className={styles.sidebarFooter}>V2 FOUNDATION</div>
    </aside>
  );
}
