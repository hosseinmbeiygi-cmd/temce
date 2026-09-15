"use client";
import React from "react";

interface Props {
  rsi: number | null;
  className?: string;
}

export function RSIIndicator({ rsi, className = "" }: Props) {
  if (rsi === null) {
    return <div className={`text-zinc-500 text-sm ${className}`}>RSI: —</div>;
  }
  let color = "text-zinc-300";
  let label = "خنثی";
  if (rsi < 30) {
    color = "text-emerald-400";
    label = "اشباع فروش (فرصت)";
  } else if (rsi < 45) {
    color = "text-emerald-300";
    label = "ناحیه خرید";
  } else if (rsi < 60) {
    color = "text-amber-400";
    label = "خنثی";
  } else if (rsi < 70) {
    color = "text-orange-400";
    label = "گرم";
  } else {
    color = "text-rose-400";
    label = "اشباع خرید";
  }

  return (
    <div className={`rounded-lg border border-zinc-700 bg-zinc-900 p-3 ${className}`}>
      <div className="text-xs text-zinc-400">RSI (۱۴ روزه)</div>
      <div className={`text-2xl font-bold ${color} font-mono`}>{rsi.toFixed(0)}</div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}
