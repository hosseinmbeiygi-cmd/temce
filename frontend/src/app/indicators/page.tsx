"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Line, Legend } from "recharts";
import AppLayout from "@/components/layout/AppLayout";
import IndicatorChart, { formatNum } from "@/components/IndicatorChart";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import { apiGet } from "@/lib/api";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------
interface IndicatorResult {
  symbol: string;
  indicator: string;
  params: Record<string, number>;
  dates: string[];
  values: number[] | Record<string, number[]>;
}

const INDICATOR_DEFS = [
  { key: "sma", label: "SMA — میانگین متحرک ساده", params: ["period"], defaults: { period: 14 } },
  { key: "ema", label: "EMA — میانگین متحرک نمایی", params: ["period"], defaults: { period: 14 } },
  { key: "rsi", label: "RSI — شاخص قدرت نسبی", params: ["period"], defaults: { period: 14 } },
  { key: "macd", label: "MACD — واگرایی میانگین متحرک", params: ["fast", "slow", "signal"], defaults: { fast: 12, slow: 26, signal: 9 } },
  { key: "bollinger", label: "Bollinger Bands — باندهای بولینگر", params: ["period", "stddev"], defaults: { period: 20, stddev: 2 } },
  { key: "stochastic", label: "Stochastic — استوکاستیک", params: ["period", "k_smooth", "d_smooth"], defaults: { period: 14, k_smooth: 3, d_smooth: 3 } },
  { key: "atr", label: "ATR — محدوده واقعی میانگین", params: ["period"], defaults: { period: 14 } },
  { key: "obv", label: "OBV — حجم تعادلی", params: [], defaults: {} },
  { key: "williams_r", label: "Williams %R — ویلیامز", params: ["period"], defaults: { period: 14 } },
  { key: "ichimoku", label: "Ichimoku — ایچیموکو", params: ["tenkan", "kijun", "senkou_b"], defaults: { tenkan: 9, kijun: 26, senkou_b: 52 } },
] as const;

const MULTI_LINE_INDICATORS = new Set(["macd", "bollinger", "stochastic", "ichimoku"]);

// Color palette for multi-line indicators
const LINE_COLORS: Record<string, string> = {
  macd: "#22c55e",
  signal: "#f59e0b",
  histogram: "#94a3b8",
  upper: "#ef4444",
  middle: "#f59e0b",
  lower: "#22c55e",
  k: "#3b82f6",
  d: "#ef4444",
  tenkan: "#f59e0b",
  kijun: "#3b82f6",
  senkou_a: "#22c55e",
  senkou_b: "#ef4444",
  chikou: "#a855f7",
  default: "#3b82f6",
};

const LINE_NAMES: Record<string, string> = {
  macd: "خط مکدی",
  signal: "سیگنال",
  histogram: "هیستوگرام",
  upper: "بالا",
  middle: "وسط",
  lower: "پایین",
  k: "%K",
  d: "%D",
  tenkan: "تنکان",
  kijun: "کیجون",
  senkou_a: "Senkou A",
  senkou_b: "Senkou B",
  chikou: "Chikou",
};

// ------ Helpers ------------------------------------------------------------------------------------------------------------------------------------
function toDisplayDate(iso: string): string {
  if (!iso) return "";
  const parts = iso.split("-");
  if (parts.length === 3) return `${parts[0]}/${parts[1]}/${parts[2]}`;
  return iso;
}

// ------ Main Page ------------------------------------------------------------------------------------------------------------------------------
export default function IndicatorsPage() {
  const [symbol, setSymbol] = useState("فولاد");
  const [indicatorKey, setIndicatorKey] = useState("sma");
  const [params, setParams] = useState<Record<string, number>>({ period: 14 });

  const currentDef = INDICATOR_DEFS.find((d) => d.key === indicatorKey)!;

  // Reset params when indicator changes
  useEffect(() => {
    // Sync derived form state to the new indicator's defaults.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setParams({ ...currentDef.defaults });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indicatorKey]);

  const isMultiLine = MULTI_LINE_INDICATORS.has(indicatorKey);

  const queryParams = useMemo(() => {
    const p = new URLSearchParams({ indicator: indicatorKey });
    Object.entries(params).forEach(([k, v]) => p.set(k, String(v)));
    return p.toString();
  }, [indicatorKey, params]);

  const {
    data: result,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["indicator", symbol, indicatorKey, params],
    queryFn: async (): Promise<IndicatorResult> => {
      const url = `/market/indicator/${encodeURIComponent(symbol)}?${queryParams}`;
      const res = await apiGet<{ success: boolean; data: IndicatorResult; error?: { message: string } }>(url);
      if (!res.success) throw new Error(res.error?.message || "خطا در دریافت داده");
      return res.data;
    },
    enabled: !!symbol,
    refetchOnWindowFocus: false,
  });

  // Build chart data from dates + values
  const chartData = useMemo(() => {
    if (!result) return [];
    const dates = result.dates || [];
    const values = result.values;
    if (!dates.length) return [];

    if (isMultiLine && values && typeof values === "object") {
      const seriesMap = values as Record<string, number[]>;
      const keys = Object.keys(seriesMap);
      const data: Record<string, unknown>[] = [];
      for (let i = 0; i < dates.length; i++) {
        const row: Record<string, unknown> = { date: toDisplayDate(dates[i] || "") };
        keys.forEach((k) => {
          row[k] = seriesMap[k]?.[i] ?? null;
        });
        data.push(row);
      }
      return data;
    }

    if (Array.isArray(values)) {
      const vals = values as number[];
      return dates.map((d, i) => ({
        date: toDisplayDate(d || ""),
        value: vals[i] ?? null,
      }));
    }

    return [];
  }, [result, isMultiLine]);

  // Stats
  const stats = useMemo(() => {
    if (!result || !chartData.length) return null;
    if (isMultiLine && result.values && typeof result.values === "object") {
      const seriesMap = result.values as Record<string, number[]>;
      const keys = Object.keys(seriesMap);
      return keys.map((k) => {
        const vals = seriesMap[k].filter((v) => v != null);
        if (!vals.length) return null;
        return {
          key: k,
          label: LINE_NAMES[k] || k,
          last: vals[vals.length - 1],
          min: Math.min(...vals),
          max: Math.max(...vals),
          avg: vals.reduce((a, b) => a + b, 0) / vals.length,
        };
      }).filter(Boolean);
    }
    if (Array.isArray(result.values)) {
      const vals = result.values as number[];
      return [{
        key: "value",
        label: indicatorKey.toUpperCase(),
        last: vals[vals.length - 1],
        min: Math.min(...vals),
        max: Math.max(...vals),
        avg: vals.reduce((a, b) => a + b, 0) / vals.length,
      }];
    }
    return null;
  }, [result, chartData, isMultiLine, indicatorKey]);

  const handleParamChange = useCallback((key: string, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      setParams((prev) => ({ ...prev, [key]: num }));
    }
  }, []);

  return (
    <AppLayout title="اندیکاتورهای تکنیکال" subtitle="نمودار اندیکاتور با داده واقعی از BrsAPI">
      {/* ------ Controls --------------------------------------------------------------------------------------------- */}
      <div className="glass-card p-5 mb-5">
        <div className="flex flex-wrap items-end gap-4">
          {/* Symbol */}
          <div>
            <label className="block text-xs text-surface-500 mb-1.5">نماد</label>
            <SymbolSelector value={symbol} onChange={setSymbol} />
          </div>

          {/* Indicator type */}
          <div>
            <label className="block text-xs text-surface-500 mb-1.5">اندیکاتور</label>
            <select
              value={indicatorKey}
              onChange={(e) => setIndicatorKey(e.target.value)}
              className="bg-surface-800 border border-surface-700 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-primary-500 appearance-none cursor-pointer min-w-[240px]"
            >
              {INDICATOR_DEFS.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          {/* Dynamic params */}
          {currentDef.params.map((pKey) => (
            <div key={pKey}>
              <label className="block text-xs text-surface-500 mb-1.5 capitalize">
                {pKey === "stddev"
                  ? "σ (StdDev)"
                  : pKey === "k_smooth"
                  ? "%K Smooth"
                  : pKey === "d_smooth"
                  ? "%D Smooth"
                  : pKey === "senkou_b"
                  ? "Senkou B"
                  : pKey === "tenkan"
                  ? "Tenkan"
                  : pKey === "kijun"
                  ? "Kijun"
                  : pKey === "fast"
                  ? "Fast"
                  : pKey === "slow"
                  ? "Slow"
                  : pKey === "signal"
                  ? "Signal"
                  : pKey}
              </label>
              <input
                type="number"
                value={params[pKey] ?? ""}
                onChange={(e) => handleParamChange(pKey, e.target.value)}
                step={pKey === "stddev" ? 0.5 : 1}
                className="bg-surface-800 border border-surface-700 rounded-xl px-3 py-2.5 text-white text-sm w-20 outline-none focus:border-primary-500 text-center font-mono"
              />
            </div>
          ))}

          {/* Refresh */}
          <button
            onClick={() => refetch()}
            className="px-5 py-2.5 bg-primary-600 hover:bg-primary-500 text-white text-sm rounded-xl transition-colors font-medium"
          >
            🔄 بروزرسانی
          </button>
        </div>
      </div>

      {/* ------ Chart --------------------------------------------------------------------------------------------------------- */}
      <div className="glass-card p-5 mb-5">
        {isLoading ? (
          <Skeleton className="h-[420px] w-full rounded-xl" />
        ) : isError ? (
          <div className="flex flex-col items-center justify-center h-[420px] text-surface-500">
            <p className="text-4xl mb-3">⚠️</p>
            <p className="text-lg font-medium mb-1">خطا در دریافت داده</p>
            <p className="text-sm text-surface-600 max-w-md text-center">
              {error instanceof Error ? error.message : "داده‌ای برای این نماد و اندیکاتور یافت نشد"}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-surface-700 hover:bg-surface-600 text-surface-200 text-sm rounded-lg transition-colors"
            >
              تلاش مجدد
            </button>
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[420px] text-surface-500">
            <p className="text-4xl mb-3">📊</p>
            <p className="text-lg font-medium mb-1">داده‌ای برای نمایش وجود ندارد</p>
            <p className="text-sm text-surface-600">داده‌ای برای این نماد و اندیکاتور یافت نشد</p>
          </div>
        ) : (
          <div className="space-y-2">
            <h3 className="text-sm font-bold text-surface-300">
              {symbol} — {currentDef.label} {isMultiLine ? "" : `(${params.period || ""})`}
            </h3>
            <IndicatorChart
              data={chartData}
              tooltipFormatter={
                isMultiLine
                  ? (value: number, name: string) => `${formatNum(value)} (${LINE_NAMES[name] || name})`
                  : undefined
              }
            >
              {isMultiLine && result && typeof result.values === "object" ? (
                <>
                  {Object.keys(result.values as Record<string, number[]>).map((k) => (
                    <Line
                      key={k}
                      type="monotone"
                      dataKey={k}
                      stroke={LINE_COLORS[k] || LINE_COLORS.default}
                      strokeWidth={k === "histogram" ? 0 : 2}
                      dot={false}
                      activeDot={{ r: 3 }}
                      name={k}
                      connectNulls
                    />
                  ))}
                  <Legend
                    formatter={(value: string) => (
                      <span style={{ color: "#94a3b8", fontSize: "11px" }}>{LINE_NAMES[value] || value}</span>
                    )}
                  />
                </>
              ) : (
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={LINE_COLORS.default}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls
                />
              )}
            </IndicatorChart>
          </div>
        )}
      </div>

      {/* ------ Stats ------------------------------------------------------------------------------------------------------------ */}
      {stats && stats.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-bold text-surface-300 mb-4">📋 آمار</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((s) =>
              s ? (
                <div key={s.key} className="bg-surface-800/50 rounded-xl p-4 text-center">
                  <div className="flex items-center justify-center gap-2 mb-1">
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: LINE_COLORS[s.key] || LINE_COLORS.default }}
                    />
                    <span className="text-xs text-surface-500">{s.label}</span>
                  </div>
                  <p className="font-mono font-bold text-surface-100 text-lg">{formatNum(s.last)}</p>
                  <div className="flex justify-between mt-2 text-[10px] text-surface-600 font-mono">
                    <span>کمترین: {formatNum(s.min)}</span>
                    <span>میانگین: {formatNum(s.avg)}</span>
                    <span>بیشترین: {formatNum(s.max)}</span>
                  </div>
                </div>
              ) : null
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
}
