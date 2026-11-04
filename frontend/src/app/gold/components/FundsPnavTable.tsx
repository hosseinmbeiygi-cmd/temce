"use client";

import type { FundBlock } from "@/types/gold";
import { cn } from "@/lib/cn";
import { DataTrustBadge } from "@/components/gold/DataTrustBadge";

interface FundTrust {
  quality?: string | null;
  source?: string | null;
  asOf?: string | null;
  ageSeconds?: number | null;
}

interface FundsPnavTableProps {
  data?: FundBlock[];
  // FundBlock در قرارداد فیلد منبع/زمان ندارد؛ برچسب از snapshot مرجع می‌آید
  // و به‌صراحت «مرجع» نامیده می‌شود تا با provenance تک‌تک ردیف‌ها اشتباه نشود.
  trust?: FundTrust;
}

const fmt = (value: number | null | undefined, digits = 0): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

// STEP 8: a missing bubble must look like no-data (neutral), never like a
// real 0٪ (which the positive/negative colors would imply).
const bubbleTone = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "text-zinc-500";
  }
  return value > 0 ? "text-rose-300" : "text-emerald-300";
};

export default function FundsPnavTable({ data, trust }: FundsPnavTableProps) {
  if (!data || data.length === 0) {
    return <div className="text-center text-sm text-zinc-500">داده‌ای برای صندوق‌ها ثبت نشده است</div>;
  }

  return (
    <div className="space-y-1">
      {trust && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="text-[10px] text-zinc-500">مرجع دادهٔ صندوق:</span>
          <DataTrustBadge
            quality={trust.quality}
            source={trust.source}
            asOf={trust.asOf}
            ageSeconds={trust.ageSeconds}
          />
        </div>
      )}
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-zinc-700/60 text-xs text-zinc-500">
            <th className="px-2 py-1 text-right">صندوق</th>
            <th className="px-2 py-1 text-right">NAV هر واحد</th>
            <th className="px-2 py-1 text-right">قیمت بازار</th>
            <th className="px-2 py-1 text-right">حباب</th>
          </tr>
        </thead>
        <tbody>
          {data.map((fund) => (
            <tr key={fund.symbol} className="border-b border-zinc-700/30 hover:bg-zinc-800/20">
              <td className="px-2 py-1 text-right text-zinc-100">{fund.fund_name}</td>
              <td className="px-2 py-1 text-right font-mono text-zinc-200">
                {fmt(fund.nav_per_unit)}
              </td>
              <td className="px-2 py-1 text-right font-mono text-zinc-400">
                {fmt(fund.market_price)}
              </td>
              <td
                className={cn(
                  "px-2 py-1 text-right font-mono",
                  bubbleTone(fund.bubble_pct),
                )}
              >
                {fund.bubble_pct === null || fund.bubble_pct === undefined
                  ? "—"
                  : `${fund.bubble_pct.toFixed(2)}٪`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
