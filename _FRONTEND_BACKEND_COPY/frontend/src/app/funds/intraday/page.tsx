"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { useFundCandles, useTopFunds, type TopMetric } from "@/hooks/useFundIntraday";

// Load chart client-side only (lightweight-charts touches the DOM).
const IntradayCandleChart = dynamic(
  () => import("@/components/IntradayCandleChart"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[360px] bg-surface-900/30 animate-pulse rounded" />
    ),
  }
);

const METRIC_LABELS: Record<TopMetric, string> = {
  market_value: "اندازه صندوق",
  trade_volume: "حجم معامله",
  trade_value: "ارزش معامله",
  nav_change_pct: "تغییر NAV",
  intraday_volume: "تعداد تیک",
};

const CANDLE_INTERVALS = [1, 5, 15, 30] as const;

export default function FundsIntradayPage() {
  const [metric, setMetric] = useState<TopMetric>("intraday_volume");
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [intervalMin, setIntervalMin] = useState<number>(5);
  const [overlays, setOverlays] = useState<Array<"SMA20" | "SMA50" | "EMA20">>([
    "SMA20",
    "EMA20",
  ]);

  const topQuery = useTopFunds(metric, 20);

  const symbols = useMemo(
    () => topQuery.data?.items.map((i) => i.symbol) ?? [],
    [topQuery.data]
  );

  // Auto-pick the top-ranked symbol when the list loads.
  const firstSymbol = symbols[0] ?? null;
  const activeSymbol = selectedSymbol ?? firstSymbol;

  const candlesQuery = useFundCandles(
    activeSymbol ? [activeSymbol] : [],
    { intervalMinutes: intervalMin }
  );

  const activeCandles = activeSymbol
    ? candlesQuery.data?.symbols?.[activeSymbol]?.candles ?? []
    : [];

  return (
    <AppLayout>
      <div className="space-y-6">
        <header className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">صندوق‌ها — داده‌های درون‌روز</h1>
            <p className="text-sm text-gray-400 mt-1">
              رتبه‌بندی صندوق‌ها بر اساس معیار انتخابی + کندل OHLCV درون‌روز
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">معیار:</label>
            <select
              value={metric}
              onChange={(e) => {
                setMetric(e.target.value as TopMetric);
                setSelectedSymbol(null);
              }}
              className="bg-surface-800 text-white text-sm rounded-md border border-surface-700 px-2 py-1"
            >
              {(Object.keys(METRIC_LABELS) as TopMetric[]).map((m) => (
                <option key={m} value={m}>
                  {METRIC_LABELS[m]}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Top funds list */}
            <Card className="p-4 lg:col-span-1">
            <h2 className="text-sm font-semibold text-gray-300 mb-3">
              برترین‌ها ({METRIC_LABELS[metric]})
            </h2>
            {topQuery.isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-6" />
                ))}
              </div>
            ) : topQuery.isError ? (
              <p className="text-rose-400 text-xs">خطا در بارگذاری</p>
            ) : (
              <ol className="space-y-1">
                {topQuery.data?.items.map((it) => {
                  const isActive = it.symbol === activeSymbol;
                  return (
                    <li key={it.symbol}>
                      <button
                        onClick={() => setSelectedSymbol(it.symbol)}
                        className={`w-full flex items-center justify-between text-right rounded px-2 py-1.5 text-sm transition ${
                          isActive
                            ? "bg-emerald-700/30 text-emerald-200"
                            : "hover:bg-surface-700/50 text-gray-200"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span className="text-xs text-gray-500 w-6">
                            #{it.rank}
                          </span>
                          <span className="font-medium">{it.symbol}</span>
                        </span>
                        <span className="text-xs text-gray-400">
                          {formatMetric(metric, it.metric_value)}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}
          </Card>

          {/* Candle chart placeholder + table */}
          <Card className="p-4 lg:col-span-2">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <h2 className="text-sm font-semibold text-gray-300">
                کندل {intervalMin} دقیقه‌ای — {activeSymbol ?? "—"}
                {candlesQuery.data?.symbols?.[activeSymbol ?? ""]?.trade_date && (
                  <span className="text-gray-500 mr-2 text-xs font-normal">
                    ({candlesQuery.data.symbols[activeSymbol!].trade_date})
                  </span>
                )}
              </h2>
              <div className="flex items-center gap-1">
                {CANDLE_INTERVALS.map((m) => (
                  <button
                    key={m}
                    onClick={() => setIntervalMin(m)}
                    className={`text-xs px-2 py-0.5 rounded ${
                      intervalMin === m
                        ? "bg-emerald-600 text-white"
                        : "bg-surface-800 text-gray-400 hover:text-white"
                    }`}
                  >
                    {m}m
                  </button>
                ))}
              </div>
            </div>

            {candlesQuery.isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-4" />
                ))}
              </div>
            ) : candlesQuery.isError ? (
              <p className="text-rose-400 text-xs">خطا در بارگذاری کندل</p>
            ) : activeCandles.length === 0 ? (
              <p className="text-gray-500 text-sm">داده‌ای برای این صندوق موجود نیست.</p>
            ) : (
              <>
                <IntradayCandleChart
                  candles={activeCandles}
                  tradeDate={candlesQuery.data?.symbols?.[activeSymbol ?? ""]?.trade_date ?? null}
                  symbol={activeSymbol ?? undefined}
                  height={360}
                  overlays={overlays}
                />
                <div className="flex items-center gap-2 mt-2 text-xs">
                  <span className="text-gray-500">اندیکاتور:</span>
                  {(["SMA20", "SMA50", "EMA20"] as const).map((k) => {
                    const on = overlays.includes(k);
                    return (
                      <button
                        key={k}
                        onClick={() =>
                          setOverlays((prev) =>
                            on ? prev.filter((x) => x !== k) : [...prev, k]
                          )
                        }
                        className={`px-2 py-0.5 rounded border ${
                          on
                            ? "border-emerald-500 text-emerald-300 bg-emerald-900/30"
                            : "border-surface-700 text-gray-500 hover:text-gray-300"
                        }`}
                      >
                        {k}
                      </button>
                    );
                  })}
                </div>
                <div className="overflow-x-auto max-h-72 overflow-y-auto mt-3">
                  <table className="w-full text-xs">
                    <thead className="text-gray-500 sticky top-0 bg-surface-900">
                      <tr>
                        <th className="text-right px-2 py-1">دقیقه</th>
                        <th className="text-right px-2 py-1">open</th>
                        <th className="text-right px-2 py-1">high</th>
                        <th className="text-right px-2 py-1">low</th>
                        <th className="text-right px-2 py-1">close</th>
                        <th className="text-right px-2 py-1">حجم</th>
                        <th className="text-right px-2 py-1">vwap</th>
                        <th className="text-right px-2 py-1">تیک</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeCandles.map((c) => (
                        <tr key={c.minute} className="hover:bg-surface-800/50">
                          <td className="px-2 py-0.5 text-gray-300">{c.minute}</td>
                          <td className="px-2 py-0.5">{fmt(c.open)}</td>
                          <td className="px-2 py-0.5 text-emerald-400">{fmt(c.high)}</td>
                          <td className="px-2 py-0.5 text-rose-400">{fmt(c.low)}</td>
                          <td className="px-2 py-0.5">{fmt(c.close)}</td>
                          <td className="px-2 py-0.5 text-gray-400">{c.volume.toLocaleString()}</td>
                          <td className="px-2 py-0.5 text-gray-400">{fmt(c.vwap)}</td>
                          <td className="px-2 py-0.5 text-gray-400">{c.trades}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}

function fmt(n: number): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function formatMetric(metric: TopMetric, v: number): string {
  if (metric === "nav_change_pct") return `${v.toFixed(2)}%`;
  if (metric === "market_value" || metric === "trade_value") {
    if (v >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
    if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
    return v.toLocaleString("en-US");
  }
  if (metric === "intraday_volume") return `${(v / 1000).toFixed(1)}K`;
  return v.toLocaleString("en-US");
}
