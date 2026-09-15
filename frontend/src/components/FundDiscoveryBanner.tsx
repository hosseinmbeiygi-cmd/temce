"use client";

/**
 * 🔄 FundDiscoveryBanner — نوار وضعیت کشف/همگام‌سازی Universe صندوق‌ها.
 *
 * در اولین باز شدن صفحه صندوق‌ها، universe به‌صورت JIT از منبع رسمی
 * ساخته می‌شود (Read-Through). این کامپوننت فقط وضعیت را نمایش می‌دهد —
 * هیچ مسدودسازی یا پنل ادمینی لازم نیست (In-Page Self-Contained).
 */

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

interface MonitoringData {
  universe_count: number;
  nav_history_rows: number;
  holdings_rows: number;
  scores_rows: number;
  quarantine_unreviewed: number;
  stale_quotes: number;
  engine_version: string;
}

export default function FundDiscoveryBanner() {
  const { data, isLoading } = useQuery({
    queryKey: ["fund-v2-monitoring"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ data: MonitoringData }>("/funds/v2/monitoring");
        return res?.data ?? null;
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  // API قدیمی یا در دسترس نیست → نوار مخفی (Zero Breaking Changes)
  if (!data || isLoading) return null;

  const isEmpty = data.universe_count === 0;
  const hasQuarantine = data.quarantine_unreviewed > 0;

  if (isEmpty) {
    return (
      <div className="glass-card p-3 mb-4 flex items-center gap-3 border-primary-500/30">
        <span className="w-2.5 h-2.5 rounded-full bg-primary-400 animate-ping shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-surface-200">در حال کشف خودکار صندوق‌های بازار…</p>
          <p className="text-[10px] text-surface-500">
            Universe کامل از منبع رسمی دریافت و در دیتابیس ثبت می‌شود — نیازی به اقدام شما نیست.
          </p>
        </div>
        <div className="hidden sm:block h-1.5 w-32 bg-surface-800 rounded-full overflow-hidden">
          <div className="h-full w-1/2 bg-primary-500/70 rounded-full animate-[shimmer_1.5s_infinite]" />
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-2.5 mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-surface-500">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald" />
        Universe: <b className="text-surface-300 font-mono">{data.universe_count.toLocaleString("fa-IR")}</b> صندوق
      </span>
      <span>NAV: <b className="text-surface-300 font-mono">{data.nav_history_rows.toLocaleString("fa-IR")}</b></span>
      <span>دارایی‌ها: <b className="text-surface-300 font-mono">{data.holdings_rows.toLocaleString("fa-IR")}</b></span>
      <span>امتیازها: <b className="text-surface-300 font-mono">{data.scores_rows.toLocaleString("fa-IR")}</b></span>
      {hasQuarantine && (
        <span className="text-accent-amber">
          ⚠️ {data.quarantine_unreviewed.toLocaleString("fa-IR")} رکورد در قرنطینه
        </span>
      )}
      <span className="ms-auto font-mono text-surface-600" dir="ltr">
        {data.engine_version}
      </span>
    </div>
  );
}
