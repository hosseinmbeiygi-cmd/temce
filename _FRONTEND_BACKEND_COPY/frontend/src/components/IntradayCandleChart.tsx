"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type LineData,
  type Time,
  ColorType,
  CrosshairMode,
} from "lightweight-charts";
import type { Candle } from "@/hooks/useFundIntraday";

function calcSMA(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    out.push(sum / period);
  }
  return out;
}

function calcEMA(values: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let ema: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null);
      continue;
    }
    if (ema === null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += values[j];
      ema = sum / period;
    } else {
      ema = (values[i] - ema) * k + ema;
    }
    out.push(ema);
  }
  return out;
}

interface Props {
  candles: Candle[];
  tradeDate: string | null;
  height?: number;
  symbol?: string;
  /** Optional moving-average overlays rendered on the price pane. */
  overlays?: Array<"SMA20" | "SMA50" | "EMA20">;
}

/**
 * Convert HH:MM candle bucket to a UTC timestamp anchored to the trade_date.
 * Returns seconds since epoch (Lightweight charts uses business-day or
 * timestamp seconds).
 */
function bucketToTimestamp(date: string | null, minute: string): number {
  // date is Jalali (YYYY-MM-DD) — we don't have a real gregorian here,
  // so just compose an arbitrary date prefix; the chart only needs
  // monotonically increasing numbers for x-axis ordering.
  const fallback = date || "1400-01-01";
  const [hh, mm] = minute.split(":").map(Number);
  // Parse Jalali YYYY-MM-DD as if gregorian (works for x-axis ordering).
  const [y, mo, d] = fallback.split("-").map(Number);
  return Math.floor(Date.UTC(y, mo - 1, d, hh, mm, 0) / 1000);
}

export default function IntradayCandleChart({
  candles,
  tradeDate,
  height = 360,
  symbol,
  overlays = ["SMA20", "EMA20"],
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // ── Initialize chart once ────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(75, 85, 99, 0.2)" },
        horzLines: { color: "rgba(75, 85, 99, 0.2)" },
      },
      rightPriceScale: {
        borderColor: "rgba(75, 85, 99, 0.4)",
      },
      timeScale: {
        borderColor: "rgba(75, 85, 99, 0.4)",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 8,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#6b7280", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#374151" },
        horzLine: { color: "#6b7280", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#374151" },
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      color: "rgba(75, 85, 99, 0.5)",
    });
    // Volume pane is ~20% of the chart height.
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const onResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [height]);

  // ── Update data when candles change ──────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
    if (candles.length === 0) {
      candleSeriesRef.current.setData([]);
      volumeSeriesRef.current.setData([]);
      return;
    }

    const candleData: CandlestickData[] = candles.map((c) => ({
      time: bucketToTimestamp(tradeDate, c.minute) as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    const volData: HistogramData[] = candles.map((c) => ({
      time: bucketToTimestamp(tradeDate, c.minute) as Time,
      value: c.volume,
      color:
        c.close >= c.open
          ? "rgba(16, 185, 129, 0.5)"
          : "rgba(239, 68, 68, 0.5)",
    }));

    candleSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volData);

    // ── Overlay indicators ───────────────────────────────
    if (!chartRef.current) return;
    const closes = candles.map((c) => c.close);
    const times = candles.map(
      (c) => bucketToTimestamp(tradeDate, c.minute) as Time
    );

    const buildLine = (values: (number | null)[]): LineData[] =>
      values
        .map((v, i): LineData | null =>
          v == null ? null : { time: times[i], value: v }
        )
        .filter((x): x is LineData => x !== null);

    // Clean up old overlay series, then add fresh ones.
    const chart = chartRef.current;
    // Lightweight-charts v5: get all series on every pane, then drop non-core ones.
    const allSeries: unknown[] = [];
    const c = chart as unknown as {
      panes?: () => Array<{ getSeries: () => unknown[] }>;
      getSeries?: () => unknown[];
    };
    if (typeof c.panes === "function") {
      c.panes().forEach((p) => allSeries.push(...p.getSeries()));
    } else if (typeof c.getSeries === "function") {
      allSeries.push(...c.getSeries());
    }
    for (const s of allSeries) {
      if (s === candleSeriesRef.current || s === volumeSeriesRef.current) continue;
      try {
        chart.removeSeries(s as never);
      } catch {
        // already detached
      }
    }

    const overlaySpec: Record<string, { period: number; kind: "SMA" | "EMA"; color: string; width: number }> = {
      SMA20: { period: 20, kind: "SMA", color: "#fbbf24", width: 1.5 },
      SMA50: { period: 50, kind: "SMA", color: "#a78bfa", width: 1.5 },
      EMA20: { period: 20, kind: "EMA", color: "#60a5fa", width: 1.5 },
    };
    for (const key of overlays) {
      const spec = overlaySpec[key];
      if (!spec) continue;
      const values =
        spec.kind === "SMA" ? calcSMA(closes, spec.period) : calcEMA(closes, spec.period);
      const lineData = buildLine(values);
      if (lineData.length === 0) continue;
      const s = chart.addSeries(LineSeries, {
        color: spec.color,
        lineWidth: spec.width as 1 | 2 | 3 | 4,
        title: key,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      s.setData(lineData);
    }

    chart.timeScale().fitContent();
  }, [candles, tradeDate, overlays]);

  if (candles.length === 0) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center text-gray-500 text-sm bg-surface-900/30 rounded"
      >
        {symbol ? `داده‌ای برای ${symbol} موجود نیست` : "داده‌ای موجود نیست"}
      </div>
    );
  }

  return <div ref={containerRef} style={{ height }} className="w-full" />;
}
