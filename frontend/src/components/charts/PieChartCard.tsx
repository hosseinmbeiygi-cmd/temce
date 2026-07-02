"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card } from "@/components/ui/Card";
import ChartContainer from "@/components/charts/ChartContainer";
import { PieChartData } from "@/lib/types";

interface PieChartCardProps {
  title: string;
  data: PieChartData[];
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  showLegend?: boolean;
  valueFormatter?: (value: number) => string;
}

const defaultFormat = (v: number) => `${v.toFixed(1)}%`;

export default function PieChartCard({
  title,
  data,
  height = 220,
  innerRadius = 55,
  outerRadius = 85,
  showLegend = true,
  valueFormatter = defaultFormat,
}: PieChartCardProps) {
  return (
    <Card title={title}>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              dataKey="value"
              nameKey="name"
              paddingAngle={2}
              stroke="none"
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                color: "var(--text-primary)",
                fontSize: "12px",
                backdropFilter: "blur(10px)",
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => [
                valueFormatter(Number(value) || 0),
                String(name),
              ]}
            />
            {showLegend && (
              <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{
                  fontSize: "11px",
                  color: "var(--text-secondary)",
                  paddingTop: "8px",
                }}
              />
            )}
          </PieChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}
