"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";

type AnalysisTab = "sentiment" | "trends" | "recommendations" | "elliot" | "liquidity";

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

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: "sentiment", label: "تحلیل احساسات" },
  { key: "trends", label: "روندها" },
  { key: "recommendations", label: "توصیه‌ها" },
  { key: "elliot", label: "امواج الیوت" },
  { key: "liquidity", label: "نقدینگی" },
];

const FALLBACK_SENTIMENT: SentimentItem[] = [
  { date: "۱۴۰۴/۰۳/۲۶", score: 72, label: "مثبت", volume: 15200000000 },
  { date: "۱۴۰۴/۰۳/۲۵", score: 65, label: "مثبت", volume: 12800000000 },
  { date: "۱۴۰۴/۰۳/۲۴", score: 48, label: "خنثی", volume: 9500000000 },
  { date: "۱۴۰۴/۰۳/۲۳", score: 38, label: "منفی", volume: 11200000000 },
  { date: "۱۴۰۴/۰۳/۲۲", score: 55, label: "خنثی", volume: 10500000000 },
  { date: "۱۴۰۴/۰۳/۲۱", score: 62, label: "مثبت", volume: 13800000000 },
  { date: "۱۴۰۴/۰۳/۲۰", score: 70, label: "مثبت", volume: 14500000000 },
];

const FALLBACK_TRENDS: TrendData = {
  symbol: "شاخص کل", name: "شاخص کل بورس تهران", trend: "bullish", strength: 72,
  gainers: [
    { symbol: "فولاد", change: 3.8 }, { symbol: "فملی", change: 3.2 },
    { symbol: "شپنا", change: 2.5 }, { symbol: "تاپیکو", change: 2.1 },
  ],
  losers: [
    { symbol: "خودرو", change: -2.4 }, { symbol: "وبملت", change: -1.8 },
    { symbol: "شتران", change: -1.2 }, { symbol: "کچاد", change: -0.9 },
  ],
};

const FALLBACK_RECOMMENDATIONS: Recommendation[] = [
  { symbol: "فولاد", name: "فولاد مبارکه", signal: "buy", targetPrice: 42000, currentPrice: 35840, upside: 17.2, analyst: "تحلیل آگاه" },
  { symbol: "فملی", name: "ملی مس", signal: "buy", targetPrice: 52000, currentPrice: 42500, upside: 22.4, analyst: "کارگزاری مفید" },
  { symbol: "شپنا", name: "پالایش اصفهان", signal: "hold", targetPrice: 13500, currentPrice: 12750, upside: 5.9, analyst: "تحلیل آگاه" },
  { symbol: "وبملت", name: "بانک ملت", signal: "sell", targetPrice: 4200, currentPrice: 4820, upside: -12.9, analyst: "کارگزاری فارابی" },
  { symbol: "خودرو", name: "ایران خودرو", signal: "hold", targetPrice: 3100, currentPrice: 2890, upside: 7.3, analyst: "کارگزاری مفید" },
  { symbol: "وغدیر", name: "سرمایه‌گذاری غدیر", signal: "buy", targetPrice: 38000, currentPrice: 31200, upside: 21.8, analyst: "تحلیل آگاه" },
];

const FALLBACK_ELLIOT: ElliotWave[] = [
  { wave: 1, label: "موج ۱ (حرکت صعودی)", status: "completed", priceRange: "۲,۲۰۰,۰۰۰ - ۲,۳۵۰,۰۰۰" },
  { wave: 2, label: "موج ۲ (اصلاح)", status: "completed", priceRange: "۲,۳۵۰,۰۰۰ - ۲,۲۸۰,۰۰۰" },
  { wave: 3, label: "موج ۳ (حرکت اصلی)", status: "in-progress", priceRange: "۲,۲۸۰,۰۰۰ - ۲,۶۵۰,۰۰۰" },
  { wave: 4, label: "موج ۴ (اصلاح)", status: "projected", priceRange: "۲,۶۵۰,۰۰۰ - ۲,۵۵۰,۰۰۰" },
  { wave: 5, label: "موج ۵ (حرکت نهایی)", status: "projected", priceRange: "۲,۵۵۰,۰۰۰ - ۲,۸۰۰,۰۰۰" },
];

const FALLBACK_LIQUIDITY: LiquidityFlow[] = [
  { symbol: "فولاد", inflow: 892000000000, outflow: 645000000000, net: 247000000000, direction: "positive" },
  { symbol: "فملی", inflow: 523000000000, outflow: 412000000000, net: 111000000000, direction: "positive" },
  { symbol: "شپنا", inflow: 345000000000, outflow: 389000000000, net: -44000000000, direction: "negative" },
  { symbol: "وبملت", inflow: 678000000000, outflow: 712000000000, net: -34000000000, direction: "negative" },
  { symbol: "خودرو", inflow: 234000000000, outflow: 231000000000, net: 3000000000, direction: "neutral" },
  { symbol: "تاپیکو", inflow: 445000000000, outflow: 398000000000, net: 47000000000, direction: "positive" },
];

function formatLarge(n: number): string {
  if (n >= 1000000000000) return (n / 1000000000000).toFixed(1) + " همت";
  if (n >= 1000000000) return (n / 1000000000).toFixed(1) + " میلیارد";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + " میلیون";
  return n.toLocaleString("fa-IR");
}

export default function AnalysisPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState<AnalysisTab>("sentiment");
  const [sentiment, setSentiment] = useState<SentimentItem[]>(FALLBACK_SENTIMENT);
  const [trends, setTrends] = useState<TrendData>(FALLBACK_TRENDS);
  const [recommendations, setRecommendations] = useState<Recommendation[]>(FALLBACK_RECOMMENDATIONS);
  const [elliotWaves, setElliotWaves] = useState<ElliotWave[]>(FALLBACK_ELLIOT);
  const [liquidity, setLiquidity] = useState<LiquidityFlow[]>(FALLBACK_LIQUIDITY);
  const [elliotSymbol, setElliotSymbol] = useState("شاخص کل");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const fetchAnalysis = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/analysis/overview");
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.data) {
          if (data.data.sentiment) setSentiment(data.data.sentiment);
          if (data.data.trends) setTrends(data.data.trends);
          if (data.data.recommendations) setRecommendations(data.data.recommendations);
          if (data.data.elliot) setElliotWaves(data.data.elliot);
          if (data.data.liquidity) setLiquidity(data.data.liquidity);
          setLastUpdate(new Date().toLocaleString("fa-IR"));
          return;
        }
      }
    } catch {
      // fallback
    }
    setSentiment(FALLBACK_SENTIMENT);
    setTrends(FALLBACK_TRENDS);
    setRecommendations(FALLBACK_RECOMMENDATIONS);
    setElliotWaves(FALLBACK_ELLIOT);
    setLiquidity(FALLBACK_LIQUIDITY);
    setLastUpdate("داده‌های نمونه");
    setIsLoading(false);
  };

  useEffect(() => {
    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 60000);
    return () => clearInterval(interval);
  }, []);

  const avgSentiment = sentiment.length
    ? (sentiment.reduce((sum, s) => sum + s.score, 0) / sentiment.length).toFixed(0)
    : "—";

  const TrendIndicator = ({ value }: { value: number }) => (
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

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex flex-wrap items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">تحلیل بازار</h1>
            <p className="text-sm text-surface-500 mt-1">تحلیل‌های تکنیکال، فاندامنتال و احساسات بازار</p>
            {lastUpdate && <p className="text-xs text-surface-600 mt-1">آخرین به‌روزرسانی: {lastUpdate}</p>}
          </div>
          {isLoading && <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />}
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg mb-4 text-sm">خطا: {error}</div>
        )}

        <div className="flex gap-2 mb-6 flex-wrap">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                tab === t.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}>{t.label}</button>
          ))}
        </div>

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
                    <span>منفی</span>
                    <span>خنثی</span>
                    <span>مثبت</span>
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
                    {sentiment.map((s, i) => (
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
                        <td className="py-2.5 font-mono text-surface-200 text-xs">{formatLarge(s.volume)}</td>
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
                    trends.trend === "bullish" ? "bg-accent-emerald/15 text-accent-emerald" :
                    trends.trend === "bearish" ? "bg-accent-rose/15 text-accent-rose" :
                    "bg-accent-amber/15 text-accent-amber"
                  }`}>{trends.trend === "bullish" ? "صعودی" : trends.trend === "bearish" ? "نزولی" : "خنثی"}</span>
                </div>
                <div className="flex items-center justify-between py-2 px-3">
                  <span className="text-sm text-surface-400">قدرت روند</span>
                  <TrendIndicator value={trends.strength} />
                </div>
                <div className="flex items-center justify-between py-2 px-3">
                  <span className="text-sm text-surface-400">نماد</span>
                  <span className="text-sm text-surface-200 font-bold">{trends.symbol}</span>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="glass-card p-5">
                <h3 className="font-bold text-accent-emerald mb-3">پررشدترین‌ها</h3>
                <div className="space-y-2">
                  {trends.gainers.map((g) => (
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
                  {trends.losers.map((l) => (
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
                  {recommendations.map((r, i) => (
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
                      <td className="py-2.5 font-mono text-surface-200">{r.currentPrice.toLocaleString("fa-IR")}</td>
                      <td className="py-2.5 font-mono text-surface-200">{r.targetPrice.toLocaleString("fa-IR")}</td>
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

        {tab === "elliot" && (
          <div className="space-y-4">
            <div className="glass-card p-5">
              <div className="flex items-center gap-3 mb-4">
                <h2 className="font-bold text-surface-200">تحلیل امواج الیوت</h2>
                <input
                  type="text"
                  value={elliotSymbol}
                  onChange={(e) => setElliotSymbol(e.target.value)}
                  placeholder="نماد..."
                  className="px-3 py-1.5 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-32"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-sm">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 font-medium">موج</th>
                      <th className="pb-2 font-medium">توضیحات</th>
                      <th className="pb-2 font-medium">وضعیت</th>
                      <th className="pb-2 font-medium">محدوده قیمت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {elliotWaves.map((w) => (
                      <tr key={w.wave} className="border-b border-surface-800/50">
                        <td className="py-2.5 font-mono text-surface-200">{w.wave}</td>
                        <td className="py-2.5 text-surface-200">{w.label}</td>
                        <td className="py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            w.status === "completed" ? "bg-accent-emerald/15 text-accent-emerald" :
                            w.status === "in-progress" ? "bg-accent-amber/15 text-accent-amber" :
                            "bg-surface-600/30 text-surface-400"
                          }`}>{w.status === "completed" ? "تکمیل شده" : w.status === "in-progress" ? "در حال انجام" : "پیش‌بینی"}</span>
                        </td>
                        <td className="py-2.5 font-mono text-surface-400 text-xs">{w.priceRange}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === "liquidity" && (
          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-4">جریان نقدینگی</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-2 font-medium">نماد</th>
                    <th className="pb-2 font-medium">ورود پول</th>
                    <th className="pb-2 font-medium">خروج پول</th>
                    <th className="pb-2 font-medium">خالص</th>
                    <th className="pb-2 font-medium">جهت</th>
                  </tr>
                </thead>
                <tbody>
                  {liquidity.map((l, i) => (
                    <tr key={i} className="border-b border-surface-800/50">
                      <td className="py-2.5 font-mono font-bold text-surface-200">{l.symbol}</td>
                      <td className="py-2.5 font-mono text-accent-emerald">{formatLarge(l.inflow)}</td>
                      <td className="py-2.5 font-mono text-accent-rose">{formatLarge(l.outflow)}</td>
                      <td className={`py-2.5 font-mono ${l.direction === "positive" ? "text-accent-emerald" : l.direction === "negative" ? "text-accent-rose" : "text-surface-400"}`}>
                        {l.net >= 0 ? "+" : ""}{formatLarge(l.net)}
                      </td>
                      <td className="py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          l.direction === "positive" ? "bg-accent-emerald/15 text-accent-emerald" :
                          l.direction === "negative" ? "bg-accent-rose/15 text-accent-rose" :
                          "bg-accent-amber/15 text-accent-amber"
                        }`}>{l.direction === "positive" ? "ورودی" : l.direction === "negative" ? "خروجی" : "خنثی"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
