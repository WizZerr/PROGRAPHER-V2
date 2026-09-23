import type { ReactNode } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import styles from "./AppShell.module.css";
import type { WorkspaceView } from "@/features/workspace/workspace.types";

type AppShellProps = {
  children: ReactNode;
  activeView: WorkspaceView;
  title: string;
  immersive?: boolean;
  onSelect: (view: WorkspaceView) => void;
};

export default function AppShell({
  children,
  activeView,
  title,
  immersive = false,
  onSelect,
}: AppShellProps) {
  return (
    <div className={styles.shell}>
      <Sidebar activeView={activeView} onSelect={onSelect} />

      <div className={immersive ? `${styles.main} ${styles.mainImmersive}` : styles.main}>
        {immersive ? null : <Header title={title} />}
        <div className={immersive ? `${styles.content} ${styles.contentImmersive}` : styles.content}>
          {children}
        </div>
      </div>
    </div>
  );
}
