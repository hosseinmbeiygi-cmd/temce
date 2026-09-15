"use client";

import { useMemo } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { FundScore } from "@/lib/fund-analysis";

interface FundScoreRadarProps {
  scores: FundScore;
  size?: number;
  showLabels?: boolean;
  compact?: boolean;
}

const DIMENSIONS = [
  { key: "financial", label: "مالی", fullLabel: "بازدهی و عملکرد" },
  { key: "liquidity", label: "نقدشوندگی", fullLabel: "حجم و عمق بازار" },
  { key: "management", label: "مدیریت", fullLabel: "تجربه و ثبات" },
  { key: "risk", label: "ریسک", fullLabel: "نوسان و افت" },
  { key: "cost", label: "هزینه", fullLabel: "کارمزد و صرف" },
  { key: "transparency", label: "شفافیت", fullLabel: "گزارش‌دهی" },
];

function scoreColor(s: number): string {
  if (s >= 75) return "#10b981";
  if (s >= 60) return "#6366f1";
  if (s >= 45) return "#f59e0b";
  return "#ef4444";
}

function RadarTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { dimension: string; value: number; fullLabel: string } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg px-3 py-2 shadow-xl text-xs border backdrop-blur-xl"
      style={{ background: "rgba(15, 23, 42, 0.95)", border: "1px solid rgba(71, 85, 105, 0.4)", color: "#e2e8f0" }}
    >
      <p className="font-bold text-[11px] mb-0.5">{d.fullLabel}</p>
      <p className="font-mono" style={{ color: scoreColor(d.value) }}>{d.value}%</p>
    </div>
  );
}

export default function FundScoreRadar({ scores, size = 280, compact = false }: FundScoreRadarProps) {
  const data = useMemo(() =>
    DIMENSIONS.map((d) => ({
      dimension: d.label,
      fullLabel: d.fullLabel,
      value: scores[d.key as keyof Omit<FundScore, "total">] ?? 0,
      fullMark: 100,
    })),
    [scores]
  );

  const avg = scores.total;
  const chartSize = compact ? 200 : size;

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={chartSize} minWidth={0}>
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="rgba(100, 116, 139, 0.15)" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fill: "#94a3b8", fontSize: compact ? 10 : 11, fontWeight: 600 }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fill: "#475569", fontSize: 9 }}
            axisLine={false}
            tickCount={5}
          />
          <Tooltip content={<RadarTooltip />} />
          <Radar
            name="امتیاز"
            dataKey="value"
            stroke={scoreColor(avg)}
            strokeWidth={2}
            fill={scoreColor(avg)}
            fillOpacity={0.2}
            dot={{ r: 4, fill: scoreColor(avg), stroke: "#0f172a", strokeWidth: 2 }}
          />
        </RadarChart>
      </ResponsiveContainer>
      {/* Center score */}
      <div className="mt-2 text-center">
        <span className="font-mono text-2xl font-black" style={{ color: scoreColor(avg) }}>
          {avg}
        </span>
        <span className="text-xs text-surface-500 mr-1">از ۱۰۰</span>
      </div>
    </div>
  );
}
