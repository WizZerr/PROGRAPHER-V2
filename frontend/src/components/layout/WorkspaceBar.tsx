import type { ReactNode } from "react";
import styles from "./WorkspaceBar.module.css";

type WorkspaceBarProps = {
  kicker?: string;
  title: string;
  detail?: string;
  counter?: string;
  children?: ReactNode;
};

export default function WorkspaceBar({
  kicker,
  title,
  detail,
  counter,
  children,
}: WorkspaceBarProps) {
  return (
    <header className={styles.bar}>
      <div className={styles.identity}>
        {kicker ? <span className={styles.kicker}>{kicker}</span> : null}
        <strong className={styles.title}>{title}</strong>
        {detail ? <span className={styles.detail}>{detail}</span> : null}
      </div>
      <div className={styles.tools}>
        {counter ? <span className={styles.counter}>{counter}</span> : null}
        {children}
      </div>
    </header>
  );
}
