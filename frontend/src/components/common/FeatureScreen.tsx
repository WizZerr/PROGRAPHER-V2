import styles from "./FeatureScreen.module.css";

type FeatureScreenProps = {
  eyebrow: string;
  title: string;
  description: string;
  placeholder?: string;
};

export default function FeatureScreen({
  eyebrow,
  title,
  description,
  placeholder = "המסך מוכן להוספת הפונקציונליות בשלב המתאים.",
}: FeatureScreenProps) {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <div className={styles.placeholder}>{placeholder}</div>
    </section>
  );
}
