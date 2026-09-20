import styles from "./AppShell.module.css";

export default function Header() {
  return (
    <header className={styles.header}>
      <div>
        <span className={styles.headerEyebrow}>PROGRAPHER V2</span>
        <h1 className={styles.headerTitle}>Workspace</h1>
      </div>
      <div className={styles.headerBadge}>Desktop</div>
    </header>
  );
}
