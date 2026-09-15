"use client";
import React from "react";

interface Props {
  gap: number;
  className?: string;
}

export function ParityBadge({ gap, className = "" }: Props) {
  const abs = Math.abs(gap);
  let color = "bg-zinc-700 text-zinc-300";
  let label = "متعادل";
  if (abs < 0.5) {
    color = "bg-emerald-700 text-emerald-100";
    label = "متعادل";
  } else if (abs < 1.5) {
    color = "bg-amber-700 text-amber-100";
    label = "کمی偏离";
  } else if (abs < 3) {
    color = "bg-orange-700 text-orange-100";
    label = "انحراف";
  } else {
    color = "bg-rose-700 text-rose-100";
    label = "آربیتراژ شدید";
  }

  const direction = gap > 0 ? "دلار گران‌تر" : gap < 0 ? "دلار ارزان‌تر" : "";

  return (
    <div className={`rounded-lg border border-zinc-700 p-4 ${className}`}>
      <div className="text-xs text-zinc-400 mb-2">شکاف درهم</div>
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold text-zinc-100 font-mono">{gap.toFixed(2)}٪</span>
        <span className={`px-2 py-1 rounded text-xs font-semibold ${color}`}>{label}</span>
      </div>
      {direction && <div className="text-xs text-zinc-500 mt-1">{direction}</div>}
    </div>
  );
}
