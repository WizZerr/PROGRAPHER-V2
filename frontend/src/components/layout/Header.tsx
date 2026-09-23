import styles from "./AppShell.module.css";

type HeaderProps = {
  title: string;
};

export default function Header({ title }: HeaderProps) {
  return (
    <header className={styles.header}>
      <h1 className={styles.headerTitle}>{title}</h1>

      <div className={styles.headerContext} aria-label="מצב סביבת העבודה">
        <span>ProGrapher</span>
        <span className={styles.headerContextDot} aria-hidden="true" />
        <span>מקומי</span>
      </div>
    </header>
  );
}
