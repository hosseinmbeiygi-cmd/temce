"use client";
import React from "react";

interface Props {
  title: string;
  value: number | string;
  unit?: string;
  delta?: number;
  className?: string;
  color?: "default" | "green" | "yellow" | "red";
}

export function GoldKPICard({ title, value, unit, delta, className = "", color = "default" }: Props) {
  const colorClass = {
    default: "border-zinc-700 bg-zinc-900",
    green: "border-emerald-700 bg-emerald-950/30",
    yellow: "border-amber-700 bg-amber-950/30",
    red: "border-rose-700 bg-rose-950/30",
  }[color];

  return (
    <div className={`rounded-lg border p-4 ${colorClass} ${className}`}>
      <div className="text-xs text-zinc-400 mb-1">{title}</div>
      <div className="text-2xl font-bold text-zinc-100">
        {typeof value === "number" ? value.toLocaleString("fa-IR") : value}
        {unit && <span className="text-sm text-zinc-400 mr-1">{unit}</span>}
      </div>
      {delta !== undefined && (
        <div className={`text-xs mt-1 ${delta > 0 ? "text-emerald-400" : delta < 0 ? "text-rose-400" : "text-zinc-500"}`}>
          {delta > 0 ? "▲" : delta < 0 ? "▼" : "▬"} {Math.abs(delta).toFixed(2)}٪
        </div>
      )}
    </div>
  );
}
