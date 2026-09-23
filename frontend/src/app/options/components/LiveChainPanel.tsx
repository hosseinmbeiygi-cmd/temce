"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import type { ChainData } from "./types";
import { fmt } from "./helpers";

const UNDERLYING_PRESETS = [
  "\u0630\u0648\u0628", "\u0641\u062e\u0632", "\u0648\u0627\u0645\u062f", "\u06a9\u0686\u0627\u062f",
  "\u0634\u067e\u0646\u0627", "\u0648\u0628\u0635\u0627", "\u0641\u0627\u062e\u0631", "\u0648\u067e\u0645\u06cc",
];

export default function LiveChainPanel() {
  const [underlying, setUnderlying] = useState("");

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["options", "chain", underlying],
    queryFn: ({ signal }) =>
      apiGet<{ success: boolean; data: ChainData }>(
        `/options/live/chain/${encodeURIComponent(underlying)}?limit=50`,
        undefined,
        signal,
      ),
    enabled: !!underlying,
    refetchInterval: 15_000,
    // Keep the previous symbol's table visible (marked stale) while the next
    // symbol loads, instead of flashing a skeleton — combined with the signal
    // above, a slow response for the OLD symbol can never overwrite the NEW
    // symbol's state: the aborted request is discarded by React Query.
    placeholderData: (prev) => prev,
  });

  const chain = data?.data;
  const calls = chain?.calls ?? [];
  const puts = chain?.puts ?? [];

  return (
    <div className="space-y-4">
      {/* Underlying Selector */}
      <Card title="نماد پایه">
        <div className="flex flex-wrap gap-2">
          {UNDERLYING_PRESETS.map((sym) => (
            <button
              key={sym}
              onClick={() => setUnderlying(sym)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${underlying === sym ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-300 border-surface-700/30 hover:bg-surface-700"}`}
            >
              {sym}
            </button>
          ))}
          <input
            value={underlying}
            onChange={(e) => setUnderlying(e.target.value.toUpperCase())}
            placeholder="سایر نمادها..."
            className="flex-1 min-w-[120px] bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-1.5 text-xs text-surface-200"
          />
        </div>
      </Card>

      {!underlying && (
        <div className="flex items-center justify-center h-32 text-surface-500 text-sm">
          یک نماد پایه انتخاب کنید
        </div>
      )}

      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {/* Explicit error banner — the panel never silently renders fake data. */}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-accent-rose/40 bg-accent-rose/10 px-4 py-3 text-sm text-accent-rose flex items-center justify-between gap-3"
        >
          <div>
            <p className="font-bold">خطا در دریافت داده‌ها از سرور</p>
            <p className="text-xs opacity-80 mt-0.5" dir="ltr">{(error as Error)?.message}</p>
          </div>
          <button
            onClick={() => refetch()}
            className="shrink-0 px-3 py-1.5 rounded-lg bg-accent-rose/20 hover:bg-accent-rose/30 text-xs font-bold"
          >
            تلاش مجدد
          </button>
        </div>
      )}

      {/* Data-quality warning: server responded but the chain is empty. */}
      {chain && !isLoading && calls.length === 0 && puts.length === 0 && (
        <div
          role="status"
          className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-400"
        >
          <p className="font-bold">هشدار: داده‌ای برای این نماد یافت نشد</p>
          <p className="text-xs opacity-80 mt-0.5">
            سرور پاسخ داد اما هیچ قرارداد فعالی برای «{chain.underlying}» ثبت نشده است.
          </p>
        </div>
      )}

      {chain && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">{chain.underlying}</p>
              <p className="text-lg font-bold text-surface-200" dir="ltr">{fmt(chain.underlying_price)}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">Call‌ها</p>
              <p className="text-lg font-bold text-accent-emerald" dir="ltr">{calls.length}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">Put‌ها</p>
              <p className="text-lg font-bold text-accent-rose" dir="ltr">{puts.length}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">قرارداد</p>
              <p className="text-lg font-bold text-surface-200" dir="ltr">{fmt(chain.total_contracts)}</p>
            </Card>
          </div>

          {/* Options Chain Table */}
          <Card
            title="زنجیره اختیار معامله"
            actions={
              isFetching ? (
                <span className="text-[10px] text-surface-500">در حال به‌روزرسانی...</span>
              ) : undefined
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]" dir="rtl">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700/50">
                    <th className="text-right py-2 px-2">نماد</th>
                    <th className="text-right py-2 px-2">نوع</th>
                    <th className="text-left py-2 px-2">اعمال</th>
                    <th className="text-left py-2 px-2">قیمت</th>
                    <th className="text-left py-2 px-2">حجم</th>
                    <th className="text-left py-2 px-2">علائق باز</th>
                    <th className="text-left py-2 px-2">تا سررسید</th>
                    <th className="text-left py-2 px-2">بید/خواست</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ...calls.map(c => ({ ...c, rowType: "call" as const })),
                    ...puts.map(p => ({ ...p, rowType: "put" as const })),
                  ].map((opt, i) => (
                    <tr
                      key={i}
                      className="border-b border-surface-800/30 hover:bg-surface-800/30"
                    >
                      <td className="py-2 px-2 font-bold">{opt.symbol}</td>
                      <td className="py-2 px-2">
                        {opt.rowType === "call" ? "Call" : "Put"}
                      </td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.strike)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.price)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.volume)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.oi)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{opt.days_to_expiry} روز</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">
                        {fmt(opt.bid)} / {fmt(opt.ask)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
