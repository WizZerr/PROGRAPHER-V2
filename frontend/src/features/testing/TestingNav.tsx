"use client";

import { createContext, useContext, useRef, useState } from "react";

export type PhotoSelection = {
  eventId: string;
  fingerprint: string;
};

export type RecipeDraft = {
  exposure: number;
  temperature: number;
  tint: number;
};

type TestingNavValue = {
  selection: PhotoSelection | null;
  outputDir: string;
  setOutputDir: (value: string) => void;
  getDraft: (eventId: string, fingerprint: string) => RecipeDraft | null;
  setDraft: (eventId: string, fingerprint: string, recipe: RecipeDraft) => void;
  clearDraft: (eventId: string, fingerprint: string) => void;
  openPhoto: (eventId: string, fingerprint: string) => void;
  openGallery: () => void;
};

const TestingNavContext = createContext<TestingNavValue | null>(null);

export function TestingNavProvider({
  children,
  onOpenDarkroom,
  onOpenGallery,
}: {
  children: React.ReactNode;
  onOpenDarkroom: () => void;
  onOpenGallery: () => void;
}) {
  const [selection, setSelection] = useState<PhotoSelection | null>(null);
  const [outputDir, setOutputDir] = useState("");
  const drafts = useRef<Record<string, RecipeDraft>>({});

  function draftKey(eventId: string, fingerprint: string) {
    return `${eventId}:${fingerprint}`;
  }

  return (
    <TestingNavContext.Provider
      value={{
        selection,
        outputDir,
        setOutputDir,
        getDraft: (eventId, fingerprint) =>
          drafts.current[draftKey(eventId, fingerprint)] ?? null,
        setDraft: (eventId, fingerprint, recipe) => {
          drafts.current[draftKey(eventId, fingerprint)] = { ...recipe };
        },
        clearDraft: (eventId, fingerprint) => {
          delete drafts.current[draftKey(eventId, fingerprint)];
        },
        openPhoto: (eventId, fingerprint) => {
          setSelection({ eventId, fingerprint });
          onOpenDarkroom();
        },
        openGallery: onOpenGallery,
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
