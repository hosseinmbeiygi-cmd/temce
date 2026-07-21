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
function dedupeByName<T extends { name?: string; symbol?: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter(item => {
    const key = item.name || item.symbol || "";
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function fmt(n: number): string {
  // Show in میلیارد تومان (1 میلیارد تومان = 10 میلیارد ریال)
  const toman = n / 10;
  if (toman >= 1_000_000) return (toman / 1_000_000).toFixed(1) + " همت";
  if (toman >= 1_000) return (toman / 1_000).toFixed(1) + " م.ت";
  if (toman >= 1) return toman.toFixed(1) + " م.ت";
  return n.toLocaleString("fa-IR") + " ریال";
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
    { name: "شاخص کل", code: "TEDPIX", value: 5_286_856, change: -0.46, pe: 7.07, trading_value: 125.94 },
    { name: "شاخص کل (هم وزن)", code: "IFX", value: 814_271, change: -1.18, pe: 7.84, trading_value: 30.17 },
    { name: "شاخص قیمت (هم وزن)", code: "IREX", value: 665_016, change: -0.46, pe: 7.15, trading_value: 157.02 },
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
    { symbol: "دشیری", title: "گزارش فعالیت ماهانه دوره 1 ماهه منتهی به 1405/03/31", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
    { symbol: "سبد مانی", title: "صورت‌های مالی سال مالی منتهی به 1404/06/31 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
    { symbol: "وملی", title: "خلاصه تصمیمات مجمع عمومی عادی سالیانه دوره 12 ماهه منتهی به 1404/12/29", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
    { symbol: "فرابورس", title: "صورت‌های مالی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
    { symbol: "خکار", title: "صورت‌های مالی تلفیقی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
    { symbol: "لبوتان", title: "صورت‌های مالی تلفیقی سال مالی منتهی به 1404/12/29 (حسابرسی شده)", date: "1405-04-10", source: "کدال", sentiment: "neutral", url: "" },
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
  const mockIndices = useMemo(() => generateMockIndices(), []);

  // Fetch indices directly from /market/indices (fast, separate from slow dashboard)
  const { data: realIndices } = useQuery({
    queryKey: ["home-indices"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; index_value: number; index_change_pct: number; index_change: number; trade_value?: number }> }>("/market/indices");
        if (res?.success && Array.isArray(res.data) && res.data.length > 0) {
          return res.data.slice(0, 3).map((idx) => ({
            name: idx.name,
            code: idx.name,
            value: idx.index_value,
            change: idx.index_change_pct,
            pe: 0,
            trading_value: idx.trade_value ? Math.round(idx.trade_value / 1e12 * 10) / 10 : 0,
          }));
        }
      } catch {}
      return null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const indices = realIndices && realIndices.length > 0 ? realIndices : mockIndices;

  // ── Fetch real market indicators from DB ──
  const { data: realIndicators } = useQuery({
    queryKey: ["home-market-indicators"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { bourse: Record<string, number>; farabourse: Record<string, number>; total: Record<string, number> } }>("/market/indicators");
        if (res?.success && res.data) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  const marketIndicators = useMemo(() => {
    if (realIndicators && realIndicators.total) {
      const b = realIndicators.bourse;
      const f = realIndicators.farabourse;
      const t = realIndicators.total;
      return [
        { label: "فشار تقاضا (%)", values: [b.demand_pressure, f.demand_pressure, t.demand_pressure], color: "text-accent-emerald" },
        { label: "قدرت خرید حقیقی (همت)", values: [b.buying_power, f.buying_power, t.buying_power], color: "text-primary-300" },
        { label: "سرانه خرید حقیقی (م.تومان)", values: [b.per_capita_buy, f.per_capita_buy, t.per_capita_buy], color: "text-accent-amber" },
        { label: "خالص خرید حقیقی (%)", values: [b.net_real_pct, f.net_real_pct, t.net_real_pct], color: "text-accent-cyan" },
        { label: "خالص خرید (همت)", values: [b.net_real_billion, f.net_real_billion, t.net_real_billion], color: "text-accent-violet" },
      ];
    }
    return generateMockMarketIndicators();
  }, [realIndicators]);

  // ── Fetch real sector data from DB ──
  const { data: realSectors } = useQuery({
    queryKey: ["home-sectors"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; change: number; count: number; total_value: number }> }>("/market/sectors");
        if (res?.success && res.data && res.data.length > 0) return res.data;
      } catch {}
      return null;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  const sectors = useMemo(() => {
    if (realSectors && realSectors.length > 0) {
      return realSectors.slice(0, 15).map(s => ({
        name: s.name,
        change: s.change || 0,
        color: (s.change || 0) >= 0 ? "#10b981" : "#f43f5e",
      }));
    }
    return generateMockSectors();
  }, [realSectors]);
  const financialRatios = useMemo(() => generateMockFinancialRatios(), []);

  // ── Fetch real currencies from BrsApi ──
  const { data: currencyData } = useQuery({
    queryKey: ["home-currency"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; symbol: string; price: number; change_value: number; change_percent: number }> }>("/brsapi/currency?limit=6");
        return res?.data ?? [];
      } catch { return []; }
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
  });
  const currencies = useMemo(() => {
    if (currencyData && currencyData.length > 0) {
      return currencyData.map(c => ({
        name: c.name || c.symbol,
        price: c.price || 0,
        change: c.change_value || 0,
        pct: c.change_percent || 0,
      }));
    }
    return generateMockCurrencies();
  }, [currencyData]);

  // ── Fetch real gold/coins from BrsApi ──
  const { data: goldCoinData } = useQuery({
    queryKey: ["home-gold-coin"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; symbol: string; price: number; change_value: number; change_percent: number }> }>("/brsapi/gold-coin?limit=8");
        return res?.data ?? [];
      } catch { return []; }
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
  });
  const coins = useMemo(() => {
    if (goldCoinData && goldCoinData.length > 0) {
      return goldCoinData.map(g => ({
        name: g.name || g.symbol,
        price: g.price || 0,
        change: g.change_value || 0,
        pct: g.change_percent || 0,
      }));
    }
    return generateMockCoins();
  }, [goldCoinData]);
  // ── Fetch real commodity data (gold ounce, metals, energy) from BrsApi ──
  const { data: commodityData } = useQuery({
    queryKey: ["home-commodities"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; symbol: string; price: number; change_value: number; change_percent: number; category: string }> }>("/brsapi/commodities");
        return res?.data ?? [];
      } catch { return []; }
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
  });

  const goldOunce = useMemo(() => {
    if (commodityData && commodityData.length > 0) {
      const precious = dedupeByName(commodityData.filter(c => c.category === "precious_metal"));
      if (precious.length > 0) {
        return precious.map(c => ({
          name: c.name || c.symbol,
          price: c.price || 0,
          change: c.change_value || 0,
          pct: c.change_percent || 0,
        }));
      }
    }
    return generateMockGoldOunce();
  }, [commodityData]);

  const metals = useMemo(() => {
    if (commodityData && commodityData.length > 0) {
      const base = dedupeByName(commodityData.filter(c => c.category === "base_metal"));
      if (base.length > 0) {
        return base.map(c => ({
          name: c.name || c.symbol,
          price: c.price || 0,
          change: c.change_value || 0,
          pct: c.change_percent || 0,
        }));
      }
    }
    return generateMockMetals();
  }, [commodityData]);

  const energy = useMemo(() => {
    if (commodityData && commodityData.length > 0) {
      const eng = dedupeByName(commodityData.filter(c => c.category === "energy"));
      if (eng.length > 0) {
        return eng.map(c => ({
          name: c.name || c.symbol,
          price: c.price || 0,
          change: c.change_value || 0,
          pct: c.change_percent || 0,
        }));
      }
    }
    return generateMockEnergy();
  }, [commodityData]);

  // ── Fetch real crypto from BrsApi ──
  const { data: cryptoData } = useQuery({
    queryKey: ["home-crypto"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: Array<{ name: string; symbol: string; price_usd: number; change_percent: number; market_cap: number }> }>("/brsapi/crypto?limit=6");
        return res?.data ?? [];
      } catch { return []; }
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
  });

  // ── Fetch real news from API ──
  const { data: realNews } = useQuery({
    queryKey: ["home-news"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { items?: Array<{ id: string; title: string; summary?: string; source?: string; url?: string; published_at?: string; symbols?: string[]; category?: string; sentiment?: string }>; total?: number } }>("/news?page_size=10");
        return (res?.data?.items ?? []);
      } catch { return []; }
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  const mockNews = useMemo(() => generateMockNews(), []);
  const news = (realNews && realNews.length > 0)
    ? realNews.map((item: any) => ({ symbol: (item.symbols && item.symbols.length > 0 ? item.symbols[0] : (item.source || "خبر")), title: item.title || "", date: (item.published_at || "").split("T")[0] || "", source: item.source || "", sentiment: item.sentiment || "neutral", url: item.url || "" }))
    : mockNews;
  const topTraded = useMemo(() => generateMockTopTraded(), []);

  const overview = dashboardData?.overview;
  const screener = dashboardData?.screener ?? [];
  const gainers = dashboardData?.gainers ?? [];
  const losers = dashboardData?.losers ?? [];
  const active = dashboardData?.active ?? [];

  const gainersCount = overview?.gainers ?? 0;
  const losersCount = overview?.losers ?? 0;
  const totalValue = overview?.total_value ?? 0;
  const totalSymbols = gainersCount + losersCount;
  const hasBreadth = totalSymbols > 0;

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
              <div className="text-xs text-surface-500">ارزش معاملات <span className="text-surface-300 font-mono">{fmt(idx.trading_value * 1e9)}</span></div>
            </div>
          </div>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════════════════════════════════════════════════════════
          ROW 2: Market Indicators (Demand Pressure, Buying Power, etc.)
          ════════════════════════════════════════════════════════════════════════════════════════════════════════════ */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-4 animate-pulse">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="glass-card p-3">
              <div className="h-3 bg-surface-700/50 rounded w-24 mb-3" />
              <div className="grid grid-cols-3 gap-1">
                <div className="h-8 bg-surface-700/30 rounded" />
                <div className="h-8 bg-surface-700/30 rounded" />
                <div className="h-8 bg-surface-700/30 rounded" />
              </div>
            </div>
          ))}
        </div>
      )}
      {!isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-4">
          {marketIndicators.map((ind, indi) => (
            <div key={`${ind.label}-${indi}`} className="glass-card p-3">
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
      )}

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
            {sectors.map((s, si) => (
              <div key={`${s.name}-${si}`} className="flex items-center gap-2 py-1">
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

        {/* Market Breadth / Supply & Demand Pressure */}
        <Card title="فشار عرضه و تقاضا">
          <div className="space-y-2 max-h-[320px] overflow-y-auto">
            {realIndicators?.total ? (
              <>
                {/* Demand Pressure */}
                <div className="flex items-center justify-between py-2 border-b border-surface-800/50">
                  <span className="text-xs text-surface-400">فشار تقاضا</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-black ${(realIndicators.total.demand_pressure ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {(realIndicators.total.demand_pressure ?? 0).toFixed(1)}%
                    </span>
                  </div>
                </div>
                {/* Buying Power */}
                <div className="flex items-center justify-between py-2 border-b border-surface-800/50">
                  <span className="text-xs text-surface-400">قدرت خرید حقیقی</span>
                  <span className="text-sm font-black text-primary-300">
                    {(realIndicators.total.buying_power ?? 0).toFixed(1)} همت
                  </span>
                </div>
                {/* Per Capita Buy */}
                <div className="flex items-center justify-between py-2 border-b border-surface-800/50">
                  <span className="text-xs text-surface-400">سرانه خرید حقیقی</span>
                  <span className="text-sm font-black text-accent-amber">
                    {(realIndicators.total.per_capita_buy ?? 0).toFixed(1)} م.تومان
                  </span>
                </div>
                {/* Net Real % */}
                <div className="flex items-center justify-between py-2 border-b border-surface-800/50">
                  <span className="text-xs text-surface-400">خالص خرید حقیقی</span>
                  <span className={`text-sm font-black ${(realIndicators.total.net_real_pct ?? 0) >= 0 ? "text-accent-cyan" : "text-accent-rose"}`}>
                    {(realIndicators.total.net_real_pct ?? 0).toFixed(1)}%
                  </span>
                </div>
                {/* Net Real Billion */}
                <div className="flex items-center justify-between py-2 border-b border-surface-800/50">
                  <span className="text-xs text-surface-400">خالص خرید (همت)</span>
                  <span className={`text-sm font-black ${(realIndicators.total.net_real_billion ?? 0) >= 0 ? "text-accent-violet" : "text-accent-rose"}`}>
                    {(realIndicators.total.net_real_billion ?? 0).toFixed(1)} همت
                  </span>
                </div>
                {/* Bourse vs Farabourse comparison */}
                <div className="mt-3 pt-3 border-t border-surface-800/50">
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div>
                      <div className="text-[10px] text-surface-500 mb-1">بورس</div>
                      <div className={`text-sm font-bold ${(realIndicators.bourse?.demand_pressure ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        فشار: {(realIndicators.bourse?.demand_pressure ?? 0).toFixed(1)}%
                      </div>
                      <div className="text-[10px] text-surface-500">
                        خالص: {(realIndicators.bourse?.net_real_pct ?? 0).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-surface-500 mb-1">فرابورس</div>
                      <div className={`text-sm font-bold ${(realIndicators.farabourse?.demand_pressure ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        فشار: {(realIndicators.farabourse?.demand_pressure ?? 0).toFixed(1)}%
                      </div>
                      <div className="text-[10px] text-surface-500">
                        خالص: {(realIndicators.farabourse?.net_real_pct ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full py-6">
                <div className="relative w-32 h-32">
                  <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="12" />
                    <circle
                      cx="50" cy="50" r="40" fill="none"
                      stroke="#10b981"
                      strokeWidth="12"
                      strokeDasharray={`${hasBreadth ? (gainersCount / totalSymbols) * 251.2 : 0} 251.2`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-xl font-black text-surface-100">{gainersCount + losersCount}</span>
                    <span className="text-[9px] text-surface-500">کل نمادها</span>
                  </div>
                </div>
                <div className="flex gap-4 mt-3">
                  <div className="text-center">
                    <div className="text-sm font-black text-accent-emerald">{gainersCount}</div>
                    <div className="text-[9px] text-surface-500">صعودی</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-black text-accent-rose">{losersCount}</div>
                    <div className="text-[9px] text-surface-500">نزولی</div>
                  </div>
                </div>
              </div>
            )}
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
            {news.map((item, i) => {
              const itemKey = (item as any).id || `${item.symbol || i}-${i}`;
              return (
                <a
                  key={itemKey}
                  href={item.url || "#"}
                  target={item.url ? "_blank" : undefined}
                  rel={item.url ? "noopener noreferrer" : undefined}
                  className="flex items-start gap-2 py-2 border-b border-surface-800/50 last:border-0 hover:bg-surface-800/30 rounded px-1 transition-colors"
                >
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
                </a>
              );
            })}
            <Link href={realNews && realNews.length > 0 ? "/news" : "/codal"} className="block text-center text-xs text-primary-400 hover:text-primary-300 py-2">
              لیست کامل {realNews && realNews.length > 0 ? "اخبار" : "اطلاعیه‌ها"} ←
            </Link>
          </div>
        </Card>

        {/* Top Active */}
        <Card
          title="فعال‌ترین نمادها"
          actions={<Link href="/markets?tab=active" className="text-xs text-primary-400 hover:text-primary-300">مشاهده همه ←</Link>}
        >
          <div className="overflow-hidden max-h-[300px]">
            {active.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-800">
                    <th className="py-1.5 text-right font-normal">#</th>
                    <th className="py-1.5 text-right font-normal">نماد</th>
                    <th className="py-1.5 text-right font-normal">قیمت</th>
                    <th className="py-1.5 text-right font-normal">تغییر</th>
                    <th className="py-1.5 text-right font-normal">حجم</th>
                    <th className="py-1.5 text-right font-normal">ارزش</th>
                  </tr>
                </thead>
                <tbody>
                  {active.slice(0, 10).map((item: any, i: number) => (
                    <tr key={item.symbol} className="border-b border-surface-800/50 hover:bg-white/[0.02]">
                      <td className="py-1.5 text-surface-500">{i + 1}</td>
                      <td className="py-1.5">
                        <Link href={`/symbol/${encodeURIComponent(item.symbol)}`} className="text-surface-200 hover:text-primary-300 font-bold">
                          {item.symbol}
                        </Link>
                      </td>
                      <td className="py-1.5 text-surface-300 font-mono">{Number(item.price_last || 0).toLocaleString("fa-IR")}</td>
                      <td className={`py-1.5 font-mono ${(item.price_change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {(item.price_change_pct ?? 0) >= 0 ? "+" : ""}{(item.price_change_pct ?? 0).toFixed(2)}%
                      </td>
                      <td className="py-1.5 text-surface-400 font-mono">{fmt(item.volume ?? 0)}</td>
                      <td className="py-1.5 text-surface-400 font-mono">{fmt(item.value ?? 0)}</td>
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
            {currencies.map((c, ci) => (
              <div key={`${c.name}-${ci}`} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
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
            {goldOunce.map((g, gi) => (
              <div key={`${g.name}-${gi}`} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
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
            {coins.map((c, ci) => (
              <div key={`${c.name}-${ci}`} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
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
            {energy.map((e, ei) => (
              <div key={`${e.name}-${ei}`} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
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
            {metals.map((m, mi) => (
              <div key={`${m.name}-${mi}`} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
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
                {financialRatios.map((r, ri) => (
                  <tr key={`${r.label}-${ri}`} className="border-b border-surface-800/50">
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
            {(cryptoData && cryptoData.length > 0 ? cryptoData.map(c => ({
              name: c.name,
              symbol: c.symbol,
              price: c.price_usd || 0,
              change_pct: c.change_percent || 0,
            })) : [
              { name: "بیت کوین", symbol: "BTC", price: 62_650, change_pct: 0 },
              { name: "اتریوم", symbol: "ETH", price: 1_760, change_pct: 0.5 },
              { name: "تتر", symbol: "USDT", price: 1_754_350, change_pct: 0.2 },
              { name: "دش", symbol: "DASH", price: 36, change_pct: -0.6 },
              { name: "ریپل", symbol: "XRP", price: 1.13, change_pct: -0.9 },
              { name: "لایت کوین", symbol: "LTC", price: 44.8, change_pct: 0.4 },
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
