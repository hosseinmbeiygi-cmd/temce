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
  height?: number;
}

export default function EquityCurveChart({ positions, height = 280 }: EquityCurveChartProps) {
  const data = positions.map((p, i) => ({ name: i, val: p.market_value }));

  const firstVal = data.length > 0 ? data[0].val : 1;
  const lastVal = data.length > 0 ? data[data.length - 1].val : 1;
  const totalReturn = ((lastVal - firstVal) / firstVal) * 100;
  const isPositive = totalReturn >= 0;

  const formatValue = (val: number) => {
    if (val >= 1_000_000_000_000) return `${(val / 1_000_000_000_000).toFixed(2)}T`;
    if (val >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`;
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
    return val.toLocaleString("fa-IR");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs text-surface-500">
          {data.length} روز معاملاتی
        </span>
        <span className={`text-sm font-black ${isPositive ? 'text-accent-emerald' : 'text-accent-rose'}`}>
          {isPositive ? '▲' : '▼'} {Math.abs(totalReturn).toFixed(2)}%
        </span>
      </div>
      <ChartContainer height={height}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0.45} />
                <stop offset="60%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0.12} />
                <stop offset="100%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="4 4"
              stroke="rgba(100, 116, 139, 0.12)"
              vertical={false}
            />
            <XAxis
              dataKey="name"
              hide
            />
            <YAxis
              stroke="#64748b"
              fontSize={10}
              tickFormatter={formatValue}
              width={55}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)", strokeWidth: 1 }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const val = Number(payload[0].value);
                const returnPct = ((val - firstVal) / firstVal) * 100;
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
                      روز {Number(label) + 1}
                    </p>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-surface-400">ارزش</span>
                      <span className="font-mono font-bold text-surface-100" dir="ltr">{formatValue(val)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4 mt-1">
                      <span className="text-surface-400">بازده</span>
                      <span className={`font-mono font-bold ${returnPct >= 0 ? 'text-accent-emerald' : 'text-accent-rose'}`}>
                        {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
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
            <Area
              type="monotone"
              dataKey="val"
              stroke={isPositive ? "#10b981" : "#ef4444"}
              strokeWidth={2.5}
              fill="url(#equityGrad)"
              dot={false}
              activeDot={{
                r: 5,
                fill: isPositive ? "#10b981" : "#ef4444",
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
