"use client";

import React from "react";

const ALL_RADAR_COLS = [
  { key: "total_return_pct" as const, label: "بازده", invert: false },
  { key: "annualized_return_pct" as const, label: "بازده سالانه", invert: false },
  { key: "sharpe_ratio" as const, label: "شارپ", invert: false },
  { key: "win_rate" as const, label: "Win Rate", invert: false },
  { key: "max_drawdown_pct" as const, label: "Max DD", invert: true },
];

const BACKTEST_RADAR_COLORS = [
  { fill: "rgba(0, 200, 255, 0.15)", stroke: "#00C8FF" },
  { fill: "rgba(0, 230, 118, 0.15)", stroke: "#00E676" },
  { fill: "rgba(255, 214, 0, 0.15)", stroke: "#FFD600" },
  { fill: "rgba(255, 82, 82, 0.15)", stroke: "#FF5252" },
  { fill: "rgba(224, 64, 251, 0.15)", stroke: "#E040FB" },
  { fill: "rgba(0, 230, 200, 0.15)", stroke: "#00E6C8" },
  { fill: "rgba(255, 168, 0, 0.15)", stroke: "#FFA800" },
  { fill: "rgba(100, 255, 218, 0.15)", stroke: "#64FFDA" },
];

export interface CompareResult {
  strategy: string;
  status?: string;
  metrics?: Record<string, number | undefined>;
}

interface BacktestRadarChartProps {
  results: CompareResult[];
  selectedStrategies: string[];
  onStrategyClick: (strategy: string, e?: React.MouseEvent) => void;
  enabledCols: string[];
  hoveredStrategy: string | null;
  onHover: (strategy: string | null) => void;
  onClearSelection?: () => void;
}

export default function BacktestRadarChart({
  results,
  selectedStrategies,
  onStrategyClick,
  enabledCols,
  hoveredStrategy,
  onHover,
  onClearSelection,
}: BacktestRadarChartProps) {
  const radarCols = ALL_RADAR_COLS.filter((c) => enabledCols.includes(c.key));

  const validResults = results.filter((r) => r.status !== "failed").slice(0, 8);
  if (validResults.length < 1) return null;
  if (radarCols.length < 3) {
    return (
      <p className="text-xs text-surface-500 text-center py-4">
        حداقل ۳ متریک برای نمایش رادار انتخاب کنید
      </p>
    );
  }

  const ranges: Record<string, { min: number; max: number }> = {};
  for (const col of radarCols) {
    const vals = validResults
      .map((r) => r.metrics?.[col.key])
      .filter((v): v is number => v != null) as number[];
    if (vals.length === 0) continue;
    ranges[col.key] = { min: Math.min(...vals), max: Math.max(...vals) };
  }

  const normalize = (key: string, v: number | undefined): number => {
    if (v == null) return 0;
    const r = ranges[key];
    if (!r || r.max === r.min) return 0.5;
    const raw = (v - r.min) / (r.max - r.min);
    const col = radarCols.find((c) => c.key === key);
    return col?.invert ? 1 - raw : raw;
  };

  const cx = 160;
  const cy = 160;
  const radius = 120;
  const angleStep = (2 * Math.PI) / radarCols.length;

  const polygons = validResults.map((r, mi) => {
    const pts = radarCols.map((col, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const val = normalize(col.key, r.metrics?.[col.key]);
      const rad = val * radius;
      return `${cx + rad * Math.cos(angle)},${cy + rad * Math.sin(angle)}`;
    });
    return { points: pts.join(" "), color: BACKTEST_RADAR_COLORS[mi % BACKTEST_RADAR_COLORS.length], label: r.strategy };
  });

  return (
    <div className="mb-6">
      <p className="text-xs text-surface-400 font-bold mb-3 text-center">
        📡 نمودار راداری — مقایسه بصری استراتژی‌ها
      </p>
      <div className="flex flex-col items-center">
        <svg width={320} height={320} viewBox="0 0 320 320" className="max-w-full">
          {Array.from({ length: 5 }, (_, li) => {
            const r = ((li + 1) / 5) * radius;
            const pts = radarCols.map((_, i) => {
              const angle = -Math.PI / 2 + i * angleStep;
              return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
            });
            return <polygon key={li} points={pts.join(" ")} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />;
          })}
          {radarCols.map((col, i) => {
            const angle = -Math.PI / 2 + i * angleStep;
            const x2 = cx + radius * Math.cos(angle);
            const y2 = cy + radius * Math.sin(angle);
            const labelX = cx + (radius + 22) * Math.cos(angle);
            const labelY = cy + (radius + 22) * Math.sin(angle);
            const anchor =
              angle > -0.1 && angle < Math.PI - 0.1 ? "start" : angle > Math.PI - 0.1 ? "end" : "middle";
            return (
              <g key={col.key}>
                <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
                <text
                  x={labelX}
                  y={labelY}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  fill="rgba(255,255,255,0.5)"
                  fontSize={9}
                  fontFamily="monospace"
                >
                  {col.label}
                </text>
              </g>
            );
          })}
          {polygons.map((p, i) => {
            const isSelected = selectedStrategies.includes(p.label);
            const isHovered = hoveredStrategy === p.label;
            const hasSelection = selectedStrategies.length > 0;
            const isDimmed = hasSelection && !isSelected;
            const dimOpacity = isDimmed ? 0.15 : isHovered ? 1 : 0.85;
            const strokeColor = isSelected ? "#fff" : isHovered ? p.color.stroke : p.color.stroke;
            const strokeW = isSelected ? 3 : isHovered ? 2.5 : 2;
            return (
              <g
                key={i}
                onClick={(e) => onStrategyClick(p.label, e)}
                onMouseEnter={() => onHover(p.label)}
                onMouseLeave={() => onHover(null)}
                style={{ cursor: "pointer" }}
              >
                <polygon
                  points={p.points}
                  fill={isSelected ? p.color.fill.replace("0.15", "0.35") : p.color.fill}
                  stroke={strokeColor}
                  strokeWidth={strokeW}
                  opacity={dimOpacity}
                  className="transition-all duration-200"
                />
                {p.points.split(" ").map((pt, pi) => {
                  const [x, y] = pt.split(",").map(Number);
                  return (
                    <circle
                      key={pi}
                      cx={x}
                      cy={y}
                      r={isSelected ? 5 : isHovered ? 4 : 3}
                      fill={isSelected ? "#fff" : p.color.stroke}
                      opacity={isDimmed ? 0.2 : 0.95}
                      className="transition-all duration-200"
                    />
                  );
                })}
              </g>
            );
          })}
          <circle cx={cx} cy={cy} r={2} fill="rgba(255,255,255,0.2)" />
        </svg>
        <div className="flex flex-wrap gap-3 justify-center mt-2">
          {polygons.map((p, i) => {
            const isSelected = selectedStrategies.includes(p.label);
            return (
              <div
                key={i}
                onClick={(e) => onStrategyClick(p.label, e)}
                onMouseEnter={() => onHover(p.label)}
                onMouseLeave={() => onHover(null)}
                className={`flex items-center gap-1.5 cursor-pointer transition-all duration-200 px-1.5 py-0.5 rounded ${
                  isSelected ? "bg-primary-600/20 ring-1 ring-primary-500/50" : "hover:bg-surface-800/50"
                }`}
              >
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: p.color.stroke }} />
                <span className={`text-[10px] ${isSelected ? "text-surface-100 font-bold" : "text-surface-400"}`}>
                  {p.label}
                </span>
              </div>
            );
          })}
          {selectedStrategies.length > 0 && onClearSelection && (
            <button
              onClick={onClearSelection}
              className="text-[9px] px-2 py-0.5 rounded bg-surface-700 hover:bg-surface-600 text-surface-400 hover:text-surface-200 transition-all"
            >
              ✕ پاک کردن انتخاب
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
