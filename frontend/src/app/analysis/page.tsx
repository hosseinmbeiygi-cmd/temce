"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { generateCandleData } from "@/lib/types";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

const CandleChartCard = dynamic(() => import("@/components/charts/CandleChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 400 }} />,
});


interface SentimentItem {
  date: string;
  score: number;
  label: string;
  volume: number;
}

interface TrendData {
  symbol: string;
  name: string;
  trend: "bullish" | "bearish" | "neutral";
  strength: number;
  gainers: { symbol: string; change: number }[];
  losers: { symbol: string; change: number }[];
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

interface ElliotWave {
  wave: number;
  label: string;
  status: "completed" | "in-progress" | "projected";
  priceRange: string;
}

interface LiquidityFlow {
  symbol: string;
  inflow: number;
  outflow: number;
  net: number;
  direction: "positive" | "negative" | "neutral";
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

function TrendIndicator({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-32 h-2 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{
          width: `${Math.abs(value)}%`,
          background: value >= 60 ? "#22c55e" : value >= 40 ? "#f59e0b" : "#ef4444"
        }} />
      </div>
      <span className={`text-xs font-mono ${value >= 60 ? "text-accent-emerald" : value >= 40 ? "text-accent-amber" : "text-accent-rose"}`}>
        {value}%
      </span>
    </div>
  );
}

export default function AnalysisPage() {
  const [tab, setTab] = useState<AnalysisTab>("sentiment");
  const [elliotSymbol, setElliotSymbol] = useState("شاخص کل");

  const { data: analysis, isLoading } = useQuery({
    queryKey: ["analysis-full"],
    queryFn: async () => {
      try {
        return await apiGet<any>("/analysis/overview");
      } catch {}
      return null;
    },
    refetchInterval: 60000,
  });

  const avgSentiment = analysis?.sentiment?.length
    ? (analysis.sentiment.reduce((sum: number, s: any) => sum + s.score, 0) / analysis.sentiment.length).toFixed(0)
    : "—";

  const CANDLE_DATA = useMemo(() => generateCandleData(60), []);

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
                        Number(avgSentiment) >= 60 ? "text-accent-emerald" : Number(avgSentiment) >= 40 ? "text-accent-amber" : "text-accent-rose"
                      }`}>{avgSentiment}%</div>
                      <div className="text-xs text-surface-500 mt-1">میانگین ۷ روزه</div>
                    </div>
                    <div className="flex-1">
                      <TrendIndicator value={Number(avgSentiment)} />
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
                        {analysis?.sentiment?.map((s: any, i: number) => (
                          <tr key={i} className="border-b border-surface-800/50">
                            <td className="py-2.5 text-surface-400 text-xs">{s.date}</td>
                            <td className="py-2.5"><TrendIndicator value={s.score} /></td>
                            <td className="py-2.5">
                              <span className={`text-xs px-2 py-0.5 rounded-full ${
                                s.label === "مثبت" ? "bg-accent-emerald/15 text-accent-emerald" :
                                s.label === "منفی" ? "bg-accent-rose/15 text-accent-rose" :
                                "bg-accent-amber/15 text-accent-amber"
                              }`}>{s.label}</span>
                            </td>
                            <td className="py-2.5 font-mono text-surface-200 text-xs">{s.volume.toLocaleString()}</td>
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
                      {analysis?.trends?.gainers?.map((g: any) => (
                        <div key={g.symbol} className="flex items-center justify-between">
                          <span className="text-sm text-surface-200">{g.symbol}</span>
                          <span className="text-sm font-mono text-accent-emerald">+{g.change.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="glass-card p-5">
                    <h3 className="font-bold text-accent-rose mb-3">پربازده‌ترین‌ها</h3>
                    <div className="space-y-2">
                      {analysis?.trends?.losers?.map((l: any) => (
                        <div key={l.symbol} className="flex items-center justify-between">
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
                      {analysis?.recommendations?.map((r: any, i: number) => (
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
                <CandleChartCard
                  title="تحلیل تکنیکال - فولاد"
                  data={CANDLE_DATA}
                  symbol="فولاد"
                  height={400}
                  showVolume={true}
                />

                {/* Technical Indicators Summary */}
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { name: "RSI (14)", value: "58.4", status: "خنثی", color: "var(--neutral)" },
                    { name: "MACD", value: "+125.3", status: "مثبت", color: "var(--positive)" },
                    { name: "MA (50)", value: "12,340", status: "بالاتر", color: "var(--positive)" },
                    { name: "Bollinger", value: "گسترده", status: "عادی", color: "var(--neutral)" },
                  ].map((ind, i) => (
                    <div key={i} className="glass-card p-4">
                      <div className="text-xs text-surface-500 mb-1">{ind.name}</div>
                      <div className="text-lg font-bold" style={{ color: ind.color, fontFamily: "Inter" }}>{ind.value}</div>
                      <div className="text-xs" style={{ color: ind.color === "var(--neutral)" ? "var(--neutral)" : ind.color }}>{ind.status}</div>
                    </div>
                  ))}
                </div>

                {/* Pattern Detection */}
                <div className="glass-card p-5">
                  <h3 className="font-bold text-surface-200 mb-3">الگوهای شناسایی شده</h3>
                  <div className="space-y-2">
                    {[
                      { pattern: "چکش (Hammer)", symbol: "فولاد", confidence: "بالا", desc: "الگوی برگشتی صعودی در حمایت روزانه" },
                      { pattern: "انگلفینگ صعودی", symbol: "شپنا", confidence: "متوسط", desc: "الگوی دو شمعی برگشتی در انتهای روند نزولی" },
                      { pattern: "ستاره ثاقب", symbol: "وبملت", confidence: "پایین", desc: "الگوی هشدار در سقف مقاومت" },
                    ].map((p, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-surface-800/30 rounded-lg">
                        <span className="w-2 h-2 rounded-full mt-1.5" style={{
                          background: p.confidence === "بالا" ? "var(--positive)" : p.confidence === "متوسط" ? "var(--neutral)" : "var(--negative)"
                        }} />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-surface-200 text-sm">{p.pattern}</span>
                            <span className="text-xs text-primary-400">{p.symbol}</span>
                          </div>
                          <p className="text-xs text-surface-500 mt-1">{p.desc}</p>
                        </div>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                          p.confidence === "بالا" ? "bg-accent-emerald/15 text-accent-emerald" :
                          p.confidence === "متوسط" ? "bg-accent-amber/15 text-accent-amber" :
                          "bg-accent-rose/15 text-accent-rose"
                        }`}>{p.confidence}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
    </AppLayout>
  );
}
