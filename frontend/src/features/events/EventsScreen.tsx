import styles from "./EventsScreen.module.css";

export default function EventsScreen() {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>EVENTS</span>
        <h2>אירועים</h2>
        <p>כאן ניצור וננהל אירוע חדש, נבחר תיקיית RAW ונעקוב אחרי תהליך הניתוח והעריכה.</p>
      </div>

      <div className={styles.placeholder}>
        המסך הופרד למודול עצמאי ומוכן להוספת הפונקציונליות בשלב המתאים.
      </div>
    </section>
  );
}
