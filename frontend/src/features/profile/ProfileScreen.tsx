import styles from "./ProfileScreen.module.css";

export default function ProfileScreen() {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>PROFILE</span>
        <h2>הפרופיל שלי</h2>
        <p>כאן ינוהלו פרופיל הצלם, סגנון העריכה והגרסאות שנלמדו לאורך זמן.</p>
      </div>

      <div className={styles.placeholder}>
        המסך הופרד למודול עצמאי ומוכן להוספת הפונקציונליות בשלב המתאים.
      </div>
    </section>
  );
}
