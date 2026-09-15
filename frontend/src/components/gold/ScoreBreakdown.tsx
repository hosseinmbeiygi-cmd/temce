"use client";
import React from "react";
import type { ScoreComponents } from "@/types/gold";

interface Props {
  components: ScoreComponents;
  className?: string;
}

const ITEMS: Array<{ key: keyof ScoreComponents; label: string; max: number; reasonKey: keyof ScoreComponents }> = [
  { key: "bubble", label: "حباب سکه", max: 20, reasonKey: "bubble_reason" },
  { key: "nav", label: "P/NAV صندوق", max: 18, reasonKey: "nav_reason" },
  { key: "tsetmc", label: "قدرت خریدار", max: 18, reasonKey: "tsetmc_reason" },
  { key: "technical", label: "RSI اونس", max: 15, reasonKey: "technical_reason" },
  { key: "parity", label: "شکاف درهم", max: 15, reasonKey: "parity_reason" },
  { key: "fund_flow", label: "NAV 7d", max: 14, reasonKey: "fund_flow_reason" },
];

export function ScoreBreakdown({ components, className = "" }: Props) {
  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 p-4 ${className}`}>
      <div className="text-sm text-zinc-400 mb-3">جزئیات امتیاز</div>
      <div className="space-y-2">
        {ITEMS.map((item) => {
          const v = components[item.key] as number;
          const reason = components[item.reasonKey] as string;
          const pct = (v / item.max) * 100;
          return (
            <div key={item.key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-zinc-300">{item.label}</span>
                <span className="text-zinc-400 font-mono">
                  {v}/{item.max}
                </span>
              </div>
              <div className="h-2 bg-zinc-800 rounded overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">{reason}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
