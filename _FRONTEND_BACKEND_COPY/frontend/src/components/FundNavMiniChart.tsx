"use client";

import { useId, useMemo, useState } from "react";

export interface FundNavPoint {
  date: string;
  nav: number;
}

interface FundNavMiniChartProps {
  points: FundNavPoint[];
  width?: number;
  height?: number;
}

/**
 * Mini NAV area chart for the fund list cards.
 *
 * Renders an SVG area chart with a soft gradient under the line, colored by
 * trend (emerald up / rose down). Hovering a segment shows a tooltip with the
 * exact date and NAV value plus a marker dot. Flat series (all-equal values)
 * are padded so they render as a centered horizontal line instead of a broken
 * line glued to the bottom edge.
 */
export default function FundNavMiniChart({
  points,
  width = 88,
  height = 30,
}: FundNavMiniChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const rawId = useId();
  const gradId = `navg${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;

  // Dedupe by date (keep last) and collapse consecutive identical values so a
  // flat period renders as one segment, not a stack of repeated points.
  const series = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const p of points ?? []) {
      if (p && p.date && Number.isFinite(p.nav) && p.nav > 0) {
        byDate.set(p.date, p.nav);
      }
    }
    let entries = Array.from(byDate.entries());
    if (entries.length > 2) {
      const out: [string, number][] = [];
      for (const [d, v] of entries) {
        const last = out[out.length - 1];
        if (last && last[1] === v) continue;
        out.push([d, v]);
      }
      // Keep at least first+last so a fully-flat series still draws a line.
      entries = out.length >= 2 ? out : [entries[0], entries[entries.length - 1]];
    }
    return entries.map(([date, nav]) => ({ date, nav }));
  }, [points]);

  const geom = useMemo(() => {
    if (series.length < 2) return null;
    const values = series.map((p) => p.nav);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min;
    const lo = span < 1 ? min - 1 : min;
    const hi = span < 1 ? max + 1 : max;
    const rng = hi - lo;
    const X = (i: number) => (i / (series.length - 1)) * width;
    const Y = (v: number) => height - ((v - lo) / rng) * height;
    const linePts = series.map((p, i) => `${X(i).toFixed(1)},${Y(p.nav).toFixed(1)}`);
    const areaPts = `${X(0).toFixed(1)},${height} ${linePts.join(" ")} ${X(series.length - 1).toFixed(1)},${height}`;
    return {
      linePts: linePts.join(" "),
      areaPts,
      X,
      Y,
      isUp: series[series.length - 1].nav >= series[0].nav,
    };
  }, [series, width, height]);

  if (!geom) return null;

  const stroke = geom.isUp ? "#10b981" : "#f43f5e";
  const hover = hoverIdx != null ? series[hoverIdx] : null;

  return (
    <div className="relative shrink-0" style={{ width, height }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="block"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon points={geom.areaPts} fill={`url(#${gradId})`} />
        <polyline
          points={geom.linePts}
          fill="none"
          stroke={stroke}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Hover zones — one transparent rect per point, spanning the
            midpoint between neighbours so every point (incl. the first) is
            hoverable. */}
        {series.map((p, i) => {
          const start = i === 0 ? 0 : (geom.X(i - 1) + geom.X(i)) / 2;
          const end =
            i === series.length - 1
              ? width
              : (geom.X(i) + geom.X(i + 1)) / 2;
          return (
            <rect
              key={`${p.date}-${i}`}
              x={start}
              y={0}
              width={Math.max(end - start, 0)}
              height={height}
              fill="transparent"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
            />
          );
        })}
      </svg>
      {hover && hoverIdx != null && (
        <>
          <div
            className="pointer-events-none absolute z-20 bottom-full right-0 mb-1 px-1.5 py-0.5 rounded bg-surface-900 border border-surface-700 text-[9px] text-surface-200 whitespace-nowrap shadow-lg"
            dir="ltr"
          >
            {hover.date}:{" "}
            {hover.nav.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
          </div>
          <span
            className="pointer-events-none absolute z-10 rounded-full border-2 border-surface-900"
            style={{
              left: geom.X(hoverIdx) - 2.5,
              top: geom.Y(hover.nav) - 2.5,
              width: 5,
              height: 5,
              background: stroke,
            }}
          />
        </>
      )}
    </div>
  );
}
