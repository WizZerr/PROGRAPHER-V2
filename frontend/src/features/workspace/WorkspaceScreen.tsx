"use client";

import { useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import DashboardScreen from "@/features/dashboard/DashboardScreen";
import EventsScreen from "@/features/events/EventsScreen";
import GalleryScreen from "@/features/gallery/GalleryScreen";
import DarkroomScreen from "@/features/darkroom/DarkroomScreen";
import ProfileScreen from "@/features/profile/ProfileScreen";
import TrainingScreen from "@/features/training/TrainingScreen";
import type { WorkspaceView } from "./workspace.types";

const titles: Record<WorkspaceView, string> = {
  dashboard: "לוח בקרה",
  events: "אירועים",
  gallery: "גלריה",
  darkroom: "חדר עריכה",
  profile: "הפרופיל שלי",
  training: "מעבדת למידה",
};

export default function WorkspaceScreen() {
  const [activeView, setActiveView] = useState<WorkspaceView>("dashboard");

  const screen = useMemo(() => {
    switch (activeView) {
      case "events":
        return <EventsScreen />;
      case "gallery":
        return <GalleryScreen />;
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
  }, [activeView]);

  return (
    <AppShell
      activeView={activeView}
      title={titles[activeView]}
      onSelect={setActiveView}
    >
      {screen}
    </AppShell>
  );
}
