"use client";
import React from "react";
import type { ScoreBlock } from "@/types/gold";

interface Props {
  score: ScoreBlock;
  className?: string;
}

export function ScoreGauge({ score, className = "" }: Props) {
  const colorMap = {
    GREEN: { bg: "bg-emerald-600", text: "text-emerald-400", label: "سبز — ورود" },
    YELLOW: { bg: "bg-amber-600", text: "text-amber-400", label: "زرد — احتیاط" },
    RED: { bg: "bg-rose-600", text: "text-rose-400", label: "قرمز — صبر" },
  };
  const c = colorMap[score.decision];

  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 p-6 ${className}`}>
      <div className="text-sm text-zinc-400 mb-2">امتیاز تصمیم‌گیری</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-6xl font-bold ${c.text}`}>{score.total}</span>
        <span className="text-zinc-500 text-sm">/ ۱۰۰</span>
      </div>
      <div className={`mt-3 inline-block px-3 py-1 rounded text-sm font-semibold ${c.bg} text-white`}>
        {c.label}
      </div>
      {score.hard_stop_active && score.hard_stop_reason && (
        <div className="mt-3 text-xs text-rose-300 bg-rose-950/40 rounded p-2">
          ⚠️ {score.hard_stop_reason}
        </div>
      )}
    </div>
  );
}
