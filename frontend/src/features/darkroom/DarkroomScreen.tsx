import styles from "./DarkroomScreen.module.css";

export default function DarkroomScreen() {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>DARKROOM</span>
        <h2>חדר עריכה</h2>
        <p>כאן נבנה את סביבת הבדיקה והעריכה של התמונות לפני ההעברה ל-Lightroom.</p>
      </div>

      <div className={styles.placeholder}>
        המסך הופרד למודול עצמאי ומוכן להוספת הפונקציונליות בשלב המתאים.
      </div>
    </section>
  );
}
