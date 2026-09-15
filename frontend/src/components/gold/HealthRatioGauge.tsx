"use client";
import React from "react";

interface Props {
  value: number | null;
  className?: string;
}

/** نیم‌دایره Gauge برای Health Ratio پورتفولیو آتی (10x IME).
 *  > 2.0 سبز، 1.2-2.0 زرد، < 1.2 قرمز (کال‌مارجین نزدیک). */
export function HealthRatioGauge({ value, className = "" }: Props) {
  if (value === null || !isFinite(value)) {
    return <div className={`text-zinc-500 text-sm ${className}`}>—</div>;
  }
  // scale: clamp to [0, 4] برای نمایش
  const clamped = Math.max(0, Math.min(4, value));
  const pct = (clamped / 4) * 100;

  // semicircle path math
  const R = 60;
  const cx = 75, cy = 70;
  const angle = (pct / 100) * Math.PI; // 0 to 180
  const x = cx - R * Math.cos(angle);
  const y = cy - R * Math.sin(angle);
  const arc = `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`;

  // رنگ بر اساس آستانه
  let color = "#10b981"; // emerald-500
  let label = "SAFE";
  let labelFa = "سالم";
  if (value < 1.2) {
    color = "#ef4444"; // red-500
    label = "CRITICAL";
    labelFa = "خطر — کال‌مارجین نزدیک";
  } else if (value < 2.0) {
    color = "#eab308"; // yellow-500
    label = "WARNING";
    labelFa = "هشدار";
  }

  return (
    <div className={`flex flex-col items-center ${className}`}>
      <svg viewBox="0 0 150 90" className="w-full max-w-[200px]">
        {/* background track */}
        <path
          d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`}
          fill="none"
          stroke="#27272a"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* value arc */}
        <path
          d={arc}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* threshold tick at health=2.0 (50%) */}
        <line
          x1={cx}
          y1={cy - R - 4}
          x2={cx}
          y2={cy - R + 4}
          stroke="#52525b"
          strokeWidth="2"
        />
        <text x={cx} y={cy - R - 8} textAnchor="middle" fontSize="8" fill="#71717a">
          2.0
        </text>
      </svg>
      <div className="text-center -mt-3">
        <div className="text-3xl font-black tabular-nums" style={{ color }}>
          {value.toFixed(2)}
        </div>
        <div className="text-[10px] uppercase tracking-wider" style={{ color }}>
          {label}
        </div>
        <div className="text-xs text-zinc-400 mt-0.5">{labelFa}</div>
      </div>
    </div>
  );
}
