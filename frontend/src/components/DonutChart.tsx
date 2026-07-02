"use client";

import React from "react";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------------

export interface DonutSliceDef {
  /** Label shown in the legend. */
  label: string;
  /** Numeric value for this slice. */
  value: number;
  /** CSS colour (any valid colour string). */
  color: string;
}

interface DonutChartProps {
  /** All slices that make up the chart. */
  slices: DonutSliceDef[];
  /** Total count displayed in the centre (defaults to sum of slice values). */
  total?: number;
  /** Chart size (default 80). */
  size?: number;
  /** Inner label (default "کل"). */
  centerLabel?: string;
}

// ------ DonutSlice (low-level) ---------------------------------------------------------------------------------------------------

/**
 * A single SVG arc segment for a donut / pie chart.
 *
 * Uses `strokeDasharray` and `strokeDashoffset` on an SVG `<circle>`
 * to render a proportional arc.  Stack multiple slices to build
 * a complete donut chart.
 *
 * ```tsx
 * <svg width={80} height={80} viewBox="0 0 80 80">
 *   <DonutSlice cx={40} cy={40} r={30} sw={12}
 *     total={100} value={50} offset={0} color="#22c55e" />
 *   <DonutSlice cx={40} cy={40} r={30} sw={12}
 *     total={100} value={30} offset={50} color="#f59e0b" />
 *   <text x="40" y="38" textAnchor="middle" …>{total}</text>
 * </svg>
 * ```
 */
export function DonutSlice({
  cx, cy, r, sw,
  total, value, offset, color,
}: {
  cx: number; cy: number; r: number; sw: number;
  total: number; value: number; offset: number; color: string;
}) {
  if (total === 0 || value === 0) return null;

  const circumference = 2 * Math.PI * r;
  const dashLength = (value / total) * circumference;
  const dashOffsetValue = -(offset / total) * circumference;

  return (
    <circle
      cx={cx} cy={cy} r={r}
      fill="none" stroke={color} strokeWidth={sw}
      strokeDasharray={`${dashLength} ${circumference - dashLength}`}
      strokeDashoffset={dashOffsetValue}
      transform={`rotate(-90 ${cx} ${cy})`}
      className="transition-all duration-500"
    />
  );
}

// ------ DonutChart (high-level with legend) ---------------------------------------------------------

/**
 * Ready-to-use donut chart with SVG + built-in legend.
 *
 * ```tsx
 * <DonutChart
 *   slices={[
 *     { label: "فعال", value: 60, color: "#22c55e" },
 *     { label: "غیرفعال", value: 40, color: "#ef4444" },
 *   ]}
 *   centerLabel="نماد"
 * />
 * ```
 */
export function DonutChart({
  slices,
  total: explicitTotal,
  size = 80,
  centerLabel = "کل",
}: DonutChartProps) {
  const total = explicitTotal ?? slices.reduce((s, sl) => s + sl.value, 0);
  if (total === 0) return null;

  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.375;      // radius = 37.5 % of size
  const sw = size * 0.15;       // stroke width = 15 % of size

  let offset = 0;

  return (
    <div className="flex items-center gap-5 flex-wrap">
      {/* SVG donut */}
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
        {slices.map((sl) => {
          const sliceEl = (
            <DonutSlice
              key={sl.label}
              cx={cx} cy={cy} r={r} sw={sw}
              total={total}
              value={sl.value}
              offset={offset}
              color={sl.color}
            />
          );
          offset += sl.value;
          return sliceEl;
        })}
        <text
          x={cx} y={cy - 5}
          textAnchor="middle"
          className="fill-surface-100 font-bold font-mono"
          style={{ fontSize: size * 0.2, dominantBaseline: "central" }}
        >
          {total}
        </text>
        <text
          x={cx} y={cy + size * 0.16}
          textAnchor="middle"
          className="fill-surface-500"
          style={{ fontSize: size * 0.09, dominantBaseline: "central" }}
        >
          {centerLabel}
        </text>
      </svg>

      {/* Legend */}
      <div className="flex flex-col gap-1.5">
        {slices.map((sl) => {
          const pct = Math.round((sl.value / total) * 100);
          return (
            <div key={sl.label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: sl.color }}
              />
              <span className="text-xs text-surface-300">{sl.label}</span>
              <span
                className="text-xs font-bold font-mono mr-auto"
                style={{ color: sl.color }}
              >
                {sl.value}
              </span>
              <span className="text-[10px] text-surface-500 w-10 text-left">
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
