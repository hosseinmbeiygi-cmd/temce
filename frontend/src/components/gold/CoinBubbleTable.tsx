"use client";
import React from "react";
import type { AssetBlock } from "@/types/gold";

interface Props {
  coins: Record<string, AssetBlock>;
  className?: string;
}

function bubbleColor(pct: number | null): string {
  if (pct === null) return "text-zinc-500";
  if (pct < 5) return "text-emerald-400";
  if (pct < 12) return "text-amber-400";
  if (pct < 22) return "text-orange-400";
  return "text-rose-400";
}

export function CoinBubbleTable({ coins, className = "" }: Props) {
  const items = Object.values(coins);
  if (items.length === 0) {
    return <div className="text-zinc-500 text-sm">داده‌ای موجود نیست</div>;
  }

  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-zinc-700 text-sm font-semibold text-zinc-300">
        حباب سکه و طلا
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-zinc-500 border-b border-zinc-800">
            <th className="text-right p-3">نام</th>
            <th className="text-left p-3">قیمت بازار</th>
            <th className="text-left p-3">ارزش ذاتی</th>
            <th className="text-left p-3">حباب ٪</th>
            <th className="text-left p-3">دلار ضمنی</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.symbol} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
              <td className="p-3 text-zinc-200">{c.display_name}</td>
              <td className="p-3 text-left text-zinc-100 font-mono">
                {c.market_price.toLocaleString("fa-IR")}
              </td>
              <td className="p-3 text-left text-zinc-400 font-mono">
                {c.fair_value ? c.fair_value.toLocaleString("fa-IR") : "—"}
              </td>
              <td className={`p-3 text-left font-bold font-mono ${bubbleColor(c.bubble_pct)}`}>
                {c.bubble_pct !== null ? `${c.bubble_pct.toFixed(2)}٪` : "—"}
              </td>
              <td className="p-3 text-left text-zinc-400 font-mono">
                {c.implied_usd ? c.implied_usd.toLocaleString("fa-IR") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
