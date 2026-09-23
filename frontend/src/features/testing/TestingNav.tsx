"use client";

import { createContext, useContext, useState } from "react";

export type PhotoSelection = {
  eventId: string;
  fingerprint: string;
};

type TestingNavValue = {
  selection: PhotoSelection | null;
  outputDir: string;
  setOutputDir: (value: string) => void;
  openPhoto: (eventId: string, fingerprint: string) => void;
};

const TestingNavContext = createContext<TestingNavValue | null>(null);

export function TestingNavProvider({
  children,
  onOpenDarkroom,
}: {
  children: React.ReactNode;
  onOpenDarkroom: () => void;
}) {
  const [selection, setSelection] = useState<PhotoSelection | null>(null);
  const [outputDir, setOutputDir] = useState("");

  return (
    <TestingNavContext.Provider
      value={{
        selection,
        outputDir,
        setOutputDir,
        openPhoto: (eventId, fingerprint) => {
          setSelection({ eventId, fingerprint });
          onOpenDarkroom();
        },
      }}
    >
      {children}
    </TestingNavContext.Provider>
  );
}

export function useTestingNav(): TestingNavValue {
  const value = useContext(TestingNavContext);
  if (!value) {
    throw new Error("Testing navigation is unavailable.");
  }
  return value;
}
