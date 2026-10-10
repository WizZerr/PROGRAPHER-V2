import styles from "./TrainingBreadcrumbs.module.css";

type Props = {
  media: "jpeg" | "raw";
  className?: string;
};

/** Shared top-right breadcrumb trail for RAW and JPEG learning. */
export default function TrainingBreadcrumbs({ media, className = "" }: Props) {
  return (
    <nav className={[styles.trail, className].filter(Boolean).join(" ")} aria-label="מיקום נוכחי" dir="rtl">
      <span>הפרופיל שלי</span>
      <span className={styles.separator} aria-hidden="true">←</span>
      <span>בניית הפרופיל</span>
      <span className={styles.separator} aria-hidden="true">←</span>
      <span aria-current="page">למידה לפי {media === "jpeg" ? "JPEG" : "RAW"}</span>
    </nav>
  );
}
