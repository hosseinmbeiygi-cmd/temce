"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import SSRSafe from "@/components/SSRSafe";
import SignalCard from "@/components/signals/SignalCard";
import SignalDetailModal from "@/components/signals/SignalDetailModal";
import type { EnrichedSignal } from "@/lib/types";

interface MultiMarketResponse {
  success: boolean;
  data?: {
    signals: EnrichedSignal[];
    summary: {
      total_signals: number;
      buy_count: number;
      sell_count: number;
      hold_count: number;
      avg_confidence: number;
    };
    accuracy: Record<string, number>;
    generated_at: string;
  };
}

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return n.toLocaleString("fa-IR");
  return n.toFixed(2);
}

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export default function SignalsStocksPage() {
  const [timeframe, setTimeframe] = useState<"daily" | "2day" | "all">("daily");
  const [signalFilter, setSignalFilter] = useState<"all" | "buy" | "sell" | "hold">("buy");
  const [selectedSignal, setSelectedSignal] = useState<EnrichedSignal | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["signals-stocks", timeframe, signalFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("market", "stock");
      params.set("min_confidence", "0.2");
      params.set("sort_by", "boosted_score");
      params.set("limit", "100");
      if (timeframe !== "all") params.set("timeframe", timeframe);
      if (signalFilter !== "all") params.set("signal", signalFilter);

      const res = await apiGet<MultiMarketResponse>(`/multi-market-signals?${params.toString()}`);
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const signals = data?.signals ?? [];
  const summary = data?.summary;
  const accuracy = data?.accuracy ?? {};

  // Group signals by symbol for stock-specific display
  const signalsBySymbol = signals.reduce<Record<string, EnrichedSignal[]>>((acc, s) => {
    if (!acc[s.symbol]) acc[s.symbol] = [];
    acc[s.symbol].push(s);
    return acc;
  }, {});

  return (
    <AppLayout title="سیگنال سهام" subtitle="سیگنال‌های سهام با تمرکز بر معاملات کوتاه‌مدت (day-trading)">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex bg-surface-800 border border-surface-700 rounded-lg overflow-hidden">
          {(["daily", "2day", "all"] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-4 py-2 text-xs font-medium transition-colors ${
                timeframe === tf
                  ? "bg-primary-600/30 text-primary-300"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-700/50"
              }`}
            >
              {tf === "daily" ? "روزانه" : tf === "2day" ? "۲ روزه" : "همه"}
            </button>
          ))}
        </div>

        <div className="flex bg-surface-800 border border-surface-700 rounded-lg overflow-hidden">
          {(["all", "buy", "sell", "hold"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setSignalFilter(f)}
              className={`px-3 py-2 text-xs font-medium transition-colors ${
                signalFilter === f
                  ? "bg-primary-600/30 text-primary-300"
                  : "text-surface-400 hover:text-surface-200 hover:bg-surface-700/50"
              }`}
            >
              {f === "all" ? "همه" : f === "buy" ? "خرید" : f === "sell" ? "فروش" : "خنثی"}
            </button>
          ))}
        </div>

        {isLoading && (
          <span className="text-xs text-surface-500 animate-pulse">در حال بارگذاری...</span>
        )}
        {data?.generated_at && (
          <span className="text-[10px] text-surface-600 mr-auto">
            {new Date(data.generated_at).toLocaleTimeString("fa-IR")}
          </span>
        )}
      </div>

      {/* Stock Accuracy */}
      {!isLoading && accuracy.stock != null && (
        <div className="glass-card p-3 mb-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="material-icons text-accent-emerald">verified</span>
            <span className="text-xs text-surface-400">دقت سیگنال سهام:</span>
            <span className="text-sm font-black text-accent-emerald">{accuracy.stock.toFixed(0)}%</span>
          </div>
          {summary && (
            <>
              <span className="text-surface-700">|</span>
              <span className="text-xs text-surface-400">
                کل: <span className="text-surface-200 font-mono">{summary.total_signals}</span>
              </span>
              <span className="text-xs text-accent-emerald">
                خرید: <span className="font-mono">{summary.buy_count}</span>
              </span>
              <span className="text-xs text-accent-rose">
                فروش: <span className="font-mono">{summary.sell_count}</span>
              </span>
            </>
          )}
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="glass-card p-6 text-center border border-accent-rose/30">
          <span className="material-icons text-3xl text-accent-rose mb-2 block">error_outline</span>
          <p className="text-sm text-accent-rose">خطا در دریافت سیگنال‌های سهام</p>
        </div>
      )}

      {/* Stock Signals */}
      {!isLoading && signals.length === 0 && !error && (
        <div className="glass-card p-12 text-center">
          <span className="material-icons text-5xl text-surface-600 mb-3 block">show_chart</span>
          <p className="text-sm text-surface-400">هیچ سیگنال سهامی یافت نشد</p>
          <p className="text-xs text-surface-600 mt-1">فیلترها را تغییر دهید یا منتظر به‌روزرسانی باشید.</p>
        </div>
      )}

      {!isLoading && signals.length > 0 && (
        <div className="space-y-4">
          {Object.entries(signalsBySymbol).map(([symbol, symbolSignals]) => {
            const mainSignal = symbolSignals[0];
            const daySignal = symbolSignals.find((s) => s.timeframe === "daily");
            const twoDaySignal = symbolSignals.find((s) => s.timeframe === "2day");

            return (
              <div key={symbol} className="glass-card p-4 border border-surface-700/50">
                {/* Symbol Header */}
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">📈</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-black text-surface-100">{mainSignal.symbol}</span>
                      <span className="text-xs text-surface-500">{mainSignal.name}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs font-mono text-surface-300">{fmtPrice(mainSignal.price)}</span>
                      <span className={`text-xs font-mono ${mainSignal.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {fmtPct(mainSignal.change_pct)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Daily + 2-Day Signals Side by Side */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Daily Signal */}
                  {daySignal && (
                    <div className="p-3 rounded-lg bg-surface-800/30 border border-surface-700/30">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-600/20 text-primary-300 font-bold">روزانه</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                          daySignal.direction === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                          daySignal.direction === "sell" ? "bg-accent-rose/15 text-accent-rose" :
                          "bg-surface-600/30 text-surface-400"
                        }`}>
                          {daySignal.direction === "buy" ? "خرید" : daySignal.direction === "sell" ? "فروش" : "خنثی"}
                        </span>
                        {daySignal.decision_grade && (
                          <span className={`text-[10px] px-1 py-0.5 rounded border font-bold ${
                            daySignal.decision_grade === "A+" || daySignal.decision_grade === "A"
                              ? "border-accent-emerald/30 text-accent-emerald"
                              : "border-accent-amber/30 text-accent-amber"
                          }`}>{daySignal.decision_grade}</span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div>
                          <span className="text-surface-500">ورود: </span>
                          <span className="text-surface-200">{daySignal.entry_zone}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">ضرر: </span>
                          <span className="text-accent-rose">{daySignal.stop_loss}</span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-surface-500">اهداف: </span>
                          <span className="text-accent-emerald">{daySignal.targets}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">R/R: </span>
                          <span className="text-primary-300 font-bold">{daySignal.risk_reward}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">اطمینان: </span>
                          <span className="text-surface-200 font-mono">{(daySignal.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="mt-2 text-[10px] text-surface-400 truncate">{daySignal.reason}</div>
                    </div>
                  )}

                  {/* 2-Day Signal */}
                  {twoDaySignal && (
                    <div className="p-3 rounded-lg bg-surface-800/30 border border-surface-700/30">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-cyan/20 text-accent-cyan font-bold">۲ روزه</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                          twoDaySignal.direction === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                          twoDaySignal.direction === "sell" ? "bg-accent-rose/15 text-accent-rose" :
                          "bg-surface-600/30 text-surface-400"
                        }`}>
                          {twoDaySignal.direction === "buy" ? "خرید" : twoDaySignal.direction === "sell" ? "فروش" : "خنثی"}
                        </span>
                        {twoDaySignal.decision_grade && (
                          <span className={`text-[10px] px-1 py-0.5 rounded border font-bold ${
                            twoDaySignal.decision_grade === "A+" || twoDaySignal.decision_grade === "A"
                              ? "border-accent-emerald/30 text-accent-emerald"
                              : "border-accent-amber/30 text-accent-amber"
                          }`}>{twoDaySignal.decision_grade}</span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div>
                          <span className="text-surface-500">ورود: </span>
                          <span className="text-surface-200">{twoDaySignal.entry_zone}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">ضرر: </span>
                          <span className="text-accent-rose">{twoDaySignal.stop_loss}</span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-surface-500">اهداف: </span>
                          <span className="text-accent-emerald">{twoDaySignal.targets}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">R/R: </span>
                          <span className="text-primary-300 font-bold">{twoDaySignal.risk_reward}</span>
                        </div>
                        <div>
                          <span className="text-surface-500">اطمینان: </span>
                          <span className="text-surface-200 font-mono">{(twoDaySignal.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                      <div className="mt-2 text-[10px] text-surface-400 truncate">{twoDaySignal.reason}</div>
                    </div>
                  )}

                  {/* If no daily/2day, show other timeframes */}
                  {!daySignal && !twoDaySignal && symbolSignals.slice(0, 2).map((s, i) => (
                    <div key={i} className="p-3 rounded-lg bg-surface-800/30 border border-surface-700/30">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-600/30 text-surface-400 font-bold">{s.timeframe}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                          s.direction === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                          s.direction === "sell" ? "bg-accent-rose/15 text-accent-rose" :
                          "bg-surface-600/30 text-surface-400"
                        }`}>
                          {s.direction === "buy" ? "خرید" : s.direction === "sell" ? "فروش" : "خنثی"}
                        </span>
                      </div>
                      <div className="text-[10px] text-surface-400">{s.reason}</div>
                    </div>
                  ))}
                </div>

                {/* Full Details Button */}
                <button
                  onClick={() => setSelectedSignal(mainSignal)}
                  className="mt-3 text-[10px] text-primary-400 hover:text-primary-300 transition-colors"
                >
                  مشاهده جزئیات کامل →
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
        />
      )}
    </AppLayout>
  );
}
