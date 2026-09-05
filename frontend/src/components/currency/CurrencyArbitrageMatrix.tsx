"use client";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { ArbitrageRow } from "@/types/currency";

function fmt(n: number): string {
  return n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

const STATUS_STYLE: Record<ArbitrageRow["status"], string> = {
  OPPORTUNITY: "bg-emerald-600/15 text-emerald-700 ring-emerald-600/30 dark:text-emerald-400",
  EXPENSIVE: "bg-rose-600/15 text-rose-700 ring-rose-600/30 dark:text-rose-400",
  NORMAL: "bg-zinc-500/15 text-zinc-600 ring-zinc-500/30 dark:text-zinc-400",
};
const STATUS_LABEL: Record<ArbitrageRow["status"], string> = {
  OPPORTUNITY: "فرصت خرید/آربیتراژ",
  EXPENSIVE: "گران‌تر از بازار",
  NORMAL: "عادی",
};

/** ماتریس اختلاف نرخ‌ها با بازار آزاد (CBI / نیما / تتر). */
export function CurrencyArbitrageMatrix({ rates }: { rates: ArbitrageRow[] }) {
  return (
    <Card title="ماتریس اختلاف نرخ‌ها با بازار آزاد">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-right text-xs opacity-70">
              <th className="py-2 pr-1 font-medium">نوع نرخ / بازار</th>
              <th className="py-2 font-medium">نرخ (تومان)</th>
              <th className="py-2 font-medium">اختلاف ریالی</th>
              <th className="py-2 text-center font-medium">اختلاف درصدی</th>
              <th className="py-2 text-center font-medium">وضعیت تحلیل</th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.name} className="border-b last:border-0">
                <td className="py-2.5 pr-1 font-semibold">{r.name}</td>
                <td className="py-2.5 tabular-nums">{fmt(r.price)}</td>
                <td className="py-2.5 font-mono tabular-nums">
                  {r.difference_with_free_market > 0 ? "+" : ""}
                  {fmt(r.difference_with_free_market)}
                </td>
                <td
                  className={cn(
                    "py-2.5 text-center font-mono tabular-nums font-medium",
                    r.spread_pct > 0
                      ? "text-rose-500"
                      : r.spread_pct < 0
                        ? "text-emerald-500"
                        : "opacity-60"
                  )}
                >
                  {r.spread_pct > 0 ? "+" : ""}
                  {r.spread_pct.toFixed(2)}%
                </td>
                <td className="py-2.5 text-center">
                  <span
                    className={cn(
                      "inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ring-1",
                      STATUS_STYLE[r.status]
                    )}
                  >
                    {STATUS_LABEL[r.status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
