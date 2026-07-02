"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import ChartContainer from "@/components/charts/ChartContainer";
import type { SentimentPoint } from "@/lib/types";

interface SentimentChartProps {
  data: SentimentPoint[];
}

export default function SentimentChart({ data }: SentimentChartProps) {
  return (
    <ChartContainer height={200}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.08)" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-secondary)", fontSize: 8 }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={30} />
          <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 9 }} tickLine={false} axisLine={false} width={25} />
          <Tooltip
            contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--glass-border)", borderRadius: "8px", fontSize: "11px" }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any, name: any) => {
              const labels: Record<string, string> = { positive: "مثبت", negative: "منفی", neutral: "خنثی" };
              return [`${Number(value) || 0}%`, String(labels[name] || name)];
            }}
          />
          <Bar dataKey="positive" stackId="a" fill="var(--positive)" radius={[0, 0, 0, 0]} />
          <Bar dataKey="neutral" stackId="a" fill="var(--neutral)" />
          <Bar dataKey="negative" stackId="a" fill="var(--negative)" radius={[0, 0, 3, 3]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
