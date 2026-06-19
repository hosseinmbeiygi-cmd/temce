"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";

interface AlphaStrategy {
  id: string;
  name: string;
  version: string;
  sharpe: number;
  returns: number;
  volatility: number;
  maxDrawdown: number;
  winRate: number;
  trades: number;
  status: "active" | "paper" | "disabled";
  description: string;
}

const FALLBACK_ALPHAS: AlphaStrategy[] = [
  { id: "mom-v3", name: "Momentum", version: "v3", sharpe: 2.14, returns: 34.5, volatility: 12.8, maxDrawdown: -8.2, winRate: 62, trades: 342, status: "active", description: "استراتژی مومنتوم بر اساس شتاب قیمتی ۳۰ روزه" },
  { id: "mr-v2", name: "Mean Reversion", version: "v2", sharpe: 1.87, returns: 28.2, volatility: 15.1, maxDrawdown: -11.5, winRate: 58, trades: 891, status: "active", description: "بازگشت به میانگین بر اساس انحراف از میانگین متحرک" },
  { id: "qi-v1", name: "Queue Imbalance", version: "v1", sharpe: 0.92, returns: 12.4, volatility: 18.6, maxDrawdown: -22.1, winRate: 51, trades: 56, status: "paper", description: "تحلیل عدم تعادل صف‌های خرید و فروش" },
  { id: "ml-v5", name: "ML Alpha", version: "v5", sharpe: 2.43, returns: 41.8, volatility: 14.2, maxDrawdown: -9.8, winRate: 65, trades: 1204, status: "active", description: "مدل یادگیری ماشین ترکیبی با ویژگی‌های تکنیکال و بنیادی" },
  { id: "arb-v1", name: "Statistical Arbitrage", version: "v1", sharpe: 1.56, returns: 22.7, volatility: 9.4, maxDrawdown: -5.6, winRate: 71, trades: 234, status: "paper", description: "آربیتراژ آماری بین نمادهای همبسته" },
  { id: "sent-v2", name: "Sentiment", version: "v2", sharpe: 1.23, returns: 18.9, volatility: 16.3, maxDrawdown: -14.7, winRate: 55, trades: 167, status: "disabled", description: "تحلیل احساسات اخبار و شبکه‌های اجتماعی" },
];

export default function AlphaPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [alphas] = useState<AlphaStrategy[]>(FALLBACK_ALPHAS);
  const [filter, setFilter] = useState<"all" | "active" | "paper" | "disabled">("all");

  const filtered = filter === "all" ? alphas : alphas.filter((a) => a.status === filter);

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-surface-100">استراتژی‌های آلفا</h1>
          <p className="text-sm text-surface-500 mt-1">مدیریت و مانیتورینگ استراتژی‌های معاملاتی</p>
        </div>

        <div className="flex gap-2 mb-4 flex-wrap">
          {([{ k: "all", l: "همه" }, { k: "active", l: "فعال" }, { k: "paper", l: "Paper" }, { k: "disabled", l: "غیرفعال" }] as const).map((t) => (
            <button key={t.k} onClick={() => setFilter(t.k)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === t.k ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{t.l}</button>
          ))}
        </div>

        <div className="grid gap-4">
          {filtered.map((a) => (
            <div key={a.id} className="glass-card p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <h3 className="font-bold text-surface-200">{a.name} <span className="text-surface-500 text-xs font-mono">{a.version}</span></h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.status === "active" ? "bg-accent-emerald/15 text-accent-emerald" :
                    a.status === "paper" ? "bg-accent-amber/15 text-accent-amber" :
                    "bg-surface-600/30 text-surface-400"
                  }`}>{a.status === "active" ? "فعال" : a.status === "paper" ? "Paper" : "غیرفعال"}</span>
                </div>
                <span className="text-xs text-surface-400">{a.trades} معامله</span>
              </div>
              <p className="text-xs text-surface-400 mb-4">{a.description}</p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                <div className="bg-white/5 rounded-lg p-2">
                  <div className={`text-sm font-bold font-mono ${a.sharpe > 1.5 ? "text-accent-emerald" : "text-accent-rose"}`}>{a.sharpe.toFixed(2)}</div>
                  <div className="text-xs text-surface-500">Sharpe</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-sm font-bold font-mono text-accent-emerald">{a.returns.toFixed(1)}%</div>
                  <div className="text-xs text-surface-500">بازده</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-sm font-bold font-mono text-accent-amber">{a.volatility.toFixed(1)}%</div>
                  <div className="text-xs text-surface-500">نوسان</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-sm font-bold font-mono text-accent-rose">{a.maxDrawdown.toFixed(1)}%</div>
                  <div className="text-xs text-surface-500">Max DD</div>
                </div>
                <div className="bg-white/5 rounded-lg p-2">
                  <div className="text-sm font-bold font-mono text-accent-cyan">{a.winRate}%</div>
                  <div className="text-xs text-surface-500">Win Rate</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
