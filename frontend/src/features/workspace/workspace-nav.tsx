"use client";

import { createContext, useContext } from "react";
import type { WorkspaceView } from "./workspace.types";

const WorkspaceNavContext = createContext<(view: WorkspaceView) => void>(() => {});

export function WorkspaceNavProvider({
  onSelect,
  children,
}: {
  onSelect: (view: WorkspaceView) => void;
  children: React.ReactNode;
}) {
  return (
    <WorkspaceNavContext.Provider value={onSelect}>
      {children}
    </WorkspaceNavContext.Provider>
  );
}

export function useWorkspaceNav() {
  return useContext(WorkspaceNavContext);
}
