import styles from "./TrainingScreen.module.css";

export default function TrainingScreen() {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>TRAINING LAB</span>
        <h2>מעבדת למידה</h2>
        <p>כאן ננהל בניית Dataset, אימון, בדיקות והשוואה בין גרסאות המודל.</p>
      </div>

      <div className={styles.placeholder}>
        המסך הופרד למודול עצמאי ומוכן להוספת הפונקציונליות בשלב המתאים.
      </div>
    </section>
  );
}
