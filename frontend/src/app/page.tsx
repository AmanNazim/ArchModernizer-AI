"use client";

import { useState } from "react";
import CodeModernizer from "@/components/CodeModernizer";
import CloudOptimizer from "@/components/CloudOptimizer";
import OnboardingChat from "@/components/OnboardingChat";

/** Tab definitions */
const TABS = [
  { id: "modernizer", label: "Code Modernizer", icon: "⚙️" },
  { id: "cloud", label: "Cloud Optimizer", icon: "☁️" },
  { id: "chat", label: "Onboarding Chat", icon: "💬" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("modernizer");

  return (
    <div className="flex flex-col min-h-screen">
      {/* ── Header ── */}
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <span className="text-2xl">🏗️</span>
          <h1 className="text-xl font-semibold tracking-tight">
            ArchModernizer <span className="text-blue-400">AI</span>
          </h1>
          <span className="ml-auto text-xs text-gray-500">
            Powered by FastAPI + Next.js
          </span>
        </div>
      </header>

      {/* ── Tab bar ── */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6">
        <div className="max-w-7xl mx-auto flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === tab.id
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* ── Tab content ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        {activeTab === "modernizer" && <CodeModernizer />}
        {activeTab === "cloud" && <CloudOptimizer />}
        {activeTab === "chat" && <OnboardingChat />}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 bg-gray-900 py-3 text-center text-xs text-gray-600">
        ArchModernizer AI — IBM Bob 2.0 demo
      </footer>
    </div>
  );
}
