"use client";


import { useMemo } from "react";
import {
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  ComposedChart,
  ReferenceArea,
} from "recharts";
import { Card } from "@/components/ui/Card";
import ChartContainer from "@/components/charts/ChartContainer";
import { ChartDataPoint } from "@/lib/types";

interface AreaSeries {
  dataKey: string;
  strokeColor: string;
  gradientId: string;
  label?: string;
  /** If true, render as bars instead of area */
  asBar?: boolean;
  /** Optional fill color for bars */
  barFill?: string;
}

interface AreaChartCardProps {
  title: string;
  data: ChartDataPoint[];
  dataKey?: string;
  gradientId?: string;
  strokeColor?: string;
  yAxisFormatter?: (value: number) => string;
  tooltipFormatter?: (value: number) => string;
  actions?: React.ReactNode;
  height?: number;
  /** Additional series to overlay */
  additionalSeries?: AreaSeries[];
  /** Show average reference line for the primary dataKey */
  showAverage?: boolean;
  /** Custom label for the X axis */
  xAxisLabel?: string;
  /** Custom label for the Y axis */
  yAxisLabel?: string;
  /** Label for the primary dataKey in tooltip/legend */
  primaryLabel?: string;
  /** Enable crosshair cursor (vertical line on hover) */
  crosshair?: boolean;
  /** Enable area animation on mount */
  animate?: boolean;
  /** Show min/max reference area */
  showMinMax?: boolean;
}

const defaultFormatter = (v: number) => v.toLocaleString("fa-IR");

interface TooltipEntry {
  value?: number | string;
  dataKey?: string;
  color?: string;
  stroke?: string;
  name?: string;
}

// ── Custom Tooltip (Advanced) ───────────────────────────────────────────────
function CustomTooltip({
  active,
  payload,
  label,
  labelMap,
  fmt,
  dataKey,
  allData,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  labelMap: Record<string, string>;
  fmt: (v: number) => string;
  dataKey: string;
  allData: ChartDataPoint[];
}) {
  if (!active || !payload?.length) return null;

  const currentIndex = allData.findIndex(d => 
    (d as { time?: string }).time === label || d.date === label
  );
  
  const prevItem = currentIndex > 0 ? allData[currentIndex - 1] : null;
  const currentValue = Number(payload[0]?.value) || 0;
  
  // Calculate change from previous
  let changePct: number | null = null;
  if (prevItem) {
    const prevVal = Number(prevItem[dataKey]) || 0;
    if (prevVal > 0) {
      changePct = ((currentValue - prevVal) / prevVal) * 100;
    }
  }

  return (
    <div
      className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
      style={{
        background: "rgba(15, 23, 42, 0.96)",
        border: "1px solid rgba(71, 85, 105, 0.5)",
        color: "#e2e8f0",
        minWidth: 180,
        maxWidth: 240,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header with time */}
      <div className="flex items-center justify-between mb-2 pb-2 border-b border-surface-700/60">
        <p className="text-[11px] font-bold text-surface-300">
          🕒 {label}
        </p>
        {changePct !== null && (
          <span
            className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
              changePct >= 0
                ? "text-accent-emerald bg-accent-emerald/10"
                : "text-accent-rose bg-accent-rose/10"
            }`}
          >
            {changePct >= 0 ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
          </span>
        )}
      </div>

      {/* Series values */}
      <div className="space-y-1.5">
        {payload.map((entry: TooltipEntry, idx: number) => {
          const color = entry.color || entry.stroke || "#888";
          const name = (entry.dataKey && labelMap[entry.dataKey]) || entry.dataKey || "";
          const val = fmt(Number(entry.value) || 0);
          return (
            <div key={idx} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5">
                <span
                  className="w-3 h-3 rounded-sm shrink-0"
                  style={{ backgroundColor: color, opacity: 0.8 }}
                />
                <span className="text-surface-400 text-[11px]">{name}</span>
              </span>
              <span className="font-mono font-bold text-surface-100 text-right tracking-wide" dir="ltr">
                {val}
              </span>
            </div>
          );
        })}
      </div>

      {/* Total */}
      {payload.length > 1 && (
        <div className="mt-2.5 pt-2 border-t border-surface-700/50 flex items-center justify-between">
          <span className="text-surface-500 text-[10px]">مجموع</span>
          <span className="font-mono font-bold text-surface-100 tracking-wide" dir="ltr">
            {fmt(
              payload.reduce((s: number, p: TooltipEntry) => s + (Number(p.value) || 0), 0),
            )}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Legend Content ──────────────────────────────────────────────────────────
function ChartLegend({ payload }: { payload?: TooltipEntry[] }) {
  if (!payload?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 mt-2 justify-center">
      {payload.map((entry: TooltipEntry, idx: number) => (
        <div key={idx} className="flex items-center gap-1.5 text-[10px]">
          <span
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: entry.color, opacity: 0.8 }}
          />
          <span className="text-surface-400 font-medium">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────
export default function AreaChartCard({
  title,
  data,
  dataKey = "value",
  gradientId = "chartGradient",
  strokeColor = "var(--accent-primary)",
  yAxisFormatter = defaultFormatter,
  tooltipFormatter,
  actions,
  height = 250,
  additionalSeries = [],
  showAverage = false,
  xAxisLabel,
  yAxisLabel,
  primaryLabel,
  crosshair = true,
  animate = true,
  showMinMax = false,
}: AreaChartCardProps) {

  const allGradients = [
    { id: gradientId, color: strokeColor },
    ...additionalSeries.filter(s => !s.asBar).map(s => ({ id: s.gradientId, color: s.strokeColor })),
  ];

  // Build label map
  const labelMap: Record<string, string> = { [dataKey]: primaryLabel || "مقدار" };
  additionalSeries.forEach(s => {
    if (s.label) labelMap[s.dataKey] = s.label;
  });

  const fmt = tooltipFormatter || yAxisFormatter;

  // Calculate average for reference line
  const avgVal = useMemo(() => 
    showAverage && data.length > 0
      ? data.reduce((s, d) => s + (Number(d[dataKey]) || 0), 0) / data.length
      : null
  , [data, dataKey, showAverage]);

  // Calculate min/max
  const { minVal, maxVal } = useMemo(() => {
    if (!showMinMax || data.length === 0) return { minVal: null, maxVal: null };
    let mn = Infinity, mx = -Infinity;
    data.forEach((d) => {
      const v = Number(d[dataKey]) || 0;
      if (v < mn) { mn = v; }
      if (v > mx) { mx = v; }
    });
    return { minVal: mn, maxVal: mx };
  }, [data, dataKey, showMinMax]);

  // Separate bar series from area series for ComposedChart
  const barSeries = additionalSeries.filter(s => s.asBar);
  const areaSeries = additionalSeries.filter(s => !s.asBar);

  // Chart margin: extra right padding for large numbers
  const chartMargin = { top: 12, right: 12, left: 0, bottom: 5 };

  // Animation duration
  const animDuration = animate ? 800 : 0;

  return (
    <Card title={title} actions={actions}>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <ComposedChart
            data={data}
            margin={chartMargin}

          >
            <defs>
              {allGradients.map(g => (
                <linearGradient key={g.id} id={g.id} x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor={g.color} stopOpacity={0.45} />
                  <stop offset="50%" stopColor={g.color} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={g.color} stopOpacity={0.03} />
                </linearGradient>
              ))}
              {/* Gradient for bars */}
              {barSeries.map(s => (
                <linearGradient key={`bar-grad-${s.dataKey}`} id={`bar-grad-${s.dataKey}`} x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor={s.barFill || s.strokeColor} stopOpacity={0.9} />
                  <stop offset="100%" stopColor={s.barFill || s.strokeColor} stopOpacity={0.3} />
                </linearGradient>
              ))}

            </defs>

            {/* Grid - more visible, horizontal only */}
            <CartesianGrid
              strokeDasharray="4 4"
              stroke="rgba(100, 116, 139, 0.12)"
              vertical={false}
              horizontal={true}
            />

            {/* X Axis */}
            <XAxis
              dataKey="time"
              tick={{ fill: "#64748b", fontSize: 10, fontWeight: 500, fontFamily: "inherit" }}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.2)", strokeWidth: 1 }}
              interval="preserveStartEnd"
              minTickGap={50}
              padding={{ left: 10, right: 10 }}
              label={
                xAxisLabel
                  ? { value: xAxisLabel, position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 9 }
                  : undefined
              }
            />

            {/* Y Axis */}
            <YAxis
              tick={{ fill: "#64748b", fontSize: 9, fontWeight: 500, fontFamily: "inherit" }}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)", strokeWidth: 1 }}
              tickFormatter={yAxisFormatter}
              width={55}
              label={
                yAxisLabel
                  ? { value: yAxisLabel, angle: -90, position: "insideLeft", offset: 0, fill: "#64748b", fontSize: 9 }
                  : undefined
              }
            />

            {/* Reference area for min/max range */}
            {showMinMax && minVal != null && maxVal != null && minVal < maxVal && (
              <ReferenceArea
                y1={minVal}
                y2={maxVal}
                fill="rgba(59, 130, 246, 0.04)"
                strokeOpacity={0}
              />
            )}

            {/* Reference line for average */}
            {showAverage && avgVal != null && (
              <ReferenceLine
                y={avgVal}
                stroke="rgba(251, 191, 36, 0.6)"
                strokeDasharray="6 3"
                strokeWidth={1.5}
                label={{
                  value: `میانگین: ${fmt(avgVal)}`,
                  fill: "#f59e0b",
                  fontSize: 9,
                  fontWeight: 600,
                  position: "insideTopRight",
                }}
              />
            )}

            {/* Tooltip */}
            <Tooltip
              content={<CustomTooltip labelMap={labelMap} fmt={fmt} dataKey={dataKey} allData={data} />}
              cursor={crosshair ? {
                stroke: "rgba(148, 163, 184, 0.3)",
                strokeDasharray: "3 3",
                strokeWidth: 1.5,
              } : false}
              wrapperStyle={{ outline: "none", zIndex: 100 }}
            />

            {/* Legend */}
            <Legend
              content={<ChartLegend />}
              verticalAlign="bottom"
              height={24}
            />

            {/* Primary area series */}
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={strokeColor}
              strokeWidth={2.5}
              fill={`url(#${gradientId})`}
              dot={false}
              activeDot={{
                r: 6,
                fill: strokeColor,
                stroke: "rgba(15, 23, 42, 0.9)",
                strokeWidth: 3,
              }}
              isAnimationActive={animate}
              animationDuration={animDuration}
              animationEasing="ease-out"
            />

            {/* Additional area series */}
            {areaSeries.map(s => (
              <Area
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                stroke={s.strokeColor}
                strokeWidth={2}
                fill={`url(#${s.gradientId})`}
                strokeDasharray="5 3"
                dot={false}
                activeDot={{
                  r: 5,
                  fill: s.strokeColor,
                  stroke: "rgba(15, 23, 42, 0.9)",
                  strokeWidth: 3,
                }}
                isAnimationActive={animate}
                animationDuration={animDuration}
                animationEasing="ease-out"
              />
            ))}

            {/* Bar series (e.g., errors) */}
            {barSeries.map(s => (
              <Bar
                key={s.dataKey}
                dataKey={s.dataKey}
                fill={`url(#bar-grad-${s.dataKey})`}
                stroke={s.strokeColor}
                strokeWidth={1}
                radius={[4, 4, 0, 0]}
                maxBarSize={24}
                isAnimationActive={animate}
                animationDuration={animDuration}
                animationEasing="ease-out"
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}
