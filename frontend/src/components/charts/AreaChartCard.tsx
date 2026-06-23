"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardAction } from "@/components/ui/Card";
import { ChartDataPoint } from "@/lib/types";

interface AreaChartCardProps {
  title: string;
  data: ChartDataPoint[];
  dataKey?: string;
  gradientId?: string;
  strokeColor?: string;
  fillColor?: string;
  yAxisFormatter?: (value: number) => string;
  tooltipFormatter?: (value: number) => string;
  actions?: React.ReactNode;
  height?: number;
}

const defaultFormatter = (v: number) => v.toLocaleString("fa-IR");

export default function AreaChartCard({
  title,
  data,
  dataKey = "value",
  gradientId = "chartGradient",
  strokeColor = "var(--accent-primary)",
  fillColor = "var(--accent-primary)",
  yAxisFormatter = defaultFormatter,
  tooltipFormatter,
  actions,
  height = 250,
}: AreaChartCardProps) {
  const fmt = tooltipFormatter || yAxisFormatter;

  return (
    <Card title={title} actions={actions}>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor={strokeColor} stopOpacity={0.25} />
                <stop offset="100%" stopColor={strokeColor} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(128,128,128,0.08)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={50}
            />
            <YAxis
              tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={yAxisFormatter}
              width={60}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                color: "var(--text-primary)",
                fontSize: "12px",
                backdropFilter: "blur(10px)",
              }}
              formatter={(value: number) => [fmt(value), "مقدار"]}
              labelStyle={{ color: "var(--text-secondary)", fontWeight: 600 }}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={strokeColor}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              dot={false}
              activeDot={{ r: 4, fill: strokeColor, stroke: "var(--bg-card)", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
