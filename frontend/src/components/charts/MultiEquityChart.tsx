"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import ChartContainer from "@/components/charts/ChartContainer";

interface Series {
  name: string;
  data: { index: number; nav: number }[];
  color: string;
}

interface MultiEquityChartProps {
  series: Series[];
  height?: number;
}

const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

export default function MultiEquityChart({ series, height = 300 }: MultiEquityChartProps) {
  // Align all series by index
  const maxLen = Math.max(...series.map((s) => s.data.length), 0);
  const alignedData = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number> = { index: i };
    for (const s of series) {
      point[s.name] = s.data[i]?.nav ?? 0;
    }
    return point;
  });

  return (
    <ChartContainer height={height}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
        <LineChart data={alignedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <XAxis dataKey="index" hide />
          <YAxis
            stroke="#4b5563"
            fontSize={12}
            tickFormatter={(val) => `${(val / 1e9).toFixed(1)}B`}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", borderColor: "#374151", color: "#f3f4f6" }}
            formatter={(value, name) => [
              `${(Number(value) / 1e9).toFixed(2)}B`,
              String(name),
            ]}
          />
          <Legend
            wrapperStyle={{ color: "#9ca3af", fontSize: 12 }}
          />
          {series.map((s, i) => (
            <Line
              key={`${s.name}-${i}`}
              type="monotone"
              dataKey={s.name}
              stroke={s.color || COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
