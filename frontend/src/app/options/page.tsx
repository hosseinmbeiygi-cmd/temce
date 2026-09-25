"use client";

import { useState } from "react";
import {
  Zap,
  ArrowLeftRight,
  Brain,
  FlaskConical,
  ShieldCheck,
} from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import SignalsTab from "./components/tabs/SignalsTab";
import ChainTab from "./components/tabs/ChainTab";
import ForecastTab from "./components/tabs/ForecastTab";
import BacktestTab from "./components/tabs/BacktestTab";
import RiskTab from "./components/tabs/RiskTab";

type TabId = "signals" | "chain" | "forecast" | "backtest" | "risk";

const TABS: { id: TabId; label: string; Icon: typeof Zap }[] = [
  { id: "signals", label: "سیگنال‌ها", Icon: Zap },
  { id: "chain", label: "زنجیره اختیار", Icon: ArrowLeftRight },
  { id: "forecast", label: "پیش‌بینی AI", Icon: Brain },
  { id: "backtest", label: "بک‌تست", Icon: FlaskConical },
  { id: "risk", label: "ریسک و وجه تضمین", Icon: ShieldCheck },
];

export default function OptionsPage() {
  const [tab, setTab] = useState<TabId>("signals");

  return (
    <AppLayout title="بازار اختیار معامله" subtitle="سیگنال، زنجیره، پیش‌بینی، بک‌تست و ریسک — در یک نگاه">
      <div className="flex gap-1 mb-6 bg-slate-900 border border-slate-800 rounded-2xl p-1.5 overflow-x-auto">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 min-w-fit px-4 py-2.5 rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-2 whitespace-nowrap ${
              tab === id
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-[480px]">
        {tab === "signals" && <SignalsTab />}
        {tab === "chain" && <ChainTab />}
        {tab === "forecast" && <ForecastTab />}
        {tab === "backtest" && <BacktestTab />}
        {tab === "risk" && <RiskTab />}
      </div>

      <div className="mt-8 text-center text-[10px] text-slate-600">
        معاملات اختیار ریسک دارد • این صفحه توصیه خرید/فروش نیست
      </div>
    </AppLayout>
  );
}
