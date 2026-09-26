"use client";

import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import TopNav from "@/components/layout/TopNav";
import IngestionPanel from "@/components/IngestionPanel";
import CodeModernizer from "@/components/CodeModernizer";
import CloudOptimizer from "@/components/CloudOptimizer";
import OnboardingChat from "@/components/OnboardingChat";

type ViewId = "setup" | "modernizer" | "cloud" | "chat";

const VIEW_TITLES: Record<ViewId, string> = {
  setup: "Project Setup",
  modernizer: "Code Modernizer",
  cloud: "Cloud Optimizer",
  chat: "Onboarding Chat",
};

export default function Home() {
  const [activeView, setActiveView] = useState<ViewId>("setup");

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ── */}
      <Sidebar
        activeView={activeView}
        onNavigate={(view) => setActiveView(view as ViewId)}
      />

      {/* ── Main area ── */}
      <div className="flex flex-col flex-1 min-w-0">
        <TopNav title={VIEW_TITLES[activeView]} />

        <main className="flex-1 px-6 py-8 overflow-auto">
          {activeView === "setup" && <IngestionPanel />}
          {activeView === "modernizer" && <CodeModernizer />}
          {activeView === "cloud" && <CloudOptimizer />}
          {activeView === "chat" && <OnboardingChat />}
        </main>

        <footer className="border-t border-gray-800 bg-gray-900 py-3 text-center text-xs text-gray-600">
          ArchModernizer AI — IBM Bob 2.0 demo
        </footer>
      </div>
    </div>
  );
}
