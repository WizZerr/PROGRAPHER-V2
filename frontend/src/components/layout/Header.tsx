import styles from "./AppShell.module.css";

type HeaderProps = {
  title: string;
};

export default function Header({ title }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <span className={styles.headerEyebrow}>PROGRAPHER V2</span>
        <h1 className={styles.headerTitle}>{title}</h1>
      </div>

      <div className={styles.headerBadge}>תוכנת מחשב</div>
    </header>
  );
}
