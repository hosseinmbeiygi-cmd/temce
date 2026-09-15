"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import OptionsDashboard from "./components/OptionsDashboard";
import StrategyAnalyzer from "./components/StrategyAnalyzer";
import LiveChainPanel from "./components/LiveChainPanel";
import AnalyticsPanel from "./components/AnalyticsPanel";
import ProfessionalTools from "./components/ProfessionalTools";
import LearnPanel from "./components/LearnPanel";
import type { TabId } from "./components/types";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "dashboard", label: "\u062f\u0627\u0634\u0628\u0648\u0631\u062f", icon: "grid_view" },
  { id: "analyze", label: "\u062a\u062d\u0644\u06cc\u0644 \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc", icon: "analytics" },
  { id: "chain", label: "\u0632\u0646\u062c\u06cc\u0631\u0647 \u0632\u0646\u062f\u0647", icon: "link" },
  { id: "analytics", label: "\u0622\u0646\u0627\u0644\u06cc\u062a\u06cc\u06a9\u0633", icon: "insights" },
  { id: "professional", label: "\u0627\u0628\u0632\u0627\u0631 \u062d\u0631\u0641\u0647\u200c\u0627\u06cc", icon: "build" },
  { id: "learn", label: "\u0622\u0645\u0648\u0632\u0634", icon: "school" },
];

export default function OptionsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");

  return (
    <AppLayout title="\u0627\u062e\u062a\u06cc\u0627\u0631 \u0645\u0639\u0627\u0645\u0644\u0647" subtitle="\u067e\u0644\u062a\u0641\u0631\u0645 \u062a\u062d\u0644\u06cc\u0644 \u0648 \u0645\u0639\u0627\u0645\u0644\u0647 \u0627\u062e\u062a\u06cc\u0627\u0631\u0627\u062a \u0628\u0627\u0632\u0627\u0631 \u0633\u0631\u0645\u0627\u06cc\u0647 \u0627\u06cc\u0631\u0627\u0646">
      {/* Tab Bar */}
      <div className="flex gap-1 mb-6 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap"
          >
            <span className="material-icons text-sm">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "dashboard" && <OptionsDashboard />}
      {activeTab === "analyze" && <StrategyAnalyzer />}
      {activeTab === "chain" && <LiveChainPanel />}
      {activeTab === "analytics" && <AnalyticsPanel />}
      {activeTab === "professional" && <ProfessionalTools />}
      {activeTab === "learn" && <LearnPanel />}
    </AppLayout>
  );
}
