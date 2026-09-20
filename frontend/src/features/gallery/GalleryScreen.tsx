import styles from "./GalleryScreen.module.css";

export default function GalleryScreen() {
  return (
    <section className={styles.screen}>
      <div className={styles.hero}>
        <span className={styles.eyebrow}>GALLERY</span>
        <h2>גלריה</h2>
        <p>כאן יוצגו התמונות של האירוע, סטטוס העריכה והחלוקה לסצנות בהמשך.</p>
      </div>

      <div className={styles.placeholder}>
        המסך הופרד למודול עצמאי ומוכן להוספת הפונקציונליות בשלב המתאים.
      </div>
    </section>
  );
}
