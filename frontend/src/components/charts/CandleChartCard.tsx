"use client";

import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardAction } from "@/components/ui/Card";
import { CandleDataPoint } from "@/lib/types";

interface CandleChartCardProps {
  title?: string;
  data: CandleDataPoint[];
  symbol?: string;
  height?: number;
  showVolume?: boolean;
}

// ── Custom Candlestick Shape ──────────────
function CandlestickShape(props: any) {
  const { x, y, width, height, payload } = props;
  if (!payload || !width) return null;

  const { open, close, high, low } = payload;
  const isUp = close >= open;
  const color = isUp ? "var(--positive)" : "var(--negative)";

  // Scale prices to chart coordinates
  const chartHeight = props.chartHeight || 200;
  const yMin = props.yMin || 0;
  const yMax = props.yMax || 1;
  const range = yMax - yMin || 1;

  const scaleY = (price: number) =>
    y + (yMax - price) / range * chartHeight;

  const bodyTop = scaleY(Math.max(open, close));
  const bodyBottom = scaleY(Math.min(open, close));
  const bodyHeight = Math.max(1, bodyBottom - bodyTop);
  const wickX = x + width / 2;
  const candleWidth = Math.max(2, width * 0.7);

  return (
    <g>
      {/* Wick (high-low line) */}
      <line
        x1={wickX}
        y1={scaleY(high)}
        x2={wickX}
        y2={scaleY(low)}
        stroke={color}
        strokeWidth={1}
      />
      {/* Body (open-close rectangle) */}
      <rect
        x={x + (width - candleWidth) / 2}
        y={bodyTop}
        width={candleWidth}
        height={bodyHeight}
        fill={color}
        rx={1}
      />
    </g>
  );
}

// ── Custom Volume Bar Shape ───────────────
function VolumeShape(props: any) {
  const { x, y, width, height, payload } = props;
  if (!payload || !width) return null;

  const isUp = payload.close >= payload.open;
  const volHeight = (payload.volume / 5000000) * height;
  const volColor = isUp ? "rgba(0,245,212,0.2)" : "rgba(247,37,133,0.2)";

  return (
    <rect
      x={x + width * 0.1}
      y={height - volHeight}
      width={width * 0.8}
      height={volHeight}
      fill={volColor}
      rx={1}
    />
  );
}

// ── Price Formatter ───────────────────────
const priceFormat = (v: number) => v.toLocaleString("fa-IR");

export default function CandleChartCard({
  title = "نمودار کندلاستیک",
  data,
  symbol = "",
  height = 350,
  showVolume = true,
}: CandleChartCardProps) {
  const [range, setRange] = useState<"1w" | "1m" | "3m">("1m");

  const filteredData = useMemo(() => {
    const count = range === "1w" ? 7 : range === "1m" ? 30 : 60;
    return data.slice(-count);
  }, [data, range]);

  const prices = filteredData.flatMap((d) => [d.high, d.low]);
  const yMin = Math.min(...prices);
  const yMax = Math.max(...prices);
  const range_px = yMax - yMin || 1;
  const padding = range_px * 0.05;

  const formatYAxis = (v: number) => {
    if (v >= 10000) return `${(v / 1000).toFixed(0)}K`;
    return v.toString();
  };

  return (
    <Card
      title={title}
      actions={
        <>
          <CardAction active={range === "1w"} onClick={() => setRange("1w")}>۱ هفته</CardAction>
          <CardAction active={range === "1m"} onClick={() => setRange("1m")}>۱ ماه</CardAction>
          <CardAction active={range === "3m"} onClick={() => setRange("3m")}>۳ ماه</CardAction>
        </>
      }
    >
      {/* ── Price Stats Bar ────────── */}
      {symbol && (
        <div
          style={{
            display: "flex",
            gap: 16,
            padding: "8px 0",
            marginBottom: 8,
            borderBottom: "1px solid var(--glass-border)",
          }}
        >
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {symbol}{" "}
            <span style={{ color: "var(--text-primary)", fontWeight: 700, fontFamily: "Inter" }}>
              {priceFormat(filteredData[filteredData.length - 1]?.close || 0)}
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            بیشترین{" "}
            <span style={{ color: "var(--positive)", fontFamily: "Inter" }}>
              {priceFormat(yMax)}
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            کمترین{" "}
            <span style={{ color: "var(--negative)", fontFamily: "Inter" }}>
              {priceFormat(yMin)}
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            حجم{" "}
            <span style={{ color: "var(--text-primary)", fontFamily: "Inter" }}>
              {(filteredData.reduce((s, d) => s + d.volume, 0) / 1000000).toFixed(0)}M
            </span>
          </div>
        </div>
      )}

      {/* ── Candlestick Chart ──────── */}
      <div style={{ width: "100%", height: showVolume ? height - 60 : height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={filteredData}
            margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(128,128,128,0.08)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: "var(--text-secondary)", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              domain={[yMin - padding, yMax + padding]}
              tick={{ fill: "var(--text-secondary)", fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatYAxis}
              width={45}
              orientation="right"
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                fontSize: "11px",
                backdropFilter: "blur(10px)",
              }}
              formatter={(value: number, name: string) => {
                const labels: Record<string, string> = {
                  open: "بازگشایش",
                  high: "بیشترین",
                  low: "کمترین",
                  close: "بسته شدن",
                  volume: "حجم",
                };
                return [priceFormat(value), labels[name] || name];
              }}
              labelFormatter={(label: string) => `📅 ${label}`}
            />
            <Bar
              dataKey="high"
              shape={<CandlestickShape chartHeight={height - 110} yMin={yMin - padding} yMax={yMax + padding} />}
              isAnimationActive={false}
            >
              {filteredData.map((entry, i) => (
                <Cell key={i} fill={entry.isUp ? "var(--positive)" : "var(--negative)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* ── Volume Bars ────────────── */}
      {showVolume && (
        <div style={{ width: "100%", height: 50, marginTop: 4 }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
            <BarChart data={filteredData} margin={{ top: 0, right: 5, left: 0, bottom: 0 }}>
              <Bar dataKey="volume" shape={<VolumeShape />} isAnimationActive={false}>
                {filteredData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.isUp ? "rgba(0,245,212,0.3)" : "rgba(247,37,133,0.3)"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
