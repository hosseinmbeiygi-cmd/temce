"use client";

import { useState, useMemo } from "react";
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
      markets: Record<string, { buy: number; sell: number; hold: number }>;
    };
    generated_at: string;
  };
}

const MARKET_LABELS: Record<string, string> = {
  stock: "سهام", gold: "طلا", currency: "ارز",
  crypto: "رمزارز", option: "آپشن", commodity: "کالا", ime: "بورس کالا",
};

const MARKET_COLORS: Record<string, string> = {
  stock: "#64FFDA", gold: "#FFD700", currency: "#FF6B6B",
  crypto: "#A78BFA", option: "#38BDF8", commodity: "#FB923C", ime: "#94A3B8",
};

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return n.toLocaleString("fa-IR");
  return n.toFixed(2);
}

function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export default function SignalsAllPage() {
  const [marketFilter, setMarketFilter] = useState("all");
  const [signalFilter, setSignalFilter] = useState("all");
  const [timeframeFilter, setTimeframeFilter] = useState("all");
  const [minConfidence, setMinConfidence] = useState(0.25);
  const [sortBy, setSortBy] = useState<"boosted_score" | "confidence" | "rule_score">("boosted_score");
  const [selectedSignal, setSelectedSignal] = useState<EnrichedSignal | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["signals-all", marketFilter, signalFilter, timeframeFilter, minConfidence, sortBy],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (marketFilter !== "all") params.set("market", marketFilter);
      if (signalFilter !== "all") params.set("signal", signalFilter);
      if (timeframeFilter !== "all") params.set("timeframe", timeframeFilter);
      params.set("min_confidence", String(minConfidence));
      params.set("sort_by", sortBy);
      params.set("limit", "200");

      const res = await apiGet<MultiMarketResponse>(`/multi-market-signals?${params.toString()}`);
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const signals = data?.signals ?? [];
  const summary = data?.summary;

  return (
    <AppLayout title="همه سیگنال‌ها" subtitle="سیگنال‌های خرید و فروش در تمام بازارها">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={marketFilter}
          onChange={(e) => setMarketFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه بازارها</option>
          {Object.entries(MARKET_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>

        <select
          value={signalFilter}
          onChange={(e) => setSignalFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه سیگنال‌ها</option>
          <option value="buy">خرید</option>
          <option value="sell">فروش</option>
          <option value="hold">خنثی</option>
        </select>

        <select
          value={timeframeFilter}
          onChange={(e) => setTimeframeFilter(e.target.value)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="all">همه بازه‌ها</option>
          <option value="daily">روزانه</option>
          <option value="2day">۲ روزه</option>
          <option value="3day">۳ روزه</option>
          <option value="weekly">هفتگی</option>
          <option value="monthly">ماهانه</option>
        </select>

        <div className="flex items-center gap-2 bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5">
          <span className="text-[10px] text-surface-500">حداقل اطمینان:</span>
          <input
            type="range"
            min="0"
            max="0.8"
            step="0.05"
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            className="w-20 accent-primary-500"
          />
          <span className="text-xs font-mono text-surface-300">{(minConfidence * 100).toFixed(0)}%</span>
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="bg-surface-800 border border-surface-700 text-surface-200 text-xs rounded-lg px-3 py-2 focus:border-primary-500 outline-none"
        >
          <option value="boosted_score">امتیاز ترکیبی</option>
          <option value="confidence">اطمینان</option>
          <option value="rule_score">امتیاز تکنیکال</option>
        </select>

        {isLoading && (
          <span className="text-xs text-surface-500 animate-pulse">در حال بارگذاری...</span>
        )}
        {data?.generated_at && (
          <span className="text-[10px] text-surface-600 mr-auto">
            {new Date(data.generated_at).toLocaleTimeString("fa-IR")}
          </span>
        )}
      </div>

      {/* Summary Stats */}
      {!isLoading && summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">کل</div>
            <div className="text-lg font-black text-surface-100">{summary.total_signals}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">خرید</div>
            <div className="text-lg font-black text-accent-emerald">{summary.buy_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">فروش</div>
            <div className="text-lg font-black text-accent-rose">{summary.sell_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">خنثی</div>
            <div className="text-lg font-black text-surface-400">{summary.hold_count}</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-[10px] text-surface-500 mb-1">بازارها</div>
            <div className="text-lg font-black text-surface-200">{Object.keys(summary.markets ?? {}).length}</div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="glass-card p-6 text-center border border-accent-rose/30">
          <span className="material-icons text-3xl text-accent-rose mb-2 block">error_outline</span>
          <p className="text-sm text-accent-rose">خطا در دریافت سیگنال‌ها</p>
        </div>
      )}

      {/* Signal List */}
      <Card
        title={`سیگنال‌ها (${signals.length})`}
        actions={
          <div className="flex gap-1">
            {(["all", "buy", "sell", "hold"] as const).map((f) => (
              <CardAction key={f} active={signalFilter === f} onClick={() => setSignalFilter(f)}>
                {f === "all" ? "همه" : f === "buy" ? "خرید" : f === "sell" ? "فروش" : "خنثی"}
              </CardAction>
            ))}
          </div>
        }
      >
        <SSRSafe style={{ overflowX: "auto" }}>
          {isLoading && (
            <div className="space-y-2 animate-pulse">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 bg-surface-800/30 rounded-lg" />
              ))}
            </div>
          )}

          {!isLoading && signals.length === 0 && (
            <div className="text-center py-12 text-surface-500">
              <span className="material-icons text-4xl mb-2 block">signal_cellular_alt</span>
              <p className="text-sm">هیچ سیگنالی با فیلترهای فعلی یافت نشد</p>
            </div>
          )}

          {!isLoading && signals.length > 0 && (
            <div className="space-y-2">
              {signals.map((s, i) => (
                <SignalCard
                  key={`${s.symbol}-${s.market}-${s.timeframe}-${i}`}
                  signal={s}
                  variant="full"
                  onClick={() => setSelectedSignal(s)}
                />
              ))}
            </div>
          )}
        </SSRSafe>
      </Card>

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
