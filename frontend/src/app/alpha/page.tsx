"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractItems } from "@/lib/api";

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

export default function AlphaPage() {
  const [filter, setFilter] = useState<"all" | "active" | "paper" | "disabled">("all");

  // Real strategies only: fabricated performance numbers used to be returned
  // from this query's catch/empty branches and rendered as if live.
  const { data: alphas, isLoading, isError } = useQuery({
    queryKey: ["alpha-strategies"],
    queryFn: async () => {
      const data = await apiGet<{ success: boolean; data: { items: AlphaStrategy[] } }>('/alpha');
      return extractItems<AlphaStrategy>(data);
    },
  });

  const filtered = alphas?.filter((a) => filter === "all" || a.status === filter);

  return (
    <AppLayout title="استراتژی‌های آلفا" subtitle="مدیریت و مانیتورینگ استراتژی‌های معاملاتی">
      <div className="flex gap-2 mb-4 flex-wrap">
        {([{ k: "all", l: "همه" }, { k: "active", l: "فعال" }, { k: "paper", l: "Paper" }, { k: "disabled", l: "غیرفعال" }] as const).map((t) => (
          <button key={t.k} onClick={() => setFilter(t.k)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${filter === t.k ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>{t.l}</button>
        ))}
      </div>

      <div className="grid gap-4">
        {isLoading ? (
          [1,2,3].map(i => <Skeleton key={i} className="h-40 w-full rounded-xl" />)
        ) : isError ? (
          <div role="alert" aria-live="polite" className="glass-card p-8 text-center">
            <span className="material-icons text-4xl text-accent-rose mb-2">wifi_off</span>
            <p className="text-sm text-surface-400">دریافت استراتژی‌های آلفا از سرور ناموفق بود — داده‌ای برای نمایش وجود ندارد.</p>
          </div>
        ) : filtered && filtered.length > 0 ? (
          filtered.map((a) => (
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
          ))
        ) : (
          <div className="text-center py-12 text-surface-500">هیچ استراتژی یافت نشد</div>
        )}
      </div>
    </AppLayout>
  );
}
