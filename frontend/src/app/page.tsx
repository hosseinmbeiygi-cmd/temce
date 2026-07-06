"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import { apiGet, safeExtractArray } from "@/lib/api";
import { useDebugLogs } from "@/hooks/useDebugLogs";
import SSRSafe from "@/components/SSRSafe";
import MiniSparkline from "@/components/MiniSparkline";

// ── Dynamic imports ──────────────────────────────────────────────────────────────────────────────────────────────────
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[280px]" />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[200px]" />,
});
const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[200px]" />,
});

// ── Types ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
interface MarketOverview {
  total_instruments?: number;
  gainers?: number;
  losers?: number;
  unchanged?: number;
  avg_change_pct?: number;
  total_volume?: number;
  total_value?: number;
  index_value?: number;
  index_change_pct?: number;
}

interface ScreenerItem {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change_pct: number;
  volume: number;
  value: number;
  smc_score: number;
  phase: string;
}

interface CommodityItem {
  name: string;
  price: number;
  change: number;
  change_pct: number;
  category: string;
  unit: string;
  time?: string;
}

interface CryptoItem {
  name: string;
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
}

interface MarketDashboardData {
  overview: MarketOverview;
  screener: ScreenerItem[];
  commodities: CommodityItem[];
  crypto: CryptoItem[];
  gainers: any[];
  losers: any[];
  active: any[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
function fmt(n: number): string {
  if (n >= 1_000_000_000_000) return (n / 1_000_000_000_000).toFixed(1) + "T";
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString("fa-IR");
}

function fmtPrice(n: number): string {
  if (n >= 1_000_000_000_000) return (n / 1_000_000_000_000).toFixed(2) + "T";
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(0) + "K";
  return n.toLocaleString("fa-IR");
}

const PHASE_COLORS: Record<string, string> = {
  accumulation: "bg-accent-emerald/15 text-accent-emerald",
  distribution: "bg-accent-rose/15 text-accent-rose",
  markup: "bg-primary-600/20 text-primary-300",
  markdown: "bg-accent-rose/20 text-accent-rose",
  neutral: "bg-surface-600/30 text-surface-400",
};

const PHASE_LABELS: Record<string, string> = {
  accumulation: "تجمع",
  distribution: "توزیع",
  markup: "مارکاپ",
  markdown: "مارک‌داون",
  neutral: "خنثی",
};

// ── Mock data generators (for fallback) ────────────────────────────────────────────────────────────────────────────────
function generateMockIndices() {
  return [
    { name: "شاخص بورس", code: "TEDPIX", value: 5_187_263, change: 1.16, pe: 7.07, trading_value: 125.94 },
    { name: "شاخص فرابورس", code: "IFX", value: 39_771, change: 1.56, pe: 7.84, trading_value: 30.17 },
    { name: "شاخص بورس ایران", code: "IREX", value: 5_011_383, change: 1.23, pe: 7.15, trading_value: 157.02 },
  ];
}

function generateMockMarketIndicators() {
  return [
    { label: "فشار تقاضا", values: [3.71, 11.22, 9.25], color: "text-accent-emerald" },
    { label: "قدرت خرید حقیقی", values: [4.17, 1.42, 2.09], color: "text-primary-300" },
    { label: "سرانه خرید حقیقی (M)", values: [63.65, 80.94, 76.55], color: "text-accent-amber" },
    { label: "خالص خرید حقیقی (%)", values: [15.78, 11.84, 12.61], color: "text-accent-cyan" },
    { label: "خالص خرید (همت)", values: [0.50, 1.53, 2.03], color: "text-accent-violet" },
  ];
}

function generateMockSectors() {
  return [
    { name: "فلزات گران بها", change: 2.57, color: "#10b981" },
    { name: "فراورده نفتی", change: 2.34, color: "#10b981" },
    { name: "بانکها", change: 1.96, color: "#10b981" },
    { name: "مواد شیمیایی", change: 1.42, color: "#10b981" },
    { name: "آهن و فولاد", change: 0.98, color: "#10b981" },
    { name: "کانی فلزی", change: 0.65, color: "#10b981" },
    { name: "دارویی", change: -0.34, color: "#f43f5e" },
    { name: "سیمان", change: -0.78, color: "#f43f5e" },
    { name: "خودرو", change: -1.23, color: "#f43f5e" },
    { name: "بیمه", change: -1.87, color: "#f43f5e" },
  ];
}

function generateMockCurrencies() {
  return [
    { name: "دلار آمریکا", price: 1_746_000, change: -16_000, pct: -0.9 },
    { name: "یورو", price: 1_997_900, change: -9_700, pct: -0.5 },
    { name: "درهم امارات", price: 479_900, change: -8_880, pct: -1.8 },
    { name: "پوند انگلیس", price: 2_332_000, change: -13_000, pct: -0.6 },
    { name: "لیر ترکیه", price: 37_350, change: -150, pct: -0.4 },
    { name: "یوان چین", price: 257_200, change: -1_200, pct: -0.5 },
  ];
}

function generateMockCoins() {
  return [
    { name: "سکه امامی", price: 1_769_800_000, change: 24_950_000, pct: 1.4 },
    { name: "سکه بهار آزادی", price: 1_720_100_000, change: 20_700_000, pct: 1.2 },
    { name: "نیم سکه", price: 917_200_000, change: 13_800_000, pct: 1.5 },
    { name: "ربع سکه", price: 528_600_000, change: 4_900_000, pct: 0.9 },
    { name: "سکه گرمی", price: 265_000_000, change: 0, pct: 0 },
  ];
}

function generateMockGoldOunce() {
  return [
    { name: "انس طلا", price: 4_175, change: 52.1, pct: 1.3 },
    { name: "انس نقره", price: 62.4, change: 1.5, pct: 2.5 },
    { name: "انس پلاتین", price: 1_652, change: 20.1, pct: 1.2 },
    { name: "انس پالادیوم", price: 1_273, change: 0.3, pct: 0 },
  ];
}

function generateMockEnergy() {
  return [
    { name: "نفت سبک", price: 69, change: 0.3, pct: 0.5 },
    { name: "نفت برنت", price: 72, change: 0.4, pct: 0.5 },
    { name: "نفت اپک", price: 77, change: 0, pct: 0 },
    { name: "گاز طبیعی", price: 3.2, change: 0, pct: 1.1 },
    { name: "گازوییل", price: 951.5, change: 21.9, pct: 2.4 },
  ];
}

function generateMockMetals() {
  return [
    { name: "مس", price: 13_380, change: 62.1, pct: 0.5 },
    { name: "روی", price: 3_550, change: 63.4, pct: 1.8 },
    { name: "سرب", price: 1_894, change: 18.1, pct: 1 },
    { name: "نیکل", price: 16_392, change: 126.8, pct: 0.8 },
    { name: "آلومینیوم", price: 3_093, change: 7.8, pct: 0.3 },
    { name: "قلع", price: 51_282, change: 0, pct: 0 },
  ];
}

function generateMockFinancialRatios() {
  return [
    { label: "P/E (ttm)", bourse: 7.07, farabourse: 7.84, irex: 7.15 },
    { label: "P/S (ttm)", bourse: 1.84, farabourse: 1.45, irex: 1.78 },
    { label: "P/B", bourse: 2.70, farabourse: 2.98, irex: 2.73 },
    { label: "P/D", bourse: 18.46, farabourse: 15.29, irex: 17.99 },
    { label: "ROA", bourse: 0.12, farabourse: 0.10, irex: 0.12 },
    { label: "ROE", bourse: 0.45, farabourse: 0.46, irex: 0.45 },
    { label: "EV/EBIT", bourse: 6.90, farabourse: 6.07, irex: 6.79 },
  ];
}

function generateMockNews() {
  return [
    { symbol: "دشیری", title: "گزارش فعالیت ماهانه دوره 1 ماهه منتهی به 1405/03/31", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
    { symbol: "سبد مانی", title: "صورت‌های مالی سال مالی منتهی به 1404/06/31 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
    { symbol: "وملی", title: "خلاصه تصمیمات مجمع عمومی عادی سالیانه دوره 12 ماهه منتهی به 1404/12/29", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
    { symbol: "فرابورس", title: "صورت‌های مالی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
    { symbol: "خکار", title: "صورت‌های مالی تلفیقی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
    { symbol: "لبوتان", title: "صورت‌های مالی تلفیقی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral" },
  ];
}

function generateMockTopTraded() {
  return [
    { symbol: "وبملت", price: 1_317, change: 2.57, value: 7.5 },
    { symbol: "شستا", price: 2_355, change: 2.97, value: 5.7 },
    { symbol: "فملی", price: 20_830, change: 0.34, value: 5.53 },
    { symbol: "شبندر", price: 12_570, change: 2.95, value: 5.3 },
    { symbol: "خودرو", price: 565, change: 2.91, value: 4.3 },
    { symbol: "شتران", price: 5_290, change: 0.76, value: 4.14 },
    { symbol: "وتجارت", price: 632, change: -0.78, value: 3.55 },
    { symbol: "ونوین", price: 3_960, change: 2.86, value: 3.31 },
  ];
}

// ── Main Page ──────────────────────────────────────────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { logs, addLog } = useDebugLogs();
  const [tab, setTab] = useState<"all" | "gainers" | "losers">("all");

  // ── Fetch dashboard data ──
  const { data: dashboardData, isLoading } = useQuery<MarketDashboardData>({
    queryKey: ["market-dashboard"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: MarketDashboardData }>("/market-dashboard");
      return res?.data ?? ({} as MarketDashboardData);
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ── Fallback data ──
  const indices = useMemo(() => generateMockIndices(), []);
  const marketIndicators = useMemo(() => generateMockMarketIndicators(), []);
  const sectors = useMemo(() => generateMockSectors(), []);
  const currencies = useMemo(() => generateMockCurrencies(), []);
  const coins = useMemo(() => generateMockCoins(), []);
  const goldOunce = useMemo(() => generateMockGoldOunce(), []);
  const energy = useMemo(() => generateMockEnergy(), []);
  const metals = useMemo(() => generateMockMetals(), []);
  const financialRatios = useMemo(() => generateMockFinancialRatios(), []);
  // ── Fetch real news from API ──
  const { data: realNews } = useQuery({
    queryKey: ["home-news"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items?: Array<{ id: string; title: string; summary?: string; source?: string; published_at?: string; symbols?: string[]; category?: string; sentiment?: string }>; total?: number } }>("/news?page_size=10");
        return (res?.data?.items ?? []);
      } catch { return []; }
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  const mockNews = useMemo(() => generateMockNews(), []);
  const news = (realNews && realNews.length > 0)
    ? realNews.map((item: any) => ({ symbol: (item.symbols && item.symbols.length > 0 ? item.symbols[0] : (item.source || "خبر")), title: item.title || "", date: (item.published_at || "").split("T")[0] || "", source: item.source || "", sentiment: item.sentiment || "neutral" }))
    : mockNews;
  const topTraded = useMemo(() => generateMockTopTraded(), []);

  const overview = dashboardData?.overview;
  const screener = dashboardData?.screener ?? [];
  const gainers = dashboardData?.gainers ?? [];
  const losers = dashboardData?.losers ?? [];
  const active = dashboardData?.active ?? [];

  const gainersCount = overview?.gainers ?? 760;
  const losersCount = overview?.losers ?? 176;
  const totalValue = overview?.total_value ?? 2_556_447_000_000_000;

  return (
    <AppLayout>
      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 1: Market Indices
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {indices.map((idx) => (
          <div key={idx.code} className="glass-card p-4 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-surface-200">{idx.name}</span>
                <span className="text-[10px] text-surface-500">({idx.code})</span>
              </div>
              <div className="text-2xl font-black text-surface-100 mt-1">
                {idx.value.toLocaleString("fa-IR")}
              </div>
              <div className={`text-sm font-bold mt-0.5 ${idx.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                {idx.change >= 0 ? "+" : ""}{idx.change.toFixed(2)}%
              </div>
            </div>
            <div className="text-left space-y-1">
              <div className="text-xs text-surface-500">P/E <span className="text-surface-300 font-mono">{idx.pe}</span></div>
              <div className="text-xs text-surface-500">ارزش معاملات <span className="text-surface-300 font-mono">{idx.trading_value}T</span></div>
            </div>
          </div>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 2: Market Indicators (Demand Pressure, Buying Power, etc.)
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-4">
        {marketIndicators.map((ind) => (
          <div key={ind.label} className="glass-card p-3">
            <div className="text-[10px] text-surface-500 mb-2">{ind.label}</div>
            <div className="grid grid-cols-3 gap-1">
              {ind.values.map((v, i) => (
                <div key={i} className="text-center">
                  <div className={`text-sm font-black ${ind.color}`}>{v}</div>
                  <div className="text-[8px] text-surface-600">
                    {i === 0 ? "بورس" : i === 1 ? "فرابورس" : "ایران"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 3: Quick Links
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mb-4">
        {[
          { href: "/screener", icon: "🔍", label: "غربالگر" },
          { href: "/heatmap", icon: "🗺️", label: "نقشه بازار" },
          { href: "/heatmap?mode=bubble", icon: "🫧", label: "نقشه حبابی" },
          { href: "/funds", icon: "📊", label: "اوراق درآمد ثابت" },
          { href: "/codal", icon: "📋", label: "اطلاعیه‌ها" },
          { href: "/macro", icon: "📈", label: "داده‌های کلان" },
          { href: "/indicators", icon: "📉", label: "نمودار تکنیکال" },
          { href: "/analysis", icon: "🔬", label: "تحلیل تکنیکال" },
        ].map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="glass-card p-3 flex flex-col items-center gap-1.5 hover:bg-white/[0.03] transition-colors group"
          >
            <span className="text-2xl group-hover:scale-110 transition-transform">{link.icon}</span>
            <span className="text-[10px] text-surface-400 group-hover:text-surface-200 transition-colors text-center">{link.label}</span>
          </Link>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 4: Sector Performance + Market Breadth + Top Traded
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {/* Sector Performance */}
        <Card title="عملکرد صنایع">
          <div className="space-y-1.5 max-h-[320px] overflow-y-auto">
            {sectors.map((s) => (
              <div key={s.name} className="flex items-center gap-2 py-1">
                <span className="text-xs text-surface-400 w-24 truncate">{s.name}</span>
                <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(Math.abs(s.change) * 15, 100)}%`,
                      backgroundColor: s.change >= 0 ? "#10b981" : "#f43f5e",
                    }}
                  />
                </div>
                <span className={`text-xs font-mono w-14 text-left ${s.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {s.change >= 0 ? "+" : ""}{s.change.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Market Breadth */}
        <Card title="فشار عرضه و تقاضا">
          <div className="flex flex-col items-center justify-center h-full py-4">
            <div className="relative w-40 h-40">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="12" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke="#10b981"
                  strokeWidth="12"
                  strokeDasharray={`${(gainersCount / (gainersCount + losersCount)) * 251.2} 251.2`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-black text-surface-100">{gainersCount + losersCount}</span>
                <span className="text-[10px] text-surface-500">کل نمادها</span>
              </div>
            </div>
            <div className="flex gap-6 mt-4">
              <div className="text-center">
                <div className="text-lg font-black text-accent-emerald">{gainersCount}</div>
                <div className="text-[10px] text-surface-500">صعودی ({((gainersCount / (gainersCount + losersCount)) * 100).toFixed(1)}%)</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-black text-accent-rose">{losersCount}</div>
                <div className="text-[10px] text-surface-500">نزولی ({((losersCount / (gainersCount + losersCount)) * 100).toFixed(1)}%)</div>
              </div>
            </div>
            <div className="text-xs text-surface-500 mt-3">
              ارزش معاملات بورس و فرابورس: {fmt(totalValue)}
            </div>
          </div>
        </Card>

        {/* Top Traded */}
        <Card
          title="بیشترین ارزش معاملات"
          actions={
            <>
              <CardAction active={tab === "all"} onClick={() => setTab("all")}>همه</CardAction>
              <CardAction active={tab === "gainers"} onClick={() => setTab("gainers")}>بیشترین حجم</CardAction>
            </>
          }
        >
          <div className="overflow-hidden max-h-[320px]">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-800">
                  <th className="py-1.5 text-right font-normal">نماد</th>
                  <th className="py-1.5 text-right font-normal">قیمت</th>
                  <th className="py-1.5 text-right font-normal">تغییر</th>
                  <th className="py-1.5 text-right font-normal">ارزش</th>
                </tr>
              </thead>
              <tbody>
                {topTraded.map((row) => (
                  <tr key={row.symbol} className="border-b border-surface-800/50 hover:bg-white/[0.02]">
                    <td className="py-1.5">
                      <Link href={`/symbol/${encodeURIComponent(row.symbol)}`} className="text-surface-200 hover:text-primary-300 font-bold">
                        {row.symbol}
                      </Link>
                    </td>
                    <td className="py-1.5 text-surface-300 font-mono">{row.price.toLocaleString("fa-IR")}</td>
                    <td className={`py-1.5 font-mono ${row.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {row.change >= 0 ? "+" : ""}{row.change.toFixed(2)}%
                    </td>
                    <td className="py-1.5 text-surface-400 font-mono">{row.value}T</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 5: News + Screener Top
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {/* News */}
        <Card title={realNews && realNews.length > 0 ? "📰 آخرین اخبار بازار" : "اطلاعیه‌ها و مجامع"}>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {news.map((item, i) => (
              <div key={i} className="flex items-start gap-2 py-2 border-b border-surface-800/50 last:border-0">
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                  item.sentiment === "positive" ? "bg-accent-emerald" :
                  item.sentiment === "negative" ? "bg-accent-rose" : "bg-primary-500"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-surface-200">{item.symbol}</span>
                    {item.source && <span className="text-[9px] text-surface-500">{item.source}</span>}
                    <span className="text-[9px] text-surface-600">{item.date}</span>
                  </div>
                  <p className="text-[11px] text-surface-400 mt-0.5 truncate">{item.title}</p>
                </div>
              </div>
            ))}
            <Link href={realNews && realNews.length > 0 ? "/news" : "/codal"} className="block text-center text-xs text-primary-400 hover:text-primary-300 py-2">
              لیست کامل {realNews && realNews.length > 0 ? "اخبار" : "اطلاعیه‌ها"} ←
            </Link>
          </div>
        </Card>

        {/* Screener Top */}
        <Card
          title="غربالگر پیشرفته - برترین SMC"
          actions={<Link href="/screener" className="text-xs text-primary-400 hover:text-primary-300">مشاهده همه ←</Link>}
        >
          <div className="overflow-hidden max-h-[300px]">
            {screener.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-800">
                    <th className="py-1.5 text-right font-normal">#</th>
                    <th className="py-1.5 text-right font-normal">نماد</th>
                    <th className="py-1.5 text-right font-normal">تغییر</th>
                    <th className="py-1.5 text-right font-normal">SMC</th>
                    <th className="py-1.5 text-right font-normal">فاز</th>
                  </tr>
                </thead>
                <tbody>
                  {screener.slice(0, 10).map((item, i) => (
                    <tr key={item.symbol} className="border-b border-surface-800/50 hover:bg-white/[0.02]">
                      <td className="py-1.5 text-surface-500">{i + 1}</td>
                      <td className="py-1.5">
                        <Link href={`/symbol/${encodeURIComponent(item.symbol)}`} className="text-surface-200 hover:text-primary-300 font-bold">
                          {item.symbol}
                        </Link>
                      </td>
                      <td className={`py-1.5 font-mono ${item.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {item.change_pct >= 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                      </td>
                      <td className="py-1.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                          item.smc_score >= 0.7 ? "bg-accent-emerald/15 text-accent-emerald" :
                          item.smc_score >= 0.5 ? "bg-accent-amber/15 text-accent-amber" :
                          "bg-surface-600/30 text-surface-400"
                        }`}>
                          {Math.round(item.smc_score * 100)}
                        </span>
                      </td>
                      <td className="py-1.5">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${PHASE_COLORS[item.phase] || PHASE_COLORS.neutral}`}>
                          {PHASE_LABELS[item.phase] || item.phase}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex items-center justify-center h-40 text-surface-500 text-xs">
                {isLoading ? "در حال بارگذاری..." : "داده‌ای موجود نیست"}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 6: Currencies + Gold + Coins
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {/* Currencies */}
        <Card title="ارز آزاد">
          <div className="space-y-1">
            {currencies.map((c) => (
              <div key={c.name} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                <span className="text-xs text-surface-300">{c.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-surface-200">{c.price.toLocaleString("fa-IR")}</span>
                  <span className={`text-[10px] font-mono ${c.pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {c.pct >= 0 ? "+" : ""}{c.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Gold Ounce */}
        <Card title="انس">
          <div className="space-y-1">
            {goldOunce.map((g) => (
              <div key={g.name} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                <span className="text-xs text-surface-300">{g.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-surface-200">{g.price.toLocaleString("fa-IR")}</span>
                  <span className={`text-[10px] font-mono ${g.pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {g.pct >= 0 ? "+" : ""}{g.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Coins */}
        <Card title="سکه">
          <div className="space-y-1">
            {coins.map((c) => (
              <div key={c.name} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                <span className="text-xs text-surface-300">{c.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-surface-200">{fmtPrice(c.price)}</span>
                  <span className={`text-[10px] font-mono ${c.pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {c.pct >= 0 ? "+" : ""}{c.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 7: Energy + Metals + Financial Ratios
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {/* Energy */}
        <Card title="نفت و انرژی">
          <div className="space-y-1">
            {energy.map((e) => (
              <div key={e.name} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                <span className="text-xs text-surface-300">{e.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-surface-200">{e.price}</span>
                  <span className={`text-[10px] font-mono ${e.pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {e.pct >= 0 ? "+" : ""}{e.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Metals */}
        <Card title="فلزات اساسی">
          <div className="space-y-1">
            {metals.map((m) => (
              <div key={m.name} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                <span className="text-xs text-surface-300">{m.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-surface-200">{m.price.toLocaleString("fa-IR")}</span>
                  <span className={`text-[10px] font-mono ${m.pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {m.pct >= 0 ? "+" : ""}{m.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Financial Ratios */}
        <Card title="نسبت مالی">
          <div className="overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-800">
                  <th className="py-1.5 text-right font-normal">نسبت</th>
                  <th className="py-1.5 text-right font-normal">بورس</th>
                  <th className="py-1.5 text-right font-normal">فرابورس</th>
                  <th className="py-1.5 text-right font-normal">ایران</th>
                </tr>
              </thead>
              <tbody>
                {financialRatios.map((r) => (
                  <tr key={r.label} className="border-b border-surface-800/50">
                    <td className="py-1.5 text-surface-400">{r.label}</td>
                    <td className="py-1.5 text-surface-200 font-mono">{r.bourse}</td>
                    <td className="py-1.5 text-surface-200 font-mono">{r.farabourse}</td>
                    <td className="py-1.5 text-surface-200 font-mono">{r.irex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 8: Crypto
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      <div className="mb-4">
        <Card title="ارز دیجیتال">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
            {(dashboardData?.crypto ?? [
              { name: "بیت کوین", symbol: "BTC", price: 62_650, change: 22, change_pct: 0 },
              { name: "اتریوم", symbol: "ETH", price: 1_760, change: 9.1, change_pct: 0.5 },
              { name: "تتر", symbol: "USDT", price: 1_754_350, change: 2_590, change_pct: 0.2 },
              { name: "دش", symbol: "DASH", price: 36, change: -0.2, change_pct: -0.6 },
              { name: "ریپل", symbol: "XRP", price: 1.13, change: -0.01, change_pct: -0.9 },
              { name: "لایت کوین", symbol: "LTC", price: 44.8, change: 0.2, change_pct: 0.4 },
            ]).map((c) => (
              <div key={c.symbol} className="glass-card p-3 text-center">
                <div className="text-[10px] text-surface-500 mb-1">{c.symbol}</div>
                <div className="text-sm font-black text-surface-200">{fmtPrice(c.price)}</div>
                <div className={`text-xs font-mono ${c.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {c.change_pct >= 0 ? "+" : ""}{c.change_pct.toFixed(2)}%
                </div>
                <div className="text-[9px] text-surface-600 mt-0.5">{c.name}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}
