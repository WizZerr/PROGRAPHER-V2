"use client";

import { createContext, useContext, useRef, useState } from "react";
import type {
  LearningSource,
  ReviewSheet,
} from "@/features/testing/testing.api";

export type PhotoSelection = {
  eventId: string;
  fingerprint: string;
  learningSource: LearningSource;
};

export type RecipeDraft = {
  exposure: number;
  temperature: number;
  tint: number;
};

export type GalleryViewMode = "standard" | "compact" | "list";

type TestingNavValue = {
  selection: PhotoSelection | null;
  outputDir: string;
  setOutputDir: (value: string) => void;

  galleryEventId: string;
  setGalleryEventId: (value: string) => void;
  galleryViewMode: GalleryViewMode;
  setGalleryViewMode: (value: GalleryViewMode) => void;

  getReviewSheetCache: (
    eventId: string,
    learningSource: LearningSource,
  ) => ReviewSheet | null;
  setReviewSheetCache: (sheet: ReviewSheet) => void;
  patchCachedReview: (
    eventId: string,
    learningSource: LearningSource,
    fingerprint: string,
    recipe: RecipeDraft,
  ) => void;

  getDraft: (eventId: string, fingerprint: string) => RecipeDraft | null;
  setDraft: (eventId: string, fingerprint: string, recipe: RecipeDraft) => void;
  clearDraft: (eventId: string, fingerprint: string) => void;
  forgetEvent: (eventId: string) => void;

  openPhoto: (
    eventId: string,
    fingerprint: string,
    learningSource: LearningSource,
  ) => void;
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
  const [galleryEventId, setGalleryEventId] = useState("");
  const [galleryViewMode, setGalleryViewMode] =
    useState<GalleryViewMode>("standard");

  const drafts = useRef<Record<string, RecipeDraft>>({});
  const reviewSheets = useRef<Record<string, ReviewSheet>>({});

  function draftKey(eventId: string, fingerprint: string) {
    return `${eventId}:${fingerprint}`;
  }

  function sheetKey(eventId: string, learningSource: LearningSource) {
    return `${learningSource}:${eventId}`;
  }

  return (
    <TestingNavContext.Provider
      value={{
        selection,
        outputDir,
        setOutputDir,

        galleryEventId,
        setGalleryEventId,
        galleryViewMode,
        setGalleryViewMode,

        getReviewSheetCache: (eventId, learningSource) =>
          reviewSheets.current[sheetKey(eventId, learningSource)] ?? null,
        setReviewSheetCache: (sheet) => {
          reviewSheets.current[sheetKey(sheet.event_id, sheet.learning_source)] =
            sheet;
        },
        patchCachedReview: (
          eventId,
          learningSource,
          fingerprint,
          recipe,
        ) => {
          const key = sheetKey(eventId, learningSource);
          const sheet = reviewSheets.current[key];
          if (!sheet) return;
          reviewSheets.current[key] = {
            ...sheet,
            files: sheet.files.map((file) =>
              file.fingerprint === fingerprint
                ? {
                    ...file,
                    saved_review: {
                      exposure: recipe.exposure,
                      temperature: recipe.temperature,
                      tint: recipe.tint,
                      process_version: file.photographer?.process_version ?? null,
                      camera_profile: file.photographer?.camera_profile ?? null,
                    },
                  }
                : file,
            ),
          };
        },

        getDraft: (eventId, fingerprint) =>
          drafts.current[draftKey(eventId, fingerprint)] ?? null,
        setDraft: (eventId, fingerprint, recipe) => {
          drafts.current[draftKey(eventId, fingerprint)] = { ...recipe };
        },
        clearDraft: (eventId, fingerprint) => {
          delete drafts.current[draftKey(eventId, fingerprint)];
        },
        forgetEvent: (eventId) => {
          for (const key of Object.keys(drafts.current)) {
            if (key.startsWith(`${eventId}:`)) {
              delete drafts.current[key];
            }
          }

          for (const key of Object.keys(reviewSheets.current)) {
            if (key.endsWith(`:${eventId}`)) {
              delete reviewSheets.current[key];
            }
          }

          setGalleryEventId((current) =>
            current === eventId ? "" : current,
          );
          setSelection((current) =>
            current?.eventId === eventId ? null : current,
          );
        },

        openPhoto: (eventId, fingerprint, learningSource) => {
          setSelection({ eventId, fingerprint, learningSource });
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
