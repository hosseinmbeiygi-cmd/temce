"use client";
import React from "react";

interface Props {
  data: Array<{ date: string; value: number }>;
  height?: number;
  color?: "emerald" | "amber" | "rose" | "blue";
  className?: string;
  yLabel?: string;
}

// SVG inline — بدون recharts
export function TimeSeriesChart({ data, height = 200, color = "blue", className = "", yLabel = "" }: Props) {
  if (data.length === 0) {
    return <div className={`text-zinc-500 text-sm ${className}`}>داده‌ای موجود نیست</div>;
  }
  if (data.length === 1) {
    return <div className={`text-zinc-500 text-sm ${className}`}>فقط یک نقطه</div>;
  }

  const w = 800;
  const h = height;
  const padX = 40;
  const padY = 20;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const x = (i: number) => padX + (i / (data.length - 1)) * (w - 2 * padX);
  const y = (v: number) => h - padY - ((v - min) / range) * (h - 2 * padY);

  const colorClass = {
    emerald: "#10b981",
    amber: "#f59e0b",
    rose: "#f43f5e",
    blue: "#3b82f6",
  }[color];

  const pathD = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(d.value).toFixed(1)}`).join(" ");
  const areaD = `${pathD} L ${x(data.length - 1).toFixed(1)} ${(h - padY).toFixed(1)} L ${x(0).toFixed(1)} ${(h - padY).toFixed(1)} Z`;

  return (
    <div className={className}>
      {yLabel && <div className="text-xs text-zinc-400 mb-1">{yLabel}</div>}
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <line
            key={p}
            x1={padX}
            x2={w - padX}
            y1={padY + p * (h - 2 * padY)}
            y2={padY + p * (h - 2 * padY)}
            stroke="#3f3f46"
            strokeWidth="0.5"
          />
        ))}
        {/* Area */}
        <path d={areaD} fill={colorClass} fillOpacity="0.15" />
        {/* Line */}
        <path d={pathD} fill="none" stroke={colorClass} strokeWidth="2" />
        {/* Dots on hover (last) */}
        <circle cx={x(data.length - 1)} cy={y(data[data.length - 1].value)} r="3" fill={colorClass} />
        {/* Min/Max labels */}
        <text x={padX - 5} y={padY + 4} fill="#71717a" fontSize="10" textAnchor="end">
          {max.toFixed(1)}
        </text>
        <text x={padX - 5} y={h - padY + 4} fill="#71717a" fontSize="10" textAnchor="end">
          {min.toFixed(1)}
        </text>
        {/* First / Last date */}
        <text x={padX} y={h - 4} fill="#71717a" fontSize="9">
          {data[0].date}
        </text>
        <text x={w - padX} y={h - 4} fill="#71717a" fontSize="9" textAnchor="end">
          {data[data.length - 1].date}
        </text>
      </svg>
    </div>
  );
}
