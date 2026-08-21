"use client";

import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, extractArray } from "@/lib/api";
import { fmtInt, fmtPct } from "@/lib/market-format";
import { DeltaBadge } from "@/components/dashboard/primitives";

interface IndexRow {
  id: number;
  name: string;
  index_value: number;
  index_change: number;
  index_change_pct: number;
  time: string;
}

export default function MarketIndicesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["market-indices"],
    queryFn: async () => apiGet<unknown>("/market/indices"),
    refetchInterval: 15000,
  });

  const rows: IndexRow[] = data
    ? extractArray((data as { data?: unknown }).data) as IndexRow[]
    : [];

  return (
    <AppLayout>
      <div className="space-y-6 p-4">
        <h1 className="text-2xl font-bold">شاخص‌های بازار</h1>
        <p className="text-sm text-ink-3">شاخص کل، هموزن و شاخص‌های تخصصی بازار بورس تهران</p>

        {isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-soft" />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-3 text-right font-bold">نام شاخص</th>
                  <th className="py-3 text-left font-bold">مقدار</th>
                  <th className="py-3 text-left font-bold">تغییر</th>
                  <th className="py-3 text-left font-bold">درصد</th>
                  <th className="py-3 text-left font-bold">زمان</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-line/50 hover:bg-soft/50">
                    <td className="py-3 font-semibold">{r.name}</td>
                    <td className="py-3 text-left font-mono tabular-nums">{fmtInt(r.index_value)}</td>
                    <td className="py-3 text-left font-mono tabular-nums">{fmtInt(r.index_change)}</td>
                    <td className="py-3 text-left">
                      <DeltaBadge value={r.index_change_pct} />
                    </td>
                    <td className="py-3 text-left text-ink-3">{r.time}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={5} className="py-8 text-center text-ink-3">داده‌ای موجود نیست</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
