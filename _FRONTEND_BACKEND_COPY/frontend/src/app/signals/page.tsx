"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
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

export default function SignalsPage() {
  const [selectedSignal, setSelectedSignal] = useState<EnrichedSignal | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["signals-top"],
    queryFn: async () => {
      const res = await apiGet<MultiMarketResponse>(
        "/multi-market-signals?limit=4&sort_by=boosted_score&min_confidence=0.25"
      );
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const signals = data?.signals ?? [];
  const summary = data?.summary;
  const topSignal = signals[0] ?? null;
  const otherSignals = signals.slice(1);

  return (
    <AppLayout title="سیگنال‌ها" subtitle="بهترین سیگنال‌های خرید و فروش در تمام بازارها">
      {/* Loading */}
      {isLoading && (
        <div className="space-y-4 animate-pulse">
          <div className="glass-card h-64" />
          <div className="grid grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass-card h-20" />
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="glass-card p-8 text-center border border-accent-rose/30">
          <span className="material-icons text-4xl text-accent-rose mb-3 block">error_outline</span>
          <p className="text-sm text-accent-rose mb-2">خطا در دریافت سیگنال‌ها</p>
          <p className="text-xs text-surface-500">لطفاً اتصال به سرور را بررسی کنید.</p>
        </div>
      )}

      {/* No signals */}
      {!isLoading && !error && signals.length === 0 && (
        <div className="glass-card p-12 text-center">
          <span className="material-icons text-5xl text-surface-600 mb-3 block">signal_cellular_alt</span>
          <p className="text-sm text-surface-400">هیچ سیگنالی یافت نشد</p>
          <p className="text-xs text-surface-600 mt-1">سیستم در حال تحلیل بازارها است...</p>
        </div>
      )}

      {!isLoading && !error && signals.length > 0 && (
        <>
          {/* Hero: Top Signal */}
          {topSignal && (
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <span className="material-icons text-accent-cyan text-lg">star</span>
                <span className="text-sm font-bold text-surface-300">بهترین سیگنال</span>
              </div>
              <SignalCard
                signal={topSignal}
                variant="hero"
                onClick={() => setSelectedSignal(topSignal)}
              />
            </div>
          )}

          {/* Quick Stats */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="glass-card p-4 text-center">
                <div className="text-[10px] text-surface-500 mb-1">کل سیگنال‌ها</div>
                <div className="text-2xl font-black text-surface-100">{summary.total_signals}</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-[10px] text-surface-500 mb-1">خرید</div>
                <div className="text-2xl font-black text-accent-emerald">{summary.buy_count}</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-[10px] text-surface-500 mb-1">فروش</div>
                <div className="text-2xl font-black text-accent-rose">{summary.sell_count}</div>
              </div>
              <div className="glass-card p-4 text-center">
                <div className="text-[10px] text-surface-500 mb-1">میانگین اطمینان</div>
                <div className="text-2xl font-black text-primary-300">{(summary.avg_confidence * 100).toFixed(0)}%</div>
              </div>
            </div>
          )}

          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
            <Link href="/signals/all" className="glass-card p-5 border border-surface-700/50 hover:border-primary-500/30 transition-all group">
              <div className="flex items-center gap-3">
                <span className="material-icons text-3xl text-primary-400 group-hover:text-primary-300">list</span>
                <div>
                  <div className="text-sm font-bold text-surface-200 group-hover:text-surface-100">همه سیگنال‌ها</div>
                  <div className="text-xs text-surface-500">سیگنال‌های تمام بازارها با ۱۱ ستون کامل</div>
                </div>
                <span className="material-icons text-surface-600 mr-auto">arrow_back</span>
              </div>
            </Link>
            <Link href="/signals/stocks" className="glass-card p-5 border border-surface-700/50 hover:border-accent-emerald/30 transition-all group">
              <div className="flex items-center gap-3">
                <span className="material-icons text-3xl text-accent-emerald group-hover:text-accent-emerald/80">show_chart</span>
                <div>
                  <div className="text-sm font-bold text-surface-200 group-hover:text-surface-100">سیگنال سهام</div>
                  <div className="text-xs text-surface-500">سیگنال‌های سهام با تمرکز بر day-trading</div>
                </div>
                <span className="material-icons text-surface-600 mr-auto">arrow_back</span>
              </div>
            </Link>
          </div>

          {/* Next Best Signals */}
          {otherSignals.length > 0 && (
            <div>
              <div className="text-xs font-bold text-surface-400 mb-3">سیگنال‌های بعدی</div>
              <div className="space-y-2">
                {otherSignals.map((s, i) => (
                  <SignalCard
                    key={`${s.symbol}-${s.market}-${i}`}
                    signal={s}
                    variant="compact"
                    onClick={() => setSelectedSignal(s)}
                  />
                ))}
              </div>
            </div>
          )}

          {data?.generated_at && (
            <div className="mt-4 text-[10px] text-surface-600 text-center">
              آخرین به‌روزرسانی: {new Date(data.generated_at).toLocaleString("fa-IR")}
            </div>
          )}
        </>
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
