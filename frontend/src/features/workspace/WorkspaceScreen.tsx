"use client";

import { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import DashboardScreen from "@/features/dashboard/DashboardScreen";
import EventsScreen from "@/features/events/EventsScreen";
import GalleryScreen from "@/features/gallery/GalleryScreen";
import DarkroomScreen from "@/features/darkroom/DarkroomScreen";
import ProfileScreen from "@/features/profile/ProfileScreen";
import TrainingScreen from "@/features/training/TrainingScreen";
import { TestingNavProvider } from "@/features/testing/TestingNav";
import { WorkspaceNavProvider } from "./workspace-nav";
import type { WorkspaceView } from "./workspace.types";

const titles: Record<WorkspaceView, string> = {
  dashboard: "ראשי",
  events: "אירועים",
  gallery: "גלריה",
  darkroom: "חדר עריכה",
  profile: "הפרופיל שלי",
  training: "למידה",
};

function ActiveScreen({ view }: { view: WorkspaceView }) {
  switch (view) {
    case "events":
      return <EventsScreen />;
    case "darkroom":
      return <DarkroomScreen />;
    case "profile":
      return <ProfileScreen />;
    case "training":
      return <TrainingScreen />;
    case "dashboard":
    default:
      return <DashboardScreen />;
  }
}

export default function WorkspaceScreen() {
  const [activeView, setActiveView] = useState<WorkspaceView>("dashboard");
  const [galleryMounted, setGalleryMounted] = useState(false);

  function selectView(view: WorkspaceView) {
    if (view === "gallery") {
      setGalleryMounted(true);
    }
    setActiveView(view);
  }

  return (
    <TestingNavProvider
      onOpenDarkroom={() => selectView("darkroom")}
      onOpenGallery={() => selectView("gallery")}
    >
    <WorkspaceNavProvider onSelect={selectView}>
      <AppShell
        activeView={activeView}
        title={titles[activeView]}
        immersive={activeView === "darkroom"}
        onSelect={selectView}
      >
        {galleryMounted && (
          <div
            hidden={activeView !== "gallery"}
            style={{ minHeight: "100%" }}
            aria-hidden={activeView !== "gallery"}
          >
            <GalleryScreen />
          </div>
        )}

        {activeView !== "gallery" && <ActiveScreen view={activeView} />}
      </AppShell>
    </WorkspaceNavProvider>
    </TestingNavProvider>
  );
}
