"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import OptionsDashboard from "./components/OptionsDashboard";
import StrategyAnalyzer from "./components/StrategyAnalyzer";
import LiveChainPanel from "./components/LiveChainPanel";
import AnalyticsPanel from "./components/AnalyticsPanel";
import ProfessionalTools from "./components/ProfessionalTools";
import ForecastPanel from "./components/ForecastPanel";
import LearnPanel from "./components/LearnPanel";

type TabId = "dashboard" | "strategies" | "chain" | "analytics" | "professional" | "forecast" | "learn";

const TABS: { id: TabId; label: string; icon: string; desc: string }[] = [
  { id: "dashboard", label: "داشبورد", icon: "📊", desc: "نمای کلی بازار" },
  { id: "strategies", label: "استراتژی‌ها", icon: "♟️", desc: "سازنده و تحلیل" },
  { id: "chain", label: "زنجیره اختیار", icon: "🔗", desc: "داده زنده" },
  { id: "analytics", label: "تحلیل پیشرفته", icon: "🧮", desc: "یونان، آربیتراژ" },
  { id: "professional", label: "ابزار حرفه‌ای", icon: "⚡", desc: "کارمزد، سایزینگ، IV" },
  { id: "forecast", label: "پیش‌بینی", icon: "🔮", desc: "۳۰روزه + سیگنال" },
  { id: "learn", label: "آموزش", icon: "📚", desc: "واژگان و فرمول" },
];

export default function OptionsPage() {
  const [tab, setTab] = useState<TabId>("dashboard");

  return (
    <AppLayout title="📊 بازار اختیار معامله" subtitle="تحلیل، استراتژی و ابزارهای حرفه‌ای اختیار — نسخه حرفه‌ای یکپارچه">
      {/* Professional Tab Bar */}
      <div className="flex gap-1 mb-6 bg-surface-900/60 backdrop-blur rounded-2xl p-1.5 border border-surface-700/50 overflow-x-auto shadow-lg shadow-black/10">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 min-w-fit px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex flex-col items-center gap-0.5 whitespace-nowrap ${
              tab === t.id
                ? "bg-primary-600 text-white shadow-md shadow-primary-600/20"
                : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
            }`}
          >
            <span className="text-sm leading-none">{t.icon}</span>
            <span>{t.label}</span>
            <span className={`text-[9px] font-normal ${tab === t.id ? "text-white/70" : "text-surface-500"}`}>{t.desc}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="min-h-[500px]">
        {tab === "dashboard" && <OptionsDashboard />}
        {tab === "strategies" && <StrategyAnalyzer />}
        {tab === "chain" && <LiveChainPanel />}
        {tab === "analytics" && <AnalyticsPanel />}
        {tab === "professional" && <ProfessionalTools />}
        {tab === "forecast" && <ForecastPanel />}
        {tab === "learn" && <LearnPanel />}
      </div>

      {/* Footer hint */}
      <div className="mt-8 text-center text-[10px] text-surface-500">
        داده‌های زنجیره از <span className="text-surface-300">brsapi_option_snapshots</span> به‌صورت زنده • تسویه T+2 • کارمزد خرید ۰.۱۲۵٪ / فروش ۰.۶۲۵٪
      </div>
    </AppLayout>
  );
}
