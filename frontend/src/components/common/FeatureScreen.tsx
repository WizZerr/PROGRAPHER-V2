import styles from "./FeatureScreen.module.css";

type FeatureModule = {
  title: string;
  description: string;
};

type FeatureScreenProps = {
  eyebrow: string;
  title: string;
  description: string;
  placeholder?: string;
  modules?: FeatureModule[];
};

export default function FeatureScreen({
  eyebrow,
  title,
  description,
  placeholder = "הפונקציונליות של המסך תיפתח לפי שלב הפיתוח המתאים.",
  modules = [],
}: FeatureScreenProps) {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <div className={styles.workspace}>
        <div className={styles.workspaceHeader}>
          <div>
            <span className={styles.workspaceEyebrow}>מבנה סביבת העבודה</span>
            <h3>המסך מוכן להמשך הפיתוח</h3>
          </div>
          <span className={styles.stageBadge}>בפיתוח</span>
        </div>

        {modules.length > 0 ? (
          <div className={styles.moduleGrid}>
            {modules.map((module) => (
              <article key={module.title} className={styles.module}>
                <span className={styles.moduleDot} aria-hidden="true" />
                <div>
                  <strong>{module.title}</strong>
                  <p>{module.description}</p>
                </div>
              </article>
            ))}
          </div>
        ) : null}

        <p className={styles.placeholder}>{placeholder}</p>
      </div>
    </section>
  );
}
