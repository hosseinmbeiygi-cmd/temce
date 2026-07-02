"use client";

import type { ReactNode } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

function formatNum(n: number): string {
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return n.toFixed(n < 1 ? 4 : n < 10 ? 2 : 0);
}

const TOOLTIP_STYLE = {
  backgroundColor: "#1e293b",
  border: "1px solid #334155",
  borderRadius: "12px",
  fontSize: "12px",
  color: "#e2e8f0",
  direction: "rtl" as const,
};

/**
 * Shared chart wrapper. Pass `children` for the Line series and optional Legend.
 */
export default function IndicatorChart({
  data,
  children,
  height = 420,
  tooltipFormatter,
}: {
  data: Record<string, unknown>[];
  children: ReactNode;
  height?: number;
  tooltipFormatter?: (value: number, name: string) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#94a3b8", fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: "#334155" }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "#94a3b8", fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: "#334155" }}
          tickFormatter={formatNum}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={
            tooltipFormatter
              ? ((value: number, name: string) => tooltipFormatter(value, name)) as any
              : ((value: number) => `${formatNum(value)}`) as any
          }
        />
        {children}
      </LineChart>
    </ResponsiveContainer>
  );
}

export { formatNum };
