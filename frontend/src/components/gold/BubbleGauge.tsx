"use client";
import React from "react";

interface Props {
  value: number | null;
  max?: number;
  className?: string;
}

export function BubbleGauge({ value, max = 30, className = "" }: Props) {
  if (value === null) {
    return <div className={`text-zinc-500 text-sm ${className}`}>—</div>;
  }
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  let color = "bg-rose-500";
  let label = "حباب شدید";
  if (value < 5) {
    color = "bg-emerald-500";
    label = "بدون حباب";
  } else if (value < 12) {
    color = "bg-amber-500";
    label = "حباب کم";
  } else if (value < 22) {
    color = "bg-orange-500";
    label = "حباب متوسط";
  }

  return (
    <div className={className}>
      <div className="flex justify-between text-xs text-zinc-400 mb-1">
        <span>{label}</span>
        <span className="font-mono">{value.toFixed(2)}٪</span>
      </div>
      <div className="h-3 bg-zinc-800 rounded overflow-hidden">
        <div className={`h-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
