"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui/Card";
import ChartContainer from "@/components/charts/ChartContainer";
import { ChartDataPoint } from "@/lib/types";

interface BarChartCardProps {
  title: string;
  data: ChartDataPoint[];
  dataKey?: string;
  colorPositive?: string;
  colorNegative?: string;
  height?: number;
  yAxisFormatter?: (value: number) => string;
  tooltipFormatter?: (value: number) => string;
  /** Label for the value axis */
  valueLabel?: string;
  /** Enable bar animation */
  animate?: boolean;
  /** Show average reference line */
  showAverage?: boolean;
}

interface TooltipEntry {
  value?: number | string;
  dataKey?: string;
  color?: string;
  stroke?: string;
  name?: string;
}

const defaultFormat = (v: number) => {
  if (v >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(1)}T`;
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  return v.toLocaleString("fa-IR");
};

function CustomTooltip({
  active,
  payload,
  label,
  fmt,
  labelName,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  fmt: (v: number) => string;
  labelName: string;
}) {
  if (!active || !payload?.length) return null;

  const val = Number(payload[0]?.value) || 0;

  return (
    <div
      className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
      style={{
        background: "rgba(15, 23, 42, 0.96)",
        border: "1px solid rgba(71, 85, 105, 0.5)",
        color: "#e2e8f0",
        minWidth: 140,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      <p className="text-[11px] font-bold text-surface-300 mb-2 pb-1.5 border-b border-surface-700/50">
        🕒 {label}
      </p>
      <div className="flex items-center justify-between gap-4">
        <span className="text-surface-400 text-[11px]">{labelName}</span>
        <span className="font-mono font-bold text-surface-100 tracking-wide" dir="ltr">
          {fmt(val)}
        </span>
      </div>
    </div>
  );
}

export default function BarChartCard({
  title,
  data,
  dataKey = "value",
  colorPositive = "var(--accent-emerald)",
  colorNegative = "var(--accent-rose)",
  height = 200,
  yAxisFormatter = defaultFormat,
  tooltipFormatter: customTooltip,
  valueLabel = "مقدار",
  animate = true,
  showAverage = false,
}: BarChartCardProps) {
  const fmt = customTooltip || yAxisFormatter;

  // Determine if data has positive/negative markers
  const hasSign = data.length > 0 && "volume" in data[0] && typeof data[0].volume === "number";

  // Calculate average
  const avgVal = useMemo(() => 
    showAverage && data.length > 0
      ? data.reduce((s, d) => s + (Number(d[dataKey]) || 0), 0) / data.length
      : null
  , [data, dataKey, showAverage]);

  // Color gradient based on value direction
  const getBarColor = (entry: ChartDataPoint, i: number) => {
    if (hasSign) {
      return entry.volume !== undefined && entry.volume >= 0 ? colorPositive : colorNegative;
    }
    // Use alternating subtle colors based on position
    return i % 2 === 0 ? "var(--accent-primary)" : "var(--accent-secondary)";
  };

  return (
    <Card title={title}>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="barPrimaryGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity={0.85} />
                <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity={0.4} />
              </linearGradient>
              <linearGradient id="barSecondaryGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="var(--accent-secondary)" stopOpacity={0.85} />
                <stop offset="100%" stopColor="var(--accent-secondary)" stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(100, 116, 139, 0.1)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: "#64748b", fontSize: 9, fontWeight: 500 }}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)", strokeWidth: 1 }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 9, fontWeight: 500 }}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)", strokeWidth: 1 }}
              tickFormatter={yAxisFormatter}
              width={50}
            />
            <Tooltip
              content={<CustomTooltip fmt={fmt} labelName={valueLabel} />}
              cursor={{
                fill: "rgba(148, 163, 184, 0.06)",
              }}
            />
            {/* Average reference line */}
            {showAverage && avgVal != null && (
              <ReferenceLine
                y={avgVal}
                stroke="rgba(251, 191, 36, 0.5)"
                strokeDasharray="6 3"
                strokeWidth={1.5}
                label={{
                  value: `میانگین: ${fmt(avgVal)}`,
                  fill: "#f59e0b",
                  fontSize: 9,
                  position: "insideTopRight",
                }}
              />
            )}
            <Bar
              dataKey={dataKey}
              radius={[4, 4, 0, 0]}
              maxBarSize={28}
              isAnimationActive={animate}
              animationDuration={600}
              animationEasing="ease-out"
            >
              {data.map((entry, i) => (
                <Cell
                  key={i}
                  fill={getBarColor(entry, i)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}

