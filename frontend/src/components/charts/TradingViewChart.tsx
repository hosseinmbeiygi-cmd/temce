"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type LineData,
  type Time,
  ColorType,
  CrosshairMode,
  LineStyle,
} from "lightweight-charts";
import { Card, CardAction } from "@/components/ui/Card";
import { CandleDataPoint } from "@/lib/types";

// ─── Types ───────────────────────────────────────────────────────────────────

type Timeframe = "1D" | "1W" | "1M" | "3M" | "6M" | "1Y" | "ALL";
type OverlayIndicator = "SMA" | "EMA" | "BB" | "none";
type SubIndicator = "RSI" | "MACD" | "none";

interface TradingViewChartProps {
  title?: string;
  data: CandleDataPoint[];
  symbol?: string;
  height?: number;
  showVolume?: boolean;
}

// ─── Indicator Calculations ──────────────────────────────────────────────────

function calcSMA(closes: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += closes[j];
      result.push(sum / period);
    }
  }
  return result;
}

function calcEMA(closes: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const result: (number | null)[] = [];
  let ema: number | null = null;
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else if (ema === null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += closes[j];
      ema = sum / period;
      result.push(ema);
    } else {
      ema = (closes[i] - ema) * k + ema;
      result.push(ema);
    }
  }
  return result;
}

function calcBB(
  closes: number[],
  period: number,
  stdMult: number
): { upper: (number | null)[]; middle: (number | null)[]; lower: (number | null)[] } {
  const sma = calcSMA(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (sma[i] === null) {
      upper.push(null);
      lower.push(null);
    } else {
      let variance = 0;
      for (let j = i - period + 1; j <= i; j++) {
        variance += (closes[j] - (sma[i] as number)) ** 2;
      }
      const std = Math.sqrt(variance / period);
      upper.push((sma[i] as number) + stdMult * std);
      lower.push((sma[i] as number) - stdMult * std);
    }
  }
  return { upper, middle: sma, lower };
}

function calcRSI(closes: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [null];
  const gains: number[] = [];
  const losses: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    gains.push(diff > 0 ? diff : 0);
    losses.push(diff < 0 ? -diff : 0);
    if (i < period) {
      result.push(null);
    } else {
      let avgGain = 0;
      let avgLoss = 0;
      for (let j = i - period; j < i; j++) {
        avgGain += gains[j];
        avgLoss += losses[j];
      }
      avgGain /= period;
      avgLoss /= period;
      if (avgLoss === 0) {
        result.push(100);
      } else {
        const rs = avgGain / avgLoss;
        result.push(100 - 100 / (1 + rs));
      }
    }
  }
  return result;
}

function calcMACD(
  closes: number[]
): { macd: (number | null)[]; signal: (number | null)[]; histogram: (number | null)[] } {
  const ema12 = calcEMA(closes, 12);
  const ema26 = calcEMA(closes, 26);
  const macdLine: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (ema12[i] !== null && ema26[i] !== null) {
      macdLine.push((ema12[i] as number) - (ema26[i] as number));
    } else {
      macdLine.push(null);
    }
  }
  const validMacd = macdLine.filter((v) => v !== null) as number[];
  const signalEma = calcEMA(validMacd, 9);
  const signal: (number | null)[] = [];
  let vi = 0;
  for (let i = 0; i < macdLine.length; i++) {
    if (macdLine[i] === null) {
      signal.push(null);
    } else {
      signal.push(signalEma[vi] ?? null);
      vi++;
    }
  }
  const histogram: (number | null)[] = [];
  for (let i = 0; i < macdLine.length; i++) {
    if (macdLine[i] !== null && signal[i] !== null) {
      histogram.push((macdLine[i] as number) - (signal[i] as number));
    } else {
      histogram.push(null);
    }
  }
  return { macd: macdLine, signal, histogram };
}

// ─── Timeframe Filtering ─────────────────────────────────────────────────────

const TIMEFRAME_DAYS: Record<Timeframe, number> = {
  "1D": 1,
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
  ALL: 9999,
};

function filterByTimeframe(data: CandleDataPoint[], tf: Timeframe): CandleDataPoint[] {
  const days = TIMEFRAME_DAYS[tf];
  if (days >= 9999) return data;
  // Intraday series (bars carry a ``time`` component) are already limited by
  // the API to the current session — slicing by day count would cut the whole
  // realtime chart down to a single bar.
  const isIntraday = data.some((d) => Boolean(d.time));
  if (isIntraday) return data;
  return data.slice(-days);
}

function toUnix(dateStr: string, timeStr?: string): number {
  if (!dateStr) return 0;
  const parts = dateStr.replace(/\//g, "-").split("-").map(Number);
  if (parts.length < 3) return 0;
  const hm = (timeStr || "").split(":").map(Number);
  const h = hm.length >= 1 && Number.isFinite(hm[0]) ? hm[0] : 0;
  const m = hm.length >= 2 && Number.isFinite(hm[1]) ? hm[1] : 0;
  if (parts[0] > 1500) {
    // Gregorian date
    return Math.floor(new Date(parts[0], parts[1] - 1, parts[2], h, m).getTime() / 1000);
  }
  // Jalali date → approximate Gregorian year
  const gy = parts[0] + 621;
  return Math.floor(new Date(gy, parts[1] - 1, parts[2], h, m).getTime() / 1000);
}

function toTime(dateStr: string, timeStr?: string): Time {
  return toUnix(dateStr, timeStr) as unknown as Time;
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function TradingViewChart({
  title = "نمودار پیشرفته",
  data,
  symbol = "",
  height = 500,
  showVolume = true,
}: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const overlaySeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const subChartRef = useRef<IChartApi | null>(null);
  const subSeriesRef = useRef<ISeriesApi<"Line" | "Histogram">[]>([]);
  const subContainerRef = useRef<HTMLDivElement | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const [timeframe, setTimeframe] = useState<Timeframe>("1M");
  const [overlay, setOverlay] = useState<OverlayIndicator>("none");
  const [subIndicator, setSubIndicator] = useState<SubIndicator>("none");
  const [hoverData, setHoverData] = useState<CandleDataPoint | null>(null);

  const filteredData = useMemo(() => filterByTimeframe(data, timeframe), [data, timeframe]);

  // True when the series is an intraday (2-min) realtime chart
  const isIntraday = useMemo(() => filteredData.some((d) => Boolean(d.time)), [filteredData]);

  // ``toTime`` already returns a numeric UTCTimestamp — compare the numbers
  // directly (re-parsing them through ``toUnix`` would zero them out and
  // drop every bar).
  const asUnix = (t: Time): number => (typeof t === "number" ? t : 0);

  const candles: CandlestickData[] = useMemo(
    () =>
      filteredData
        .map((d) => ({
          time: toTime(d.date || "", d.time),
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }))
        .filter((c) => asUnix(c.time) > 0)
        .sort((a, b) => asUnix(a.time) - asUnix(b.time)),
    [filteredData]
  );

  const volumes: HistogramData[] = useMemo(
    () =>
      filteredData
        .map((d) => ({
          time: toTime(d.date || "", d.time),
          value: d.volume,
          color: d.close >= d.open ? "rgba(0,209,175,0.35)" : "rgba(247,37,133,0.35)",
        }))
        .filter((v) => asUnix(v.time) > 0)
        .sort((a, b) => asUnix(a.time) - asUnix(b.time)),
    [filteredData]
  );

  const closes = useMemo(() => filteredData.map((d) => d.close), [filteredData]);

  // ── Cleanup helper ──────────────────────────────────────────────────────

  const cleanupSubChart = useCallback(() => {
    if (subChartRef.current) {
      subChartRef.current.remove();
      subChartRef.current = null;
    }
    if (subContainerRef.current) {
      subContainerRef.current.remove();
      subContainerRef.current = null;
    }
    subSeriesRef.current = [];
  }, []);

  // ── Create / Rebuild Chart ──────────────────────────────────────────────

  const buildChart = useCallback(() => {
    if (!chartContainerRef.current) return;

    // Cleanup previous
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    cleanupSubChart();
    overlaySeriesRef.current = [];

    const container = chartContainerRef.current;
    const mainHeight = subIndicator !== "none" ? Math.floor(height * 0.7) : height;

    // ── Main Chart ──
    const chart = createChart(container, {
      width: container.clientWidth,
      height: mainHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontFamily: "'Vazirmatn', 'Inter', sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(128,128,128,0.06)" },
        horzLines: { color: "rgba(128,128,128,0.06)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          width: 1,
          color: "rgba(128,128,128,0.4)",
          style: LineStyle.Dashed,
          labelBackgroundColor: "#374151",
        },
        horzLine: {
          width: 1,
          color: "rgba(128,128,128,0.4)",
          style: LineStyle.Dashed,
          labelBackgroundColor: "#374151",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(128,128,128,0.1)",
        scaleMargins: { top: 0.05, bottom: showVolume ? 0.25 : 0.05 },
      },
      timeScale: {
        borderColor: "rgba(128,128,128,0.1)",
        timeVisible: isIntraday,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: isIntraday ? 6 : 8,
        minBarSpacing: 3,
      },
      handleScroll: { vertTouchDrag: false },
    });
    chartRef.current = chart;

    // ── Candlestick Series ──
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00d1af",
      downColor: "#f72585",
      borderUpColor: "#00d1af",
      borderDownColor: "#f72585",
      wickUpColor: "#00d1af",
      wickDownColor: "#f72585",
    });
    candleSeries.setData(candles);
    candleSeriesRef.current = candleSeries;

    // ── Volume Series ──
    if (showVolume) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(volumes);
      volumeSeriesRef.current = volumeSeries;
    }

    // ── Crosshair data ──
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHoverData(null);
        return;
      }
      const cd = param.seriesData.get(candleSeries) as CandlestickData | undefined;
      if (cd) {
        const original = filteredData.find(
          (d) => toUnix(d.date || "", d.time) === asUnix(cd.time as Time)
        );
        setHoverData(original || null);
      }
    });

    // ── Responsive ──
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        chart.applyOptions({ width: w });
      }
    });
    ro.observe(container);
    resizeObserverRef.current = ro;

    chart.timeScale().fitContent();
  }, [candles, volumes, height, showVolume, filteredData, subIndicator, isIntraday, cleanupSubChart]);

  useEffect(() => {
    buildChart();
    return () => {
      resizeObserverRef.current?.disconnect();
      chartRef.current?.remove();
      cleanupSubChart();
    };
  }, [buildChart]);

  // ── Overlay Indicators ──────────────────────────────────────────────────

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !candleSeriesRef.current) return;

    // Remove old overlays
    overlaySeriesRef.current.forEach((s) => {
      try { chart.removeSeries(s); } catch {}
    });
    overlaySeriesRef.current = [];

    if (overlay === "none") return;

    const timeData = candles.map((c) => c.time);

    if (overlay === "SMA") {
      const sma = calcSMA(closes, 20);
      const lineData = sma
        .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
        .filter(Boolean) as LineData[];
      if (lineData.length > 0) {
        const series = chart.addSeries(LineSeries, {
          color: "#3b82f6",
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        series.setData(lineData);
        overlaySeriesRef.current.push(series);
      }
    } else if (overlay === "EMA") {
      const ema = calcEMA(closes, 20);
      const lineData = ema
        .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
        .filter(Boolean) as LineData[];
      if (lineData.length > 0) {
        const series = chart.addSeries(LineSeries, {
          color: "#a855f7",
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        series.setData(lineData);
        overlaySeriesRef.current.push(series);
      }
    } else if (overlay === "BB") {
      const bb = calcBB(closes, 20, 2);
      const colors = ["#f59e0b", "#f59e0b", "#f59e0b"];
      const widths: Array<1 | 2 | 3 | 4> = [1, 2, 1];
      const styles = [LineStyle.Dashed, LineStyle.Solid, LineStyle.Dashed];
      const bbLines = [bb.upper, bb.middle, bb.lower];
      for (let k = 0; k < 3; k++) {
        const ld = bbLines[k]
          .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
          .filter(Boolean) as LineData[];
        if (ld.length > 0) {
          const series = chart.addSeries(LineSeries, {
            color: colors[k],
            lineWidth: widths[k],
            lineStyle: styles[k],
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          series.setData(ld);
          overlaySeriesRef.current.push(series);
        }
      }
    }
  }, [overlay, candles, closes]);

  // ── Sub Indicators (RSI / MACD) ────────────────────────────────────────

  useEffect(() => {
    if (subIndicator === "none") return;
    if (!chartContainerRef.current) return;

    const subContainer = document.createElement("div");
    subContainer.style.height = `${Math.floor(height * 0.28)}px`;
    subContainer.style.marginTop = "4px";
    chartContainerRef.current.parentElement?.appendChild(subContainer);
    subContainerRef.current = subContainer;

    const subChart = createChart(subContainer, {
      width: chartContainerRef.current.clientWidth,
      height: Math.floor(height * 0.28),
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontFamily: "'Vazirmatn', 'Inter', sans-serif",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(128,128,128,0.04)" },
        horzLines: { color: "rgba(128,128,128,0.04)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "rgba(128,128,128,0.1)" },
      timeScale: {
        borderColor: "rgba(128,128,128,0.1)",
        visible: true,
        timeVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    // Sync time scale with main chart
    if (chartRef.current) {
      subChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) chartRef.current?.timeScale().setVisibleLogicalRange(range);
      });
      chartRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range) subChart.timeScale().setVisibleLogicalRange(range);
      });
    }

    subChartRef.current = subChart;

    const timeData = candles.map((c) => c.time);

    if (subIndicator === "RSI") {
      const rsi = calcRSI(closes, 14);
      const series = subChart.addSeries(LineSeries, {
        color: "#a855f7",
        lineWidth: 2,
        priceLineVisible: false,
      });
      const rsiData = rsi
        .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
        .filter(Boolean) as LineData[];
      series.setData(rsiData);

      // Overbought / Oversold lines
      if (timeData.length >= 2) {
        const obLine = subChart.addSeries(LineSeries, {
          color: "rgba(247,37,133,0.4)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        obLine.setData([
          { time: timeData[0], value: 70 },
          { time: timeData[timeData.length - 1], value: 70 },
        ]);

        const osLine = subChart.addSeries(LineSeries, {
          color: "rgba(0,209,175,0.4)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        osLine.setData([
          { time: timeData[0], value: 30 },
          { time: timeData[timeData.length - 1], value: 30 },
        ]);

        subSeriesRef.current = [series, obLine, osLine];
      } else {
        subSeriesRef.current = [series];
      }
    } else if (subIndicator === "MACD") {
      const macd = calcMACD(closes);
      const macdLineSeries = subChart.addSeries(LineSeries, {
        color: "#3b82f6",
        lineWidth: 2,
        priceLineVisible: false,
      });
      const signalLineSeries = subChart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
        priceLineVisible: false,
      });
      const histSeries = subChart.addSeries(HistogramSeries, {
        priceLineVisible: false,
      });

      const macdData = macd.macd
        .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
        .filter(Boolean) as LineData[];
      const signalData = macd.signal
        .map((v, i) => (v !== null ? { time: timeData[i], value: v } : null))
        .filter(Boolean) as LineData[];
      const histData = macd.histogram
        .map((v, i) =>
          v !== null
            ? { time: timeData[i], value: v, color: v >= 0 ? "rgba(0,209,175,0.6)" : "rgba(247,37,133,0.6)" }
            : null
        )
        .filter(Boolean) as HistogramData[];

      macdLineSeries.setData(macdData);
      signalLineSeries.setData(signalData);
      histSeries.setData(histData);
      subSeriesRef.current = [macdLineSeries, signalLineSeries, histSeries];
    }

    subChart.timeScale().fitContent();

    return () => {
      cleanupSubChart();
    };
  }, [subIndicator, candles, closes, height, cleanupSubChart]);

  // ── Helpers ─────────────────────────────────────────────────────────────

  const fmt = (v: number) => v.toLocaleString("fa-IR");
  const pct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  const lastPrice = filteredData.length > 0 ? filteredData[filteredData.length - 1].close : 0;
  const firstPrice = filteredData.length > 0 ? filteredData[0].close : 1;
  const changePct = ((lastPrice - firstPrice) / firstPrice) * 100;
  const highAll = filteredData.length > 0 ? Math.max(...filteredData.map((d) => d.high)) : 0;
  const lowAll = filteredData.length > 0 ? Math.min(...filteredData.map((d) => d.low)) : 0;
  const volAll = filteredData.reduce((s, d) => s + d.volume, 0);

  // ── Render ──────────────────────────────────────────────────────────────

  const TF_LABELS: Record<Timeframe, string> = {
    "1D": "۱ روز",
    "1W": "۱ هفته",
    "1M": "۱ ماه",
    "3M": "۳ ماه",
    "6M": "۶ ماه",
    "1Y": "۱ سال",
    ALL: "همه",
  };

  return (
    <Card
      title={title}
      actions={
        <div className="flex items-center gap-2 flex-wrap">
          {(Object.keys(TF_LABELS) as Timeframe[]).map((tf) => (
            <CardAction key={tf} active={timeframe === tf} onClick={() => setTimeframe(tf)}>
              {TF_LABELS[tf]}
            </CardAction>
          ))}
        </div>
      }
    >
      {/* ── Stats Bar ── */}
      <div className="flex flex-wrap items-center gap-4 mb-3 pb-3" style={{ borderBottom: "1px solid var(--glass-border)" }}>
        {symbol && (
          <div className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
            {symbol}{" "}
            <span className="font-bold" style={{ color: "var(--text-primary-light)", fontFamily: "Inter" }}>
              {fmt(lastPrice)}
            </span>
            <span
              className="mr-2 font-bold"
              style={{ color: changePct >= 0 ? "var(--positive)" : "var(--negative)", fontFamily: "Inter" }}
            >
              {pct(changePct)}
            </span>
          </div>
        )}
        <div className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
          بیشترین <span style={{ color: "var(--positive)", fontFamily: "Inter" }}>{fmt(highAll)}</span>
        </div>
        <div className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
          کمترین <span style={{ color: "var(--negative)", fontFamily: "Inter" }}>{fmt(lowAll)}</span>
        </div>
        <div className="text-xs" style={{ color: "var(--text-secondary-light)" }}>
          حجم <span style={{ color: "var(--text-primary-light)", fontFamily: "Inter" }}>{(volAll / 1e6).toFixed(1)}M</span>
        </div>

        {/* Crosshair data */}
        {hoverData && (
          <div className="flex gap-3 mr-auto text-xs font-mono" style={{ direction: "ltr" }}>
            <span style={{ color: "var(--text-secondary-light)" }}>O <span style={{ color: "var(--text-primary-light)" }}>{fmt(hoverData.open)}</span></span>
            <span style={{ color: "var(--text-secondary-light)" }}>H <span style={{ color: "var(--positive)" }}>{fmt(hoverData.high)}</span></span>
            <span style={{ color: "var(--text-secondary-light)" }}>L <span style={{ color: "var(--negative)" }}>{fmt(hoverData.low)}</span></span>
            <span style={{ color: "var(--text-secondary-light)" }}>C <span style={{ color: "var(--text-primary-light)" }}>{fmt(hoverData.close)}</span></span>
            <span style={{ color: "var(--text-secondary-light)" }}>V <span style={{ color: "var(--text-primary-light)" }}>{fmt(hoverData.volume)}</span></span>
          </div>
        )}
      </div>

      {/* ── Indicator Toolbar ── */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <span className="text-xs" style={{ color: "var(--text-secondary-light)" }}>اندیکاتور روی نمودار:</span>
        {(["none", "SMA", "EMA", "BB"] as OverlayIndicator[]).map((ind) => (
          <button
            key={ind}
            onClick={() => setOverlay(ind)}
            className="text-xs px-2.5 py-1 rounded-md transition-all"
            style={{
              background: overlay === ind ? "var(--accent-primary)" : "var(--bg-surface)",
              color: overlay === ind ? "#fff" : "var(--text-secondary-light)",
            }}
          >
            {ind === "none" ? "بدون" : ind === "SMA" ? "SMA (20)" : ind === "EMA" ? "EMA (20)" : "Bollinger"}
          </button>
        ))}

        <span className="text-xs mr-3" style={{ color: "var(--text-secondary-light)" }}>پنل جدا:</span>
        {(["none", "RSI", "MACD"] as SubIndicator[]).map((ind) => (
          <button
            key={ind}
            onClick={() => setSubIndicator(ind)}
            className="text-xs px-2.5 py-1 rounded-md transition-all"
            style={{
              background: subIndicator === ind ? "var(--accent-secondary)" : "var(--bg-surface)",
              color: subIndicator === ind ? "#fff" : "var(--text-secondary-light)",
            }}
          >
            {ind === "none" ? "بدون" : ind}
          </button>
        ))}
      </div>

      {/* ── Chart Container ── */}
      <div ref={chartContainerRef} style={{ width: "100%" }} />
    </Card>
  );
}
