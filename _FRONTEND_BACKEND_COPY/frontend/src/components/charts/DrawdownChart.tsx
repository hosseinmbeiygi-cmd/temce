"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import ChartContainer from "@/components/charts/ChartContainer";

interface DrawdownChartProps {
  data: { index: number; drawdown: number; date?: string }[];
  height?: number;
}

function formatValue(v: number): string {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function DrawdownChart({ data, height = 200 }: DrawdownChartProps) {
  const maxDD = data.length > 0 ? Math.min(...data.map(d => d.drawdown)) : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs text-surface-500">
          {data.length} روز معاملاتی
        </span>
        <span className="text-xs font-bold text-accent-rose">
          حداکثر Drawdown: {maxDD.toFixed(2)}%
        </span>
      </div>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.45} />
                <stop offset="60%" stopColor="#ef4444" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="4 4"
              stroke="rgba(100, 116, 139, 0.12)"
              vertical={false}
            />
            <XAxis
              dataKey="index"
              hide
            />
            <YAxis
              stroke="#64748b"
              fontSize={10}
              tickFormatter={formatValue}
              width={55}
              domain={["dataMin", 0]}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)", strokeWidth: 1 }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const val = Number(payload[0].value);
                const d = payload[0].payload;
                return (
                  <div className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
                    style={{
                      background: "rgba(15, 23, 42, 0.96)",
                      border: "1px solid rgba(71, 85, 105, 0.5)",
                      color: "#e2e8f0",
                      minWidth: 140,
                      boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
                    }}>
                    <p className="text-[11px] font-bold text-surface-300 mb-2 pb-1.5 border-b border-surface-700/50">
                      روز {Number(label) + 1}{d?.date ? ` — ${d.date}` : ''}
                    </p>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-surface-400">Drawdown</span>
                      <span className="font-mono font-bold text-accent-rose" dir="ltr">
                        {val.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                );
              }}
              cursor={{
                stroke: "rgba(148, 163, 184, 0.3)",
                strokeDasharray: "3 3",
                strokeWidth: 1.5,
              }}
            />
            <ReferenceLine y={0} stroke="rgba(148, 163, 184, 0.3)" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              strokeWidth={2}
              fill="url(#ddGradient)"
              dot={false}
              activeDot={{
                r: 4,
                fill: "#ef4444",
                stroke: "rgba(15, 23, 42, 0.9)",
                strokeWidth: 3,
              }}
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  );
}
