"use client";

import type { AssetBlock } from "@/types/gold";
import { cn } from "@/lib/cn";
import { DataTrustBadge } from "@/components/gold/DataTrustBadge";

interface CoinBubbleTableProps {
  data?: AssetBlock[];
}

const fmt = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}٪`;
};

const fmtPrice = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
};

// STEP 8: a missing bubble must look like no-data (neutral), never like a
// real 0٪ (which the positive/negative colors would imply).
const bubbleTone = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "text-zinc-500";
  }
  return value > 0 ? "text-rose-300" : "text-emerald-300";
};

export default function CoinBubbleTable({ data }: CoinBubbleTableProps) {
  if (!data || data.length === 0) {
    return <div className="text-center text-sm text-zinc-500">داده‌ای برای سکه‌ها ثبت نشده است</div>;
  }

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-zinc-700/60 text-xs text-zinc-500">
          <th className="px-2 py-1 text-right">سکه / منبع داده</th>
          <th className="px-2 py-1 text-right">قیمت بازار</th>
          <th className="px-2 py-1 text-right">ارزش منصفانه</th>
          <th className="px-2 py-1 text-right">حباب</th>
        </tr>
      </thead>
      <tbody>
        {data.map((asset) => (
          <tr key={asset.symbol} className="border-b border-zinc-700/30 hover:bg-zinc-800/20">
            <td className="px-2 py-1 text-right">
              <div className="text-zinc-100">{asset.display_name}</div>
              <DataTrustBadge
                quality={asset.quality}
                source={asset.source}
                asOf={asset.asOf}
                className="mt-1"
              />
            </td>
            <td className="px-2 py-1 text-right font-mono text-zinc-200">{fmtPrice(asset.market_price)}</td>
            <td className="px-2 py-1 text-right font-mono text-zinc-400">{fmtPrice(asset.fair_value)}</td>
            <td
              className={cn(
                "px-2 py-1 text-right font-mono",
                bubbleTone(asset.bubble_pct),
              )}
            >
              {fmt(asset.bubble_pct)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
