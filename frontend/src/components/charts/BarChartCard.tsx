"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
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
}

const defaultFormat = (v: number) => {
  if (v >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(1)}T`;
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  return v.toLocaleString("fa-IR");
};

export default function BarChartCard({
  title,
  data,
  dataKey = "value",
  colorPositive = "var(--positive)",
  colorNegative = "var(--negative)",
  height = 200,
  yAxisFormatter = defaultFormat,
  tooltipFormatter: customTooltip,
}: BarChartCardProps) {
  const fmt = customTooltip || yAxisFormatter;

  // Determine if data has positive/negative volume markers
  const hasSign = data.length > 0 && "volume" in data[0] && typeof data[0].volume === "number";

  return (
    <Card title={title}>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(128,128,128,0.08)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: "var(--text-secondary)", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              tick={{ fill: "var(--text-secondary)", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={yAxisFormatter}
              width={50}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                color: "var(--text-primary)",
                fontSize: "11px",
                backdropFilter: "blur(10px)",
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any) => [fmt(Number(value) || 0), "حجم"]}
              labelStyle={{ color: "var(--text-secondary)", fontWeight: 600 }}
            />
            <Bar
              dataKey={dataKey}
              radius={[3, 3, 0, 0]}
              maxBarSize={20}
            >
              {hasSign
                ? data.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={
                        entry.volume !== undefined && entry.volume >= 0
                          ? colorPositive
                          : colorNegative
                      }
                    />
                  ))
                : null}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}
