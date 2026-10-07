import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import styles from "./AppShell.module.css";
import type { WorkspaceView } from "@/features/workspace/workspace.types";

type AppShellProps = {
  children: ReactNode;
  activeView: WorkspaceView;
  immersive?: boolean;
  onSelect: (view: WorkspaceView) => void;
};

export default function AppShell({
  children,
  activeView,
  immersive = false,
  onSelect,
}: AppShellProps) {
  const shellClass =
    activeView === "profile" || activeView === "training"
      ? `${styles.shell} ${styles.profileShell}`
      : styles.shell;

  return (
    <div className={shellClass}>
      <Sidebar
        activeView={activeView === "training" ? "profile" : activeView}
        onSelect={onSelect}
      />
      <div className={immersive ? `${styles.main} ${styles.mainImmersive}` : styles.main}>
        <div className={immersive ? `${styles.content} ${styles.contentImmersive}` : styles.content}>
          {children}
        </div>
      </div>
    </div>
  );
}
