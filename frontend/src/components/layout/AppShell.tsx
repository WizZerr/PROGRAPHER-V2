import type { ReactNode } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import styles from "./AppShell.module.css";
import type { WorkspaceView } from "@/features/workspace/workspace.types";

type AppShellProps = {
  children: ReactNode;
  activeView: WorkspaceView;
  title: string;
  onSelect: (view: WorkspaceView) => void;
};

export default function AppShell({
  children,
  activeView,
  title,
  onSelect,
}: AppShellProps) {
  return (
    <div className={styles.shell}>
      <Sidebar activeView={activeView} onSelect={onSelect} />

      <div className={styles.main}>
        <Header title={title} />
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
