"use client";
import React from "react";
import type { FundBlock } from "@/types/gold";

interface Props {
  funds: FundBlock[];
  className?: string;
}

export function FundNAVTable({ funds, className = "" }: Props) {
  if (funds.length === 0) {
    return <div className="text-zinc-500 text-sm">صندوقی یافت نشد</div>;
  }

  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-zinc-700 text-sm font-semibold text-zinc-300">
        صندوق‌های طلا (NAV)
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-zinc-500 border-b border-zinc-800">
            <th className="text-right p-3">صندوق</th>
            <th className="text-left p-3">NAV</th>
            <th className="text-left p-3">بازار</th>
            <th className="text-left p-3">حباب NAV</th>
            <th className="text-left p-3">BPR</th>
            <th className="text-left p-3">ورود خالص</th>
          </tr>
        </thead>
        <tbody>
          {funds.map((f) => {
            const navPctColor =
              f.bubble_pct <= 1.5 ? "text-emerald-400" : f.bubble_pct <= 3 ? "text-amber-400" : "text-rose-400";
            return (
              <tr key={f.symbol} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                <td className="p-3 text-zinc-200">{f.fund_name}</td>
                <td className="p-3 text-left text-zinc-100 font-mono">{f.nav_per_unit.toLocaleString("fa-IR")}</td>
                <td className="p-3 text-left text-zinc-100 font-mono">{f.market_price.toLocaleString("fa-IR")}</td>
                <td className={`p-3 text-left font-mono font-bold ${navPctColor}`}>
                  {f.bubble_pct > 0 ? "+" : ""}
                  {f.bubble_pct.toFixed(2)}٪
                </td>
                <td className="p-3 text-left text-zinc-300 font-mono">{f.bpr.toFixed(2)}</td>
                <td className="p-3 text-left text-zinc-300 font-mono">
                  {(f.net_inflow / 1e9).toFixed(2)}B
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
