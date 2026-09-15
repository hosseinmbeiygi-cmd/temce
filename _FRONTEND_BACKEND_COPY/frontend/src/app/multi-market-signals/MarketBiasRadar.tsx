"use client";

import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from "recharts";

interface MarketBias {
  bias: string;
  buy_pct: number;
  sell_pct: number;
  total: number;
}

const MARKET_LABELS: Record<string, string> = {
  stock: "سهام",
  gold: "طلا",
  currency: "ارز",
  crypto: "رمزارز",
  option: "آپشن",
  commodity: "کالا",
  ime: "بورس کالا",
};

interface Props {
  biases: Record<string, MarketBias>;
}

export default function MarketBiasRadar({ biases }: Props) {
  const data = Object.entries(MARKET_LABELS)
    .filter(([market]) => biases[market] != null)
    .map(([market, label]) => {
      const bias = biases[market];
      return {
        market: label,
        buy: bias.buy_pct,
        sell: bias.sell_pct,
        total: bias.total,
      };
    });

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-surface-500 text-sm">
        داده‌ای برای رادار موجود نیست
      </div>
    );
  }

  return (
    <div dir="ltr">
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="#334155" strokeDasharray="3 3" />
          <PolarAngleAxis
            dataKey="market"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fill: "#64748b", fontSize: 9 }}
            stroke="#334155"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              fontSize: "12px",
              fontFamily: "Vazirmatn, sans-serif",
              direction: "rtl",
            }}
            formatter={((value: number, name: string) => [
              `${value}%`,
              name === "buy" ? "خرید" : "فروش",
            ]) as never}
          />
          <Radar
            name="خرید"
            dataKey="buy"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.15}
            strokeWidth={2}
          />
          <Radar
            name="فروش"
            dataKey="sell"
            stroke="#f43f5e"
            fill="#f43f5e"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
