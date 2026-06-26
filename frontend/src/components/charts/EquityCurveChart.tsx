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
import ChartContainer from "@/components/charts/ChartContainer";

interface EquityCurveChartProps {
  positions: { market_value: number }[];
}

export default function EquityCurveChart({ positions }: EquityCurveChartProps) {
  const data = positions.map((p, i) => ({ name: i, val: p.market_value }));

  return (
    <ChartContainer height={256}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <XAxis dataKey="name" hide />
          <YAxis stroke="#4b5563" fontSize={12} tickFormatter={(val) => `${(val / 1e9).toFixed(1)}B`} />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", borderColor: "#374151", color: "#f3f4f6" }}
            itemStyle={{ color: "#818cf8" }}
          />
          <Area type="monotone" dataKey="val" stroke="#6366f1" fillOpacity={1} fill="url(#colorVal)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
