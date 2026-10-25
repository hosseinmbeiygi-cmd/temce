"use client";
import React from "react";
import { decisionView } from "@/lib/gold-decision";
import type { ScoreBlock } from "@/types/gold";

interface Props {
  score: ScoreBlock;
  className?: string;
}

export function ScoreGauge({ score, className = "" }: Props) {
  // جدول محلی با `map[decision]` بدون fallback، با هر مقدار تازه‌ای (مثل NO_DATA
  // در C1) TypeError می‌ساخت. حالا از نگاشت مشترک استفاده می‌شود.
  const view = decisionView(score.decision);
  const coverage = score.data_coverage_pct;

  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 p-6 ${className}`}>
      <div className="text-sm text-zinc-400 mb-2">امتیاز تصمیم‌گیری</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-6xl font-bold ${view.text}`}>{score.total}</span>
        <span className="text-zinc-500 text-sm">/ ۱۰۰</span>
      </div>
      {coverage !== null && coverage !== undefined && (
        <div className="mt-2 text-[11px] text-zinc-500">پوشش داده: {Math.round(coverage)}٪</div>
      )}
      <div className={`mt-3 inline-block px-3 py-1 rounded text-sm font-semibold ring-1 ${view.cls}`}>
        {view.label}
      </div>
      {score.hard_stop_active && score.hard_stop_reason && (
        <div className="mt-3 text-xs text-rose-300 bg-rose-950/40 rounded p-2">
          ⚠️ {score.hard_stop_reason}
        </div>
      )}
    </div>
  );
}
