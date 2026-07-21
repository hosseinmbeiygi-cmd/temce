"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";

const CandleChartCard = dynamic(() => import("@/components/charts/TradingViewChart"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 400 }} />,
});

// Format ریال to میلیارد تومان
function fmtToman(rials: number): string {
  const toman = rials / 10;  // 1 تومان = 10 ریال
  if (toman >= 1_000_000) return (toman / 1_000_000).toFixed(1) + " همت";
  if (toman >= 1_000) return (toman / 1_000).toFixed(1) + " م.ت";
  return toman.toFixed(1) + " م.ت";
}


interface SentimentItem {
  date: string;
  score: number;
  label: string;
  volume: number;
}

interface Recommendation {
  symbol: string;
  name: string;
  signal: "buy" | "hold" | "sell";
  targetPrice: number;
  currentPrice: number;
  upside: number;
  analyst: string;
}

interface AnalysisTrends {
  trend: string;
  strength: number;
  gainers: { symbol: string; change: number }[];
  losers: { symbol: string; change: number }[];
}

interface AnalysisData {
  sentiment: SentimentItem[];
  trends: AnalysisTrends;
  recommendations: Recommendation[];
}

interface ElliotWaveData {
  symbol: string;
  wave_count: number;
  current_wave: number;
  waves: { wave: number; type: string; start: number | null; end: number | null; percent: number | null; current?: boolean; projected?: boolean }[];
  fibonacci_levels: Record<string, number>;
  target_price: number;
  stop_loss: number;
  pattern: string;
  analysis: string;
}

interface LiquidityData {
  date: string;
  total_trade_value: number;
  total_trade_volume: number;
  total_inflow: number;
  total_outflow: number;
  net_flow: number;
  institutional_flow: number;
  retail_flow: number;
  top_inflow_sectors: { sector: string; inflow: number; symbols: string[] }[];
  top_outflow_sectors: { sector: string; outflow: number; symbols: string[] }[];
  money_flow_index: number;
  interpretation: string;
}

interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface IndicatorResponse {
  values: number[] | Record<string, number[]>;
}

type AnalysisTab = "sentiment" | "trends" | "recommendations" | "elliot" | "liquidity" | "technical";

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: "sentiment", label: "تحلیل احساسات" },
  { key: "trends", label: "روندها" },
  { key: "recommendations", label: "توصیه‌ها" },
  { key: "technical", label: "تحلیل تکنیکال" },
  { key: "elliot", label: "امواج الیوت" },
  { key: "liquidity", label: "نقدینگی" },
];

// ------ Technical Analysis Constants (default symbol) ------
const TECH_SYMBOL = "فخاس";  // فولاد خراسان - has data in DB

function TrendIndicator({ value }: { value: number }) {
  const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="w-32 h-2 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{
          width: `${safeValue}%`,
          background: safeValue >= 60 ? "#22c55e" : safeValue >= 40 ? "#f59e0b" : "#ef4444"
        }} />
      </div>
      <span className={`text-xs font-mono ${safeValue >= 60 ? "text-accent-emerald" : safeValue >= 40 ? "text-accent-amber" : "text-accent-rose"}`}>
        {safeValue}%
      </span>
    </div>
  );
}

export default function AnalysisPage() {
  const [tab, setTab] = useState<AnalysisTab>("sentiment");


  const { data: analysis, isLoading } = useQuery({
    queryKey: ["analysis-full"],
    queryFn: async () => {
      try {
        return await apiGet<AnalysisData>("/analysis/overview");
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
  });

  const avgSentiment = analysis?.sentiment?.length
    ? (analysis.sentiment.reduce((sum: number, s: SentimentItem) => sum + (Number(s.score) || 0), 0) / analysis.sentiment.length).toFixed(0)
    : null;

  // ── Real OHLCV data for Technical Analysis ──
  const { data: ohlcvBars, isLoading: loadingOhlcv } = useQuery({
    queryKey: ["analysis-ohlcv", TECH_SYMBOL],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: OHLCVBar[] }>(
          `/market/history/${encodeURIComponent(TECH_SYMBOL)}?limit=60`
        );
        if (res?.success && Array.isArray(res.data)) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  // ── Real Technical Indicators ──
  const { data: rsiData } = useQuery({
    queryKey: ["analysis-rsi", TECH_SYMBOL],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: IndicatorResponse }>(
          `/market/indicator/${encodeURIComponent(TECH_SYMBOL)}?indicator=rsi&period=14`
        );
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  const { data: macdData } = useQuery({
    queryKey: ["analysis-macd", TECH_SYMBOL],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: IndicatorResponse }>(
          `/market/indicator/${encodeURIComponent(TECH_SYMBOL)}?indicator=macd&fast=12&slow=26&signal=9`
        );
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  const { data: smaData } = useQuery({
    queryKey: ["analysis-sma", TECH_SYMBOL],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: IndicatorResponse }>(
          `/market/indicator/${encodeURIComponent(TECH_SYMBOL)}?indicator=sma&period=50`
        );
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  // Map OHLCV data to CandleChartCard format
  const CANDLE_DATA = useMemo(() => {
    if (ohlcvBars && ohlcvBars.length > 0) {
      return ohlcvBars.map((bar) => ({
        date: bar.date,
        time: bar.date,
        open: bar.open || bar.close,
        high: bar.high || bar.close,
        low: bar.low || bar.close,
        close: bar.close || 0,
        volume: bar.volume || 0,
        isUp: (bar.close || 0) >= (bar.open || 0),
      }));
    }
    return [];
  }, [ohlcvBars]);

  // Extract indicator last values
  const rsiValue = useMemo(() => {
    const v = rsiData?.values;
    if (Array.isArray(v) && v.length > 0) return v[v.length - 1];
    return null;
  }, [rsiData]);

  const macdValue = useMemo(() => {
    const v = macdData?.values;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const m = (v as Record<string, number[]>).macd;
      const s = (v as Record<string, number[]>).signal;
      if (m?.length && s?.length) {
        const lastM = m[m.length - 1];
        const lastS = s[s.length - 1];
        return { value: lastM, signal: lastS, diff: lastM - lastS };
      }
    }
    return null;
  }, [macdData]);

  const smaValue = useMemo(() => {
    const v = smaData?.values;
    if (Array.isArray(v) && v.length > 0) return Math.round(v[v.length - 1]);
    return null;
  }, [smaData]);

  // ── Elliot Wave Data ──
  const { data: elliotData, isLoading: loadingElliot } = useQuery({
    queryKey: ["analysis-elliot", TECH_SYMBOL],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: ElliotWaveData }>(
          `/analysis/elliot-waves/${encodeURIComponent(TECH_SYMBOL)}`
        );
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  // ── Liquidity Data ──
  const { data: liquidityData, isLoading: loadingLiquidity } = useQuery({
    queryKey: ["analysis-liquidity"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: LiquidityData }>("/analysis/liquidity");
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 600_000,
    staleTime: 60_000,
  });

  return (
    <AppLayout title="تحلیل بازار" subtitle="تحلیل‌های تکنیکال، فاندامنتال و احساسات بازار">
      <div className="flex gap-2 mb-6 flex-wrap">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === t.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}>{t.label}</button>
        ))}
      </div>

      {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full rounded-2xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        ) : (
          <>
            {tab === "sentiment" && (
              <div className="space-y-4">
                <div className="glass-card p-5">
                  <h2 className="font-bold text-surface-200 mb-4">شاخص احساسات بازار</h2>
                  <div className="flex items-center gap-6 mb-4">
                    <div className="text-center">
                      <div className={`text-3xl font-black ${
                        avgSentiment === null ? "text-surface-600" :
                        Number(avgSentiment) >= 60 ? "text-accent-emerald" : Number(avgSentiment) >= 40 ? "text-accent-amber" : "text-accent-rose"
                      }`}>{avgSentiment !== null ? `${avgSentiment}%` : "—"}</div>
                      <div className="text-xs text-surface-500 mt-1">میانگین ۷ روزه</div>
                    </div>
                    <div className="flex-1">
                      {avgSentiment !== null ? (
                        <TrendIndicator value={Number(avgSentiment)} />
                      ) : (
                        <div className="w-full h-2 bg-surface-700 rounded-full" />
                      )}
                      <div className="flex justify-between text-xs text-surface-600 mt-1">
                        <span>منفی</span><span>خنثی</span><span>مثبت</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="glass-card p-5">
                  <h2 className="font-bold text-surface-200 mb-4">روند احساسات</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-right text-sm">
                      <thead>
                        <tr className="text-surface-500 border-b border-surface-700">
                          <th className="pb-2 font-medium">تاریخ</th>
                          <th className="pb-2 font-medium">امتیاز</th>
                          <th className="pb-2 font-medium">وضعیت</th>
                          <th className="pb-2 font-medium">حجم معاملات</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis?.sentiment?.map((s: SentimentItem, i: number) => (
                          <tr key={i} className="border-b border-surface-800/50">
                            <td className="py-2.5 text-surface-400 text-xs">{formatDateShamsi(s.date)}</td>
                            <td className="py-2.5"><TrendIndicator value={Number(s.score) || 0} /></td>
                            <td className="py-2.5">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                s.label === "مثبت" ? "bg-accent-emerald/15 text-accent-emerald" :
                                s.label === "منفی" ? "bg-accent-rose/15 text-accent-rose" :
                                "bg-accent-amber/15 text-accent-amber"
                              }`}>{s.label || "خنثی"}</span>
                            </td>
                            <td className="py-2.5 font-mono text-surface-200 text-xs">{(s.volume || 0).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {tab === "trends" && (
              <div className="grid md:grid-cols-3 gap-4">
                <div className="glass-card p-5 col-span-2">
                  <h2 className="font-bold text-surface-200 mb-4">تحلیل روند بازار</h2>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 px-3 bg-surface-800/50 rounded-lg">
                      <span className="text-sm text-surface-300">نشانگر</span>
                      <span className="text-sm text-surface-300">مقدار</span>
                    </div>
                    <div className="flex items-center justify-between py-2 px-3">
                      <span className="text-sm text-surface-400">روند کلی</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        analysis?.trends?.trend === "bullish" ? "bg-accent-emerald/15 text-accent-emerald" :
                        analysis?.trends?.trend === "bearish" ? "bg-accent-rose/15 text-accent-rose" :
                        "bg-accent-amber/15 text-accent-amber"
                      }`}>{analysis?.trends?.trend === "bullish" ? "صعودی" : analysis?.trends?.trend === "bearish" ? "نزولی" : "خنثی"}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 px-3">
                      <span className="text-sm text-surface-400">قدرت روند</span>
                      <TrendIndicator value={analysis?.trends?.strength || 0} />
                    </div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="glass-card p-5">
                    <h3 className="font-bold text-accent-emerald mb-3">پررشدترین‌ها</h3>
                    <div className="space-y-2">
                      {analysis?.trends?.gainers?.map((g: { symbol: string; change: number }, i: number) => (
                        <div key={`${g.symbol}-${i}`} className="flex items-center justify-between">
                          <span className="text-sm text-surface-200">{g.symbol}</span>
                          <span className="text-sm font-mono text-accent-emerald">+{g.change.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="glass-card p-5">
                    <h3 className="font-bold text-accent-rose mb-3">پربازده‌ترین‌ها</h3>
                    <div className="space-y-2">
                      {analysis?.trends?.losers?.map((l: { symbol: string; change: number }, i: number) => (
                        <div key={`${l.symbol}-${i}`} className="flex items-center justify-between">
                          <span className="text-sm text-surface-200">{l.symbol}</span>
                          <span className="text-sm font-mono text-accent-rose">{l.change.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "recommendations" && (
              <div className="glass-card p-5">
                <h2 className="font-bold text-surface-200 mb-4">توصیه‌های تحلیلی</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-right text-sm">
                    <thead>
                      <tr className="text-surface-500 border-b border-surface-700">
                        <th className="pb-2 font-medium">نماد</th>
                        <th className="pb-2 font-medium">نام</th>
                        <th className="pb-2 font-medium">توصیه</th>
                        <th className="pb-2 font-medium">قیمت فعلی</th>
                        <th className="pb-2 font-medium">قیمت هدف</th>
                        <th className="pb-2 font-medium">پتانسیل</th>
                        <th className="pb-2 font-medium">تحلیلگر</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis?.recommendations?.map((r: Recommendation, i: number) => (
                        <tr key={i} className="border-b border-surface-800/50">
                          <td className="py-2.5 font-mono font-bold text-surface-200">{r.symbol}</td>
                          <td className="py-2.5 text-surface-400 text-xs">{r.name}</td>
                          <td className="py-2.5">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              r.signal === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                              r.signal === "sell" ? "bg-accent-rose/15 text-accent-rose" :
                              "bg-accent-amber/15 text-accent-amber"
                            }`}>{r.signal === "buy" ? "خرید" : r.signal === "sell" ? "فروش" : "نگهداری"}</span>
                          </td>
                          <td className="py-2.5 font-mono text-surface-200">{r.currentPrice?.toLocaleString("fa-IR")}</td>
                          <td className="py-2.5 font-mono text-surface-200">{r.targetPrice?.toLocaleString("fa-IR")}</td>
                          <td className={`py-2.5 font-mono ${r.upside >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {r.upside >= 0 ? "+" : ""}{r.upside.toFixed(1)}%
                          </td>
                          <td className="py-2.5 text-surface-400 text-xs">{r.analyst}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {tab === "technical" && (
              <div className="space-y-4">
                {/* Candlestick Chart */}
                {loadingOhlcv ? (
                  <Skeleton className="h-[400px] w-full rounded-2xl" />
                ) : CANDLE_DATA.length > 0 ? (
                  <CandleChartCard
                    title={"تحلیل تکنیکال - " + TECH_SYMBOL}
                    data={CANDLE_DATA}
                    symbol={TECH_SYMBOL}
                    height={400}
                    showVolume={true}
                  />
                ) : (
                  <div className="glass-card p-8 text-center text-surface-500">
                    <p className="text-4xl mb-3">📈</p>
                    <p>داده‌ای از جدول quotes برای {TECH_SYMBOL} یافت نشد</p>
                    <p className="text-xs mt-1">لطفاً یک نماد معتبر با داده تاریخی انتخاب کنید</p>
                  </div>
                )}

                {/* Technical Indicators Summary */}
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* RSI */}
                  <div className="glass-card p-4">
                    <div className="text-xs text-surface-500 mb-1">RSI (14)</div>
                    <div className={`text-lg font-bold font-mono ${
                      rsiValue != null
                        ? rsiValue > 70 ? "text-accent-rose" : rsiValue < 30 ? "text-accent-emerald" : "text-surface-200"
                        : "text-surface-600"
                    }`}>{rsiValue != null ? rsiValue.toFixed(1) : "—"}</div>
                    <div className="text-xs mt-0.5" style={{
                      color: rsiValue != null
                        ? rsiValue > 70 ? "var(--negative)" : rsiValue < 30 ? "var(--positive)" : "var(--neutral)"
                        : "var(--neutral)"
                    }}>
                      {rsiValue != null
                        ? rsiValue > 70 ? "اشباع خرید 📈" : rsiValue < 30 ? "اشباع فروش 📉" : "خنثی"
                        : "—"}
                    </div>
                  </div>
                  {/* MACD */}
                  <div className="glass-card p-4">
                    <div className="text-xs text-surface-500 mb-1">MACD (12,26,9)</div>
                    <div className={`text-lg font-bold font-mono ${
                      macdValue != null
                        ? macdValue.diff > 0 ? "text-accent-emerald" : "text-accent-rose"
                        : "text-surface-600"
                    }`}>{macdValue != null ? macdValue.value.toFixed(1) : "—"}</div>
                    <div className="text-xs mt-0.5" style={{
                      color: macdValue != null
                        ? macdValue.diff > 0 ? "var(--positive)" : "var(--negative)"
                        : "var(--neutral)"
                    }}>
                      {macdValue != null
                        ? macdValue.diff > 0 ? "سیگنال خرید ✅" : "سیگنال فروش ❌"
                        : "—"}
                    </div>
                  </div>
                  {/* MA (50) */}
                  <div className="glass-card p-4">
                    <div className="text-xs text-surface-500 mb-1">SMA (50)</div>
                    <div className={`text-lg font-bold font-mono ${smaValue != null ? "text-surface-200" : "text-surface-600"}`}>
                      {smaValue != null ? smaValue.toLocaleString() : "—"}
                    </div>
                    <div className="text-xs mt-0.5 text-surface-500">
                      {smaValue != null
                        ? (ohlcvBars?.[ohlcvBars.length - 1]?.close ?? 0) > smaValue
                          ? "قیمت بالاتر از میانگین ⬆️"
                          : "قیمت پایین‌تر از میانگین ⬇️"
                        : "—"}
                    </div>
                  </div>
                  {/* Volume */}
                  <div className="glass-card p-4">
                    <div className="text-xs text-surface-500 mb-1"> حجم آخرین روز</div>
                    <div className={`text-lg font-bold font-mono ${
                      ohlcvBars && ohlcvBars.length > 0 ? "text-surface-200" : "text-surface-600"
                    }`}>
                      {ohlcvBars && ohlcvBars.length > 0
                        ? ohlcvBars[ohlcvBars.length - 1]?.volume?.toLocaleString() ?? "—"
                        : "—"}
                    </div>
                    <div className="text-xs mt-0.5 text-surface-500">
                      {ohlcvBars && ohlcvBars.length > 2
                        ? (() => {
                            const last = ohlcvBars[ohlcvBars.length - 1]?.volume || 0;
                            const prev = ohlcvBars[ohlcvBars.length - 2]?.volume || 1;
                            const chg = ((last - prev) / prev) * 100;
                            return (chg >= 0 ? "⬆️" : "⬇️") + " " + Math.abs(chg).toFixed(0) + "% نسبت به روز قبل";
                          })()
                        : "—"}
                    </div>
                  </div>
                </div>

                {/* Pattern Detection */}
                <div className="glass-card p-5">
                  <h3 className="font-bold text-surface-200 mb-3">تحلیل بر اساس داده‌های لحظه‌ای</h3>
                  <div className="space-y-2">
                    {ohlcvBars && ohlcvBars.length > 5 ? (
                      (() => {
                        const last5 = ohlcvBars.slice(-5);
                        const avgVol = last5.reduce((s, b) => s + (b.volume || 0), 0) / 5;
                        const lastVol = last5[last5.length - 1]?.volume || 0;
                        const volChange = ((lastVol - avgVol) / Math.max(avgVol, 1)) * 100;
                        const lastClose = last5[last5.length - 1]?.close || 0;
                        const prevClose = last5[last5.length - 2]?.close || lastClose;
                        const priceChange = ((lastClose - prevClose) / Math.max(prevClose, 1)) * 100;

                        return (
                          <>
                            <div className="flex items-start gap-3 p-3 bg-surface-800/30 rounded-lg">
                              <span className="w-2 h-2 rounded-full mt-1.5" style={{ background: priceChange > 0 ? "var(--positive)" : "var(--negative)" }} />
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-surface-200 text-sm">روند قیمت</span>
                                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${priceChange > 0 ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"}`}>
                                    {priceChange > 0 ? "صعودی" : "نزولی"}
                                  </span>
                                </div>
                                <p className="text-xs text-surface-500 mt-1">تغییر قیمت: {priceChange > 0 ? "+" : ""}{priceChange.toFixed(2)}%</p>
                              </div>
                            </div>
                            <div className="flex items-start gap-3 p-3 bg-surface-800/30 rounded-lg">
                              <span className="w-2 h-2 rounded-full mt-1.5" style={{ background: volChange > 20 ? "var(--positive)" : volChange < -20 ? "var(--negative)" : "var(--neutral)" }} />
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-surface-200 text-sm">حجم معاملات</span>
                                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${volChange > 20 ? "bg-accent-emerald/15 text-accent-emerald" : volChange < -20 ? "bg-accent-rose/15 text-accent-rose" : "bg-accent-amber/15 text-accent-amber"}`}>
                                    {volChange > 20 ? "افزایش" : volChange < -20 ? "کاهش" : "عادی"}
                                  </span>
                                </div>
                                <p className="text-xs text-surface-500 mt-1">تغییر حجم: {volChange > 0 ? "+" : ""}{volChange.toFixed(0)}% نسبت به میانگین</p>
                              </div>
                            </div>
                          </>
                        );
                      })()
                    ) : (
                      <p className="text-xs text-surface-500 text-center py-4">داده کافی برای تحلیل موجود نیست</p>
                    )}
                  </div>
                </div>
              </div>
            )}
            {tab === "elliot" && (
              <div className="space-y-4">
                {loadingElliot ? (
                  <Skeleton className="h-64 w-full rounded-2xl" />
                ) : elliotData ? (
                  <>
                    <div className="glass-card p-5">
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="font-bold text-surface-200">امواج الیوت — {elliotData.symbol}</h2>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-primary-600/15 text-primary-300">{elliotData.pattern}</span>
                      </div>
                      <p className="text-sm text-surface-400 mb-4">{elliotData.analysis}</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">تعداد امواج</div>
                          <div className="text-lg font-bold text-surface-200">{elliotData.wave_count}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">موج فعلی</div>
                          <div className="text-lg font-bold text-primary-400">{elliotData.current_wave}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">قیمت هدف</div>
                          <div className="text-lg font-bold text-accent-emerald">{elliotData.target_price.toLocaleString()}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">حد ضرر</div>
                          <div className="text-lg font-bold text-accent-rose">{elliotData.stop_loss.toLocaleString()}</div>
                        </div>
                      </div>
                    </div>

                    <div className="glass-card p-5">
                      <h3 className="font-bold text-surface-200 mb-3">جزئیات امواج</h3>
                      <div className="space-y-2">
                        {elliotData.waves.map((w) => (
                          <div key={w.wave} className={`flex items-center gap-3 p-3 rounded-lg ${w.current ? "bg-primary-600/10 border border-primary-600/20" : w.projected ? "bg-surface-800/30 border border-surface-700/50 border-dashed" : "bg-surface-800/30"}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${w.type === "impulse" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-amber/15 text-accent-amber"}`}>
                              {w.wave}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-surface-200">موج {w.wave}</span>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${w.type === "impulse" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-amber/15 text-accent-amber"}`}>
                                  {w.type === "impulse" ? "حرکتی" : "اصلاحی"}
                                </span>
                                {w.current && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary-600/15 text-primary-300">فعلی</span>}
                                {w.projected && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-600/30 text-surface-400">پیش‌بینی</span>}
                              </div>
                              <div className="text-xs text-surface-500 mt-0.5">
                                {w.start != null ? w.start.toLocaleString() : "—"} → {w.end != null ? w.end.toLocaleString() : "—"}
                                {w.percent != null && <span className={w.percent >= 0 ? "text-accent-emerald" : "text-accent-rose"}> ({w.percent > 0 ? "+" : ""}{w.percent}%)</span>}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="glass-card p-5">
                      <h3 className="font-bold text-surface-200 mb-3">سطوح فیبوناچی</h3>
                      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                        {Object.entries(elliotData.fibonacci_levels).map(([level, price]) => (
                          <div key={level} className="bg-surface-800/50 rounded-lg p-2.5 text-center">
                            <div className="text-[10px] text-surface-500">{level}</div>
                            <div className="text-sm font-mono font-bold text-surface-200">{price.toLocaleString()}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="glass-card p-12 text-center text-surface-500">
                    <p className="text-4xl mb-3">🌊</p>
                    <p>داده‌ای برای امواج الیوت یافت نشد</p>
                  </div>
                )}
              </div>
            )}

            {tab === "liquidity" && (
              <div className="space-y-4">
                {loadingLiquidity ? (
                  <Skeleton className="h-64 w-full rounded-2xl" />
                ) : liquidityData ? (
                  <>
                    <div className="glass-card p-5">
                      <h2 className="font-bold text-surface-200 mb-4">تحلیل نقدینگی بازار</h2>
                      <p className="text-sm text-surface-400 mb-4">{liquidityData.interpretation}</p>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">ارزش کل معاملات</div>
                          <div className="text-lg font-bold text-surface-200">{fmtToman(liquidityData.total_trade_value)}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">ورود پول</div>
                          <div className="text-lg font-bold text-accent-emerald">+{fmtToman(liquidityData.total_inflow)}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">خروج پول</div>
                          <div className="text-lg font-bold text-accent-rose">-{fmtToman(liquidityData.total_outflow)}</div>
                        </div>
                        <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                          <div className="text-xs text-surface-500">خالص جریان</div>
                          <div className={`text-lg font-bold ${liquidityData.net_flow >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {liquidityData.net_flow >= 0 ? "+" : ""}{fmtToman(liquidityData.net_flow)}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="glass-card p-5">
                        <h3 className="font-bold text-accent-emerald mb-3">بیشترین ورود پول</h3>
                        <div className="space-y-3">
                          {liquidityData.top_inflow_sectors.map((s) => (
                            <div key={s.sector} className="bg-surface-800/30 rounded-lg p-3">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-surface-200">{s.sector}</span>
                                <span className="text-xs font-mono text-accent-emerald">+{fmtToman(s.inflow)}</span>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {s.symbols.map((sym) => (
                                  <span key={sym} className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-emerald/10 text-accent-emerald">{sym}</span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="glass-card p-5">
                        <h3 className="font-bold text-accent-rose mb-3">بیشترین خروج پول</h3>
                        <div className="space-y-3">
                          {liquidityData.top_outflow_sectors.map((s) => (
                            <div key={s.sector} className="bg-surface-800/30 rounded-lg p-3">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-surface-200">{s.sector}</span>
                                <span className="text-xs font-mono text-accent-rose">-{fmtToman(s.outflow)}</span>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {s.symbols.map((sym) => (
                                  <span key={sym} className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-rose/10 text-accent-rose">{sym}</span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="glass-card p-5">
                      <h3 className="font-bold text-surface-200 mb-3">شاخص جریان پول</h3>
                      <div className="flex items-center gap-4">
                        <div className="text-3xl font-black font-mono text-surface-100">{liquidityData.money_flow_index}</div>
                        <div className="flex-1">
                          <div className="w-full h-3 bg-surface-700 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${Math.min(100, liquidityData.money_flow_index)}%`,
                                background: liquidityData.money_flow_index >= 60 ? "#22c55e" : liquidityData.money_flow_index >= 40 ? "#f59e0b" : "#ef4444"
                              }}
                            />
                          </div>
                          <div className="flex justify-between text-xs text-surface-600 mt-1">
                            <span>فروش</span><span>خنثی</span><span>خرید</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="glass-card p-12 text-center text-surface-500">
                    <p className="text-4xl mb-3">💧</p>
                    <p>داده‌ای برای نقدینگی یافت نشد</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
    </AppLayout>
  );
}
