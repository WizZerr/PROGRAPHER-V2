import type { ReactNode } from "react";
import styles from "./StatusBadge.module.css";

export type StatusTone = "success" | "warning" | "danger" | "neutral";

type StatusBadgeProps = {
  tone?: StatusTone;
  children: ReactNode;
};

export default function StatusBadge({
  tone = "neutral",
  children,
}: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      {children}
    </span>
  );
}
