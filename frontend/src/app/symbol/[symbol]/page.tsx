"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AuditBadge } from "@/components/AuditBadge";
import { DonutChart } from "@/components/DonutChart";
import { EmptyTab } from "@/components/EmptyTab";
import { IndicatorBox } from "@/components/IndicatorBox";
import { InfoRow } from "@/components/InfoRow";
import { MetricBox } from "@/components/MetricBox";
import { RealLegalCard } from "@/components/RealLegalCard";
import { StatRow } from "@/components/StatRow";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import { apiGet, extractArray, extractItems } from "@/lib/api";
import { formatDateShamsi, formatTime } from "@/lib/dates";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------------
interface CompanyProfile {
  symbol: string; name: string; industry: string;
  eps: number; pe: number; group_pe?: number;
  ps_ratio?: number;
  market_cap: number; shares_count: number;
  free_float_pct?: number;
  // Price thresholds
  price_lowest_allowed?: number;
  price_highest_allowed?: number;
  price_min?: number;
  price_max?: number;
  price_yesterday?: number;
  price_last?: number;
  price_close?: number;
  // Status & market
  state?: string;
  market?: string;
  board?: string;
  sub_sector?: string;
  // Trade data
  trade_volume?: number;
  trade_value?: number;
  trade_count?: number;
  base_volume?: number;
  // Real/Legal trade data
  buy_real_count?: number;
  buy_legal_count?: number;
  sell_real_count?: number;
  sell_legal_count?: number;
  buy_real_volume?: number;
  buy_legal_volume?: number;
  sell_real_volume?: number;
  sell_legal_volume?: number;
  // Static
  established: number; ceo: string; board_chairman: string;
}

interface QuoteData {
  symbol: string; price_close: number; price_change: number;
  price_change_pct: number; volume: number; value: number;
  price_high: number; price_low: number; price_open: number;
  price_yesterday: number; date: string;
}

interface CodalReport {
  id: string; symbol: string; report_type: string;
  fiscal_year: string; period: string; publish_date: string;
  summary: { text?: string } | string; attachment_url: string;
}

interface BrsapiCodalItem {
  id?: number; symbol: string; company_name: string;
  title: string; code: string; date_title: string;
  date_send: string; time_send: string;
  date_publish: string; time_publish: string;
  link: string; link_pdf: string;
  link_excel: string; link_attachment: string;
  audit_status: string;
}

interface SignalItem {
  id: string; symbol: string; signal_type: string;
  direction: string; confidence: number; description: string; date: string;
}

interface NewsItem {
  id: string; symbol: string; title: string;
  source: string; published_at: string; summary: string;
  url: string;
}

interface InsiderTrade {
  date: string; person: string; position: string;
  type: "buy" | "sell"; volume: number; price: number; value: number;
}

interface IntradayTrade {
  id: number; symbol: string; row: number | null;
  time: string; volume: number; price: number;
  canceled: boolean | null; trade_date: string; created_at: string;
}

interface MajorHolder {
  name: string; shares: number; percentage: number; type: string;
}

interface DividendRecord {
  date: string; cash_per_share: number; total_payout: number; type: string; meeting: string;
}

interface FinancialQuarter {
  period: string; revenue: number; cost: number; gross_profit: number;
  operating_profit: number; net_profit: number; eps: number;
}

// ------ Tabs ---------------------------------------------------------------------------------------------------------------------------------------------------------
const TABS = [
  { key: "overview", label: "نمای کلی", icon: "📊" },
  { key: "price", label: "قیمت و تکنیکال", icon: "📈" },
  { key: "codal", label: "گزارش‌های کدال", icon: "📋" },
  { key: "fundamental", label: "بنیادی", icon: "💰" },
  { key: "signals", label: "سیگنال‌ها", icon: "📡" },
  { key: "news", label: "اخبار", icon: "📰" },
  { key: "holders", label: "سهامداران", icon: "👥" },
  { key: "trades", label: "ریز معاملات", icon: "🔄" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

// ------ Helpers ------------------------------------------------------------------------------------------------------------------------------------------------
const FALLBACK_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر"];

async function searchSymbols(query: string): Promise<string[]> {
  if (!query) return FALLBACK_SYMBOLS;
  try {
    const res = await apiGet<{ success: boolean; data: { items: { symbol: string }[] } }>(`/instruments/search?q=${encodeURIComponent(query)}&page_size=20`);
    const items = extractItems<{ symbol: string }>(res);
    if (items.length > 0) return items.map(i => i.symbol);
  } catch {}
  // Fallback: filter local list
  return FALLBACK_SYMBOLS.filter(s => s.includes(query));
}

function formatCurrency(val: number | null | undefined): string {
  if (val == null) return "—";
  if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(1) + "T";
  if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(1) + "B";
  if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(1) + "M";
  if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(0) + "K";
  return val.toLocaleString();
}

function formatPct(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "—", color: "text-surface-400" };
  const fixed = val.toFixed(2);
  if (val > 0) return { text: `+${fixed}%`, color: "text-accent-emerald" };
  if (val < 0) return { text: `${fixed}%`, color: "text-accent-rose" };
  return { text: "0.00%", color: "text-surface-400" };
}

// ------ Mini Chart (sparkline) ---------------------------------------------------------------------------------------------------
function Sparkline({ data, width = 120, height = 40, color = "#22c55e" }: { data: number[]; width?: number; height?: number; color?: string }) {
  if (!data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height}`).join(" ");
  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function generateSparkline(seed: number, count = 30) {
  let v = seed;
  const out: number[] = [];
  for (let i = 0; i < count; i++) {
    v += (Math.random() - 0.48) * 0.05 * v;
    v = Math.max(v, seed * 0.7);
    out.push(v);
  }
  return out;
}

function deriveQuoteFromProfile(p: CompanyProfile): QuoteData {
  const close = p.price_close ?? p.price_last ?? 0;
  const yesterday = p.price_yesterday ?? close;
  const change = close - yesterday;
  const changePct = yesterday > 0 ? change / yesterday : 0;
  return {
    symbol: p.symbol,
    price_close: close,
    price_change: change,
    price_change_pct: changePct,
    volume: p.trade_volume ?? 0,
    value: p.trade_value ?? 0,
    price_high: p.price_max ?? close,
    price_low: p.price_min ?? close,
    price_open: close,
    price_yesterday: yesterday,
    date: "",
  };
}

// ------ Main Component --------------------------------------------------------------------------------------------------------------------------- ---------------------------------------------------------------------------------------------------------------------------
export default function SymbolPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = (params?.symbol as string) || "فولاد";
  const decodedSymbol = decodeURIComponent(symbol);

  const [tab, setTab] = useState<TabKey>("overview");
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [codal, setCodal] = useState<CodalReport[]>([]);
  const [brsapiCodal, setBrsapiCodal] = useState<BrsapiCodalItem[]>([]);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [holders, setHolders] = useState<MajorHolder[]>([]);
  const [insider, setInsider] = useState<InsiderTrade[]>([]);
  const [dividends, setDividends] = useState<DividendRecord[]>([]);
  const [financials, setFinancials] = useState<FinancialQuarter[]>([]);
  const [trades, setTrades] = useState<IntradayTrade[]>([]);
  const [sparkHistory, setSparkHistory] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, cRes, bRes, sRes, nRes, hRes, iRes, dRes, fRes, tRes, sparkRes] = await Promise.allSettled([
        apiGet<{ success: boolean; data: CompanyProfile }>(`/codal/${decodedSymbol}/profile`),
        apiGet<{ success: boolean; data: { items: CodalReport[] } }>(`/codal/${decodedSymbol}?page_size=20`),
        apiGet<{ success: boolean; data: { announcements: BrsapiCodalItem[] } }>(`/codal/brsapi-search?symbol=${encodeURIComponent(decodedSymbol)}&page=1`),
        apiGet<{ success: boolean; data: { items: SignalItem[] } }>(`/signals/${encodeURIComponent(decodedSymbol)}?page_size=20`),
        apiGet<{ success: boolean; data: { items: NewsItem[] } }>(`/news/symbol/${encodeURIComponent(decodedSymbol)}?page_size=10`),
        apiGet<{ success: boolean; data: { holders: MajorHolder[] } }>(`/codal/${decodedSymbol}/holders`),
        apiGet<{ success: boolean; data: { trades: InsiderTrade[] } }>(`/codal/${decodedSymbol}/insider`),
        apiGet<{ success: boolean; data: { dividends: DividendRecord[] } }>(`/codal/${decodedSymbol}/dividends`),
        apiGet<{ success: boolean; data: { quarters: FinancialQuarter[] } }>(`/codal/${decodedSymbol}/financials`),
        apiGet<{ success: boolean; data: { items: IntradayTrade[] } }>(`/trades/${encodeURIComponent(decodedSymbol)}?limit=200`),
        // Fetch real OHLCV data for sparkline
        apiGet<{ success: boolean; data: { date: string; close: number }[] }>(
          `/market/history/${encodeURIComponent(decodedSymbol)}?limit=60`
        ),
      ]);

      if (pRes.status === "fulfilled" && pRes.value?.data) setProfile(pRes.value.data);
      if (cRes.status === "fulfilled" && cRes.value?.data?.items) setCodal(cRes.value.data.items);
      if (bRes.status === "fulfilled" && bRes.value?.data?.announcements) setBrsapiCodal(bRes.value.data.announcements);
      if (sRes.status === "fulfilled") setSignals(extractItems(sRes.value));
      if (nRes.status === "fulfilled") setNews(extractItems(nRes.value));
      if (hRes.status === "fulfilled" && hRes.value?.data?.holders) setHolders(hRes.value.data.holders);
      if (iRes.status === "fulfilled" && iRes.value?.data?.trades) setInsider(iRes.value.data.trades);
      if (dRes.status === "fulfilled" && dRes.value?.data?.dividends) setDividends(dRes.value.data.dividends);
      if (fRes.status === "fulfilled" && fRes.value?.data?.quarters) setFinancials(fRes.value.data.quarters);
      if (tRes.status === "fulfilled") setTrades(extractItems(tRes.value));

      // Real sparkline data from market history API
      if (sparkRes.status === "fulfilled" && sparkRes.value?.success && Array.isArray(sparkRes.value.data)) {
        const closes = sparkRes.value.data.map((d: any) => d.close || 0);
        if (closes.length > 0) {
          setSparkHistory(closes.reverse()); // chronological order for sparkline
        }
      }
    } catch {}
    setLoading(false);
  }, [decodedSymbol]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Derive quote data from profile (no separate quote API needed)
  const derivedQuote = useMemo(() => profile ? deriveQuoteFromProfile(profile) : null, [profile]);
  const displayQuote = quote ?? derivedQuote;

  // Enriched display values
  const displayState = profile?.state;

  const sparkData = useMemo(() => {
    if (sparkHistory.length > 0) return sparkHistory;
    // Fallback to generated data if no real data available
    return displayQuote ? generateSparkline(displayQuote.price_close, 40) : [];
  }, [sparkHistory, displayQuote?.price_close]);
  const pct = displayQuote ? formatPct(displayQuote.price_change_pct) : { text: "—", color: "text-surface-500" };

  if (loading) {
    return (
      <AppLayout title={"جزئیات " + decodedSymbol} subtitle="در حال بارگذاری...">
        <div className="max-w-7xl mx-auto space-y-4">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </AppLayout>
    );
  }

  const stateColor = profile?.state === "مجاز" ? "bg-accent-emerald/15 text-accent-emerald" :
    profile?.state === "ممنوع" || profile?.state === "متوقف" ? "bg-accent-rose/15 text-accent-rose" :
    "bg-surface-700 text-surface-400";

  return (
    <AppLayout title={profile?.name || decodedSymbol} subtitle={profile ? "نماد: " + decodedSymbol + " • " + profile.industry : decodedSymbol}>
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ------ Header Bar ------------------------------------------------------------------------------------------------------ */}
        {displayQuote ? (
          <div className="glass-card p-5 flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <SymbolSelector value={decodedSymbol} onChange={(s) => router.push(`/symbol/${s}`)} />
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-black text-surface-100 font-mono">{displayQuote.price_close.toLocaleString()}</span>
                  <span className={`text-lg font-bold font-mono ${pct.color}`}>{pct.text}</span>
                  {displayState && (
                    <span className={`text-xs font-bold px-2 py-1 rounded-lg ${stateColor}`}>{displayState}</span>
                  )}
                </div>
                <div className="flex items-center gap-4 mt-1 text-xs text-surface-500">
                  <span>حجم: {formatCurrency(displayQuote.volume)}</span>
                  <span>ارزش: {formatCurrency(displayQuote.value)} ریال</span>
                  <span>دیروز: {displayQuote.price_yesterday.toLocaleString()}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <Sparkline data={sparkData} width={150} height={40} color={displayQuote.price_change_pct >= 0 ? "#22c55e" : "#ef4444"} />
              <div className="grid grid-cols-3 gap-4 text-center">
                <div><div className="text-xs text-surface-500">بالا</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_high.toLocaleString()}</div></div>
                <div><div className="text-xs text-surface-500">پایین</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_low.toLocaleString()}</div></div>
                <div><div className="text-xs text-surface-500">باز</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_open.toLocaleString()}</div></div>
              </div>
            </div>
          </div>
        ) : (
          <div className="glass-card p-5 flex items-center gap-4">
            <SymbolSelector value={decodedSymbol} onChange={(s) => router.push(`/symbol/${s}`)} />
            {!loading && (
              <span className="text-sm text-surface-500">داده‌های قیمتی در دسترس نیست</span>
            )}
          </div>
        )}

        {/* ------ Tab Navigation ------------------------------------------------------------------------------------------ */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`shrink-0 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                tab === t.key ? "bg-primary-600 text-white shadow-lg" : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
              }`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* ------ Tab Content --------------------------------------------------------------------------------------------------- */}
        {tab === "overview" && <OverviewTab profile={profile} quote={displayQuote ?? null} codal={codal} signals={signals} news={news} holders={holders} financials={financials} />}
        {tab === "price" && (displayQuote ? <PriceTab symbol={decodedSymbol} quote={displayQuote} /> : <EmptyTab message="داده‌های قیمتی برای نمایش وجود ندارد" />)}
        {tab === "codal" && <CodalTab codal={codal} brsapiCodal={brsapiCodal} symbol={decodedSymbol} />}
        {tab === "fundamental" && <FundamentalTab financials={financials} dividends={dividends} profile={profile} />}
        {tab === "signals" && <SignalsTab signals={signals} symbol={decodedSymbol} />}
        {tab === "news" && <NewsTab news={news} symbol={decodedSymbol} />}
        {tab === "holders" && <HoldersTab holders={holders} insider={insider} />}
        {tab === "trades" && <TradesTab trades={trades} symbol={decodedSymbol} />}

        {/* ------ Quick Links --------------------------------------------------------------------------------------------------- */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href={`/instruments`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← همه نمادها</Link>
          <Link href={`/codal`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">کدال</Link>
          <Link href={`/analysis`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">تحلیل بازار</Link>
          <Link href={`/smart-money?symbol=${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">پول هوشمند</Link>
          <Link href={`/brsapi/history/${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">📈 تاریخچه قیمت</Link>
        </div>
      </div>
    </AppLayout>
  );
}

// ═══════════════════════════════════════════════════════════════
// Tab Components
// ═══════════════════════════════════════════════════════════════

function PriceThresholdRange({ low, high, current }: { low?: number; high?: number; current: number }) {
  if (low == null || high == null || high <= low) return null;
  const rangePct = ((current - low) / (high - low)) * 100;
  const clampedPct = Math.max(5, Math.min(95, rangePct));
  const distToFloor = rangePct;
  const distToCeiling = 100 - rangePct;
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs">
        <span className="text-accent-emerald font-mono">{low.toLocaleString()}</span>
        <span className="text-surface-500">آستانه مجاز</span>
        <span className="text-accent-rose font-mono">{high.toLocaleString()}</span>
      </div>
      <div className="relative h-1.5 bg-gradient-to-r from-red-500/40 via-purple-500/40 to-blue-500/40 rounded-full" dir="ltr">
        <div className="group absolute top-1/2 -translate-y-1/2" style={{ left: `${clampedPct}%` }}>
          <div className="w-3 h-3 rounded-full bg-surface-50 border-2 border-primary-500 shadow-lg transition-all group-hover:scale-150 group-hover:shadow-primary-500/50 cursor-crosshair" />
          {/* Tooltip */}
          <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-44 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50">
            <div className="bg-surface-900 border border-surface-700 rounded-xl px-3 py-2.5 shadow-2xl text-xs text-right">
              <div className="flex justify-between gap-3">
                <span className="text-surface-500">فاصله از کف:</span>
                <span className="font-mono font-bold text-accent-emerald">{distToFloor.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3 mt-1">
                <span className="text-surface-500">فاصله از سقف:</span>
                <span className="font-mono font-bold text-accent-rose">{distToCeiling.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3 mt-1 pt-1.5 border-t border-surface-700">
                <span className="text-surface-500">موقعیت:</span>
                <span className="font-mono text-primary-300">{rangePct.toFixed(1)}%</span>
              </div>
            </div>
            {/* Arrow */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-surface-700" />
          </div>
        </div>
      </div>
      <div className="text-center text-xs text-surface-500">
        قیمت فعلی: <span className="font-mono text-surface-200">{current.toLocaleString()}</span>
        {' '}•{' '}
        <span className={rangePct <= 25 ? "text-accent-emerald" : rangePct >= 75 ? "text-accent-rose" : "text-surface-300"}>
          {Math.round(rangePct < 50 ? rangePct : 100 - rangePct)}% فاصله از {rangePct < 50 ? "کف" : "سقف"}
        </span>
      </div>
    </div>
  );
}

// ------ Fundamental Comparison Card ------------------------------------------------------------------------------
function FundamentalCompareCard({ currentSymbol, currentProfile }: { currentSymbol: string; currentProfile: CompanyProfile }) {
  const [compareWith, setCompareWith] = useState("");
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareQuery, setCompareQuery] = useState("");
  const [compareResults, setCompareResults] = useState<string[]>(FALLBACK_SYMBOLS.filter(s => s !== currentSymbol));
  const [targetProfile, setTargetProfile] = useState<CompanyProfile | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  // Fetch comparison data
  useEffect(() => {
    if (!compareWith) { setTargetProfile(null); return; }
    let cancelled = false;
    setLoadingCompare(true);
    apiGet<{ success: boolean; data: CompanyProfile }>(`/codal/${compareWith}/profile`)
      .then(res => { if (!cancelled && res?.data) setTargetProfile(res.data); })
      .catch(() => { if (!cancelled) setTargetProfile(null); })
      .finally(() => { if (!cancelled) setLoadingCompare(false); });
    return () => { cancelled = true; };
  }, [compareWith]);

  // Search symbols for the comparison selector
  useEffect(() => {
    if (!compareOpen) return;
    let cancelled = false;
    searchSymbols(compareQuery).then(symbols => {
      if (!cancelled) setCompareResults(symbols.filter(s => s !== currentSymbol));
    });
    return () => { cancelled = true; };
  }, [compareQuery, compareOpen, currentSymbol]);

  const metrics: { label: string; ours: string; theirs: string | null; color?: "green" | "red" }[] = [
    {
      label: "قیمت",
      ours: currentProfile.price_last?.toLocaleString() ?? "—",
      theirs: targetProfile?.price_last?.toLocaleString() ?? null,
    },
    {
      label: "ارزش بازار",
      ours: formatCurrency(currentProfile.market_cap),
      theirs: targetProfile ? formatCurrency(targetProfile.market_cap) : null,
    },
    {
      label: "P/E",
      ours: currentProfile.pe.toFixed(1),
      theirs: targetProfile ? targetProfile.pe.toFixed(1) : null,
      color: currentProfile.pe < (targetProfile?.pe ?? Infinity) ? "green" : currentProfile.pe > (targetProfile?.pe ?? 0) ? "red" : undefined,
    },
    {
      label: "EPS",
      ours: currentProfile.eps.toLocaleString(),
      theirs: targetProfile ? targetProfile.eps.toLocaleString() : null,
      color: currentProfile.eps > (targetProfile?.eps ?? -Infinity) ? "green" : currentProfile.eps < (targetProfile?.eps ?? Infinity) ? "red" : undefined,
    },
    {
      label: "P/S",
      ours: currentProfile.ps_ratio != null && currentProfile.ps_ratio !== 0 ? currentProfile.ps_ratio.toFixed(2) : "—",
      theirs: targetProfile?.ps_ratio != null && targetProfile.ps_ratio !== 0 ? targetProfile.ps_ratio.toFixed(2) : null,
    },
    {
      label: "P/E گروه",
      ours: currentProfile.group_pe != null && currentProfile.group_pe !== 0 ? currentProfile.group_pe.toFixed(1) : "—",
      theirs: targetProfile?.group_pe != null && targetProfile.group_pe !== 0 ? targetProfile.group_pe.toFixed(1) : null,
    },
    {
      label: "شناوری",
      ours: currentProfile.free_float_pct != null ? `${currentProfile.free_float_pct.toFixed(1)}%` : "—",
      theirs: targetProfile?.free_float_pct != null ? `${targetProfile.free_float_pct.toFixed(1)}%` : null,
    },
    {
      label: "تعداد سهام",
      ours: formatCurrency(currentProfile.shares_count),
      theirs: targetProfile ? formatCurrency(targetProfile.shares_count) : null,
    },
  ];

  return (
    <Card title="⚖️ مقایسه بنیادی" className="lg:col-span-full">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-surface-400">مقایسه با:</span>
        <div className="relative">
          <input
            value={compareQuery}
            onChange={(e) => setCompareQuery(e.target.value)}
            onFocus={() => setCompareOpen(true)}
            placeholder="جستجوی نماد..."
            className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-sm text-white w-36 outline-none focus:border-primary-500"
          />
          {compareOpen && compareResults.length > 0 && (
            <div className="absolute top-full mt-1 right-0 z-50 bg-surface-800 border border-surface-700 rounded-lg shadow-2xl w-36 overflow-hidden">
              {compareResults.map((s) => (
                <button
                  key={s}
                  onClick={() => { setCompareWith(s); setCompareQuery(s); setCompareOpen(false); }}
                  className={`w-full text-right px-3 py-1.5 text-sm hover:bg-surface-700 transition-colors ${s === compareWith ? "bg-primary-600/20 text-primary-300" : "text-surface-200"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        {loadingCompare && <span className="text-xs text-surface-500">در حال بارگذاری...</span>}
        {compareWith && !loadingCompare && targetProfile && (
          <span className="text-xs text-accent-emerald">✓ {targetProfile.name || compareWith}</span>
        )}
        {compareWith && !loadingCompare && !targetProfile && (
          <span className="text-xs text-accent-rose">✗ اطلاعات در دسترس نیست</span>
        )}
      </div>

      {compareWith && targetProfile ? (
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700 text-xs">
                <th className="pb-2 px-3 font-medium">معیار</th>
                <th className="pb-2 px-3 font-medium text-center">{currentSymbol}</th>
                <th className="pb-2 px-3 font-medium text-center">{compareWith}</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, mi) => (
                <tr key={`${m.label}-${mi}`} className="border-b border-surface-800/50 hover:bg-white/5">
                  <td className="py-2.5 px-3 text-surface-500">{m.label}</td>
                  <td className={`py-2.5 px-3 font-mono font-bold text-center ${m.color === "green" ? "text-accent-emerald" : m.color === "red" ? "text-accent-rose" : "text-surface-200"}`}>
                    {m.ours}
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-center text-surface-200">
                    {m.theirs ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-surface-500 text-sm text-center py-4">
          {compareWith && !targetProfile ? "داده‌ای برای مقایسه یافت نشد" : "یک نماد را انتخاب کنید تا مقایسه بنیادی نمایش داده شود"}
        </p>
      )}
    </Card>
  );
}

function OverviewTab({ profile, quote, codal, signals, news, holders, financials }: {
  profile: CompanyProfile | null; quote: QuoteData | null; codal: CodalReport[];
  signals: SignalItem[]; news: NewsItem[]; holders: MajorHolder[]; financials: FinancialQuarter[];
}) {
  const lastFin = financials[0];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      {/* Company Info */}
      <Card title="🏢 اطلاعات شرکت" className="lg:col-span-1">
        {profile ? (
          <div className="space-y-3 text-sm">
            <InfoRow label="نام کامل" value={profile.name} />
            <InfoRow label="صنعت" value={profile.industry} />
            {profile.sub_sector && <InfoRow label="زیرگروه" value={profile.sub_sector} />}
            <InfoRow label="مدیرعامل" value={profile.ceo} />
            <InfoRow label="رئیس هیئت مدیره" value={profile.board_chairman} />
            <InfoRow label="سال تأسیس" value={String(profile.established)} />
            <InfoRow label="تعداد سهام" value={formatCurrency(profile.shares_count)} />
            <InfoRow label="حجم مبنا" value={profile.base_volume ? profile.base_volume.toLocaleString() : "-"} />
            <InfoRow label="ارزش بازار" value={formatCurrency(profile.market_cap) + " ریال"} />
            {profile.free_float_pct != null && profile.free_float_pct > 0 && (
              <InfoRow label="درصد شناوری" value={`${profile.free_float_pct.toFixed(1)}%`} />
            )}
            <InfoRow label="بازار / تابلو" value={[profile.market, profile.board].filter(Boolean).join(" • ") || "-"} />
          </div>
        ) : (
          <p className="text-surface-500 text-sm">اطلاعات شرکت در دسترس نیست</p>
        )}
      </Card>

      {/* Key Metrics */}
      <Card title="📊 معیارهای کلیدی">
        {profile ? (
          <div className="grid grid-cols-2 gap-4 text-center">
            <MetricBox label="EPS" value={profile.eps.toLocaleString()} unit="ریال" />
            <MetricBox label="P/E" value={profile.pe.toFixed(1)} unit="×" />
            {profile.group_pe != null && profile.group_pe !== 0 && (
              <MetricBox label="P/E گروه" value={profile.group_pe.toFixed(1)} unit="×" />
            )}
            <MetricBox label="شناوری" value={profile.free_float_pct != null ? `${profile.free_float_pct.toFixed(1)}%` : "-"} unit="" />
            <MetricBox label="ارزش بازار" value={formatCurrency(profile.market_cap)} unit="ریال" />
            <MetricBox label="قیمت پایانی" value={quote?.price_close?.toLocaleString() ?? "—"} unit="ریال" color="text-primary-300" />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 text-center">
            <MetricBox label="قیمت" value={quote?.price_close?.toLocaleString() ?? "—"} unit="ریال" color="text-primary-300" />
            <MetricBox label="حجم" value={quote ? formatCurrency(quote.volume) : "—"} unit="سهم" />
            <MetricBox label="ارزش" value={quote ? formatCurrency(quote.value) : "—"} unit="ریال" />
            <MetricBox label="تغییر" value={`${(quote?.price_change_pct ?? 0) >= 0 ? "+" : ""}${(quote?.price_change_pct ?? 0).toFixed(2)}%`} color={(quote?.price_change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
          </div>
        )}
      </Card>

      {/* Quick Stats */}
      <Card title="⏱ خلاصه">
        <div className="space-y-4">
          <StatRow icon="📋" label="گزارش‌های کدال" value={codal.length + " گزارش"} />
          <StatRow icon="📡" label="سیگنال‌ها" value={signals.length + " سیگنال"} />
          <StatRow icon="📰" label="اخبار" value={news.length + " خبر"} />
          <StatRow icon="👥" label="سهامداران عمده" value={holders.length + " سهامدار"} />
          {lastFin && <StatRow icon="💰" label="آخرین EPS" value={lastFin.eps.toLocaleString()} />}
          {profile?.base_volume != null && profile.base_volume > 0 && (
            <StatRow icon="📦" label="حجم مبنا" value={profile.base_volume.toLocaleString()} />
          )}
        </div>
      </Card>

      {/* Fundamental Summary */}
      <Card title="📈 خلاصه بنیادی" className="lg:col-span-1">
        {profile ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 text-center">
              <MetricBox label="P/E" value={profile.pe.toFixed(1)} unit="×" />
              <MetricBox label="P/S" value={profile.ps_ratio != null && profile.ps_ratio !== 0 ? profile.ps_ratio.toFixed(2) : "—"} unit="" />
            </div>
            <div className="grid grid-cols-2 gap-3 text-center">
              <MetricBox label="EPS" value={profile.eps.toLocaleString()} unit="ریال" color={profile.eps >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
              <MetricBox label="P/E گروه" value={profile.group_pe != null && profile.group_pe !== 0 ? profile.group_pe.toFixed(1) : "—"} unit="×" />
            </div>
          </div>
        ) : (
          <p className="text-surface-500 text-sm">داده‌های بنیادی در دسترس نیست</p>
        )}
      </Card>

      {/* Price Thresholds */}
      {profile?.price_lowest_allowed != null && profile?.price_highest_allowed != null && (
        <Card title="🎯 آستانه مجاز قیمت" className="lg:col-span-1">
          <PriceThresholdRange low={profile.price_lowest_allowed} high={profile.price_highest_allowed} current={quote?.price_close ?? 0} />
          <div className="grid grid-cols-2 gap-3 mt-4 text-center">
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">بالاترین قیمت روز</p>
              <p className="font-mono font-bold text-accent-rose">{(profile.price_max ?? quote?.price_high ?? 0).toLocaleString()}</p>
            </div>
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">پایین‌ترین قیمت روز</p>
              <p className="font-mono font-bold text-accent-emerald">{(profile.price_min ?? quote?.price_low ?? 0).toLocaleString()}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3 text-center">
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">EPS</p>
              <p className="font-mono font-bold text-primary-300">{profile.eps.toLocaleString()}</p>
              <p className="text-xs text-surface-600 mt-0.5">ریال</p>
            </div>
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">P/E گروه</p>
              <p className={`font-mono font-bold ${profile.group_pe != null && profile.group_pe !== 0 ? "text-surface-100" : "text-surface-600"}`}>
                {profile.group_pe != null && profile.group_pe !== 0 ? profile.group_pe.toFixed(1) : "—"}
              </p>
              <p className="text-xs text-surface-600 mt-0.5">×</p>
            </div>
          </div>
        </Card>
      )}

      {/* Latest Codal */}
      <Card title="📋 آخرین گزارش‌های کدال" className="lg:col-span-2">
        {codal.length > 0 ? (
          <div className="space-y-2">
            {codal.slice(0, 5).map((r) => (
              <div key={r.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-surface-200 truncate">{typeof r.summary === "string" ? r.summary : r.summary?.text || r.report_type}</p>
                  <p className="text-xs text-surface-500 mt-0.5">{r.report_type} • {r.fiscal_year} • {r.period}</p>
                </div>
                <span className="text-xs text-surface-500 shrink-0 mx-3">{r.publish_date}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-surface-500 text-sm">گزارشی یافت نشد</p>}
      </Card>

      {/* Real/Legal Summary */}
      {profile && (profile.buy_real_volume != null || profile.buy_legal_volume != null) && (
        <Card title="🧑‍💼 معاملات حقیقی/حقوقی" className="lg:col-span-1">
          <RealLegalCard data={profile} />
        </Card>
      )}

      {/* Latest Signals */}
      <Card title="📡 آخرین سیگنال‌ها">
        {signals.length > 0 ? (
          <div className="space-y-2">
            {signals.slice(0, 5).map((s) => (
              <div key={s.id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-800/50">
                <div>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    s.direction === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                    s.direction === "sell" ? "bg-accent-rose/15 text-accent-rose" : "bg-accent-amber/15 text-accent-amber"
                  }`}>{s.signal_type || s.direction}</span>
                  <p className="text-xs text-surface-400 mt-1">{s.description}</p>
                </div>
                <span className="text-xs text-surface-600">{s.date}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-surface-500 text-sm">سیگنالی یافت نشد</p>}
      </Card>

      {/* Fundamental Comparison */}
      {profile && <FundamentalCompareCard currentSymbol={profile.symbol} currentProfile={profile} />}

      {/* Latest News */}
      <Card title="📰 آخرین اخبار" className="lg:col-span-full">
        {news.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {news.slice(0, 4).map((n, i) => (
              <a
                key={n.id || `news-${i}`}
                href={n.url || "#"}
                target={n.url ? "_blank" : undefined}
                rel={n.url ? "noopener noreferrer" : undefined}
                className="block p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors"
              >
                <p className="text-sm font-medium text-surface-200 line-clamp-2">{n.title}</p>
                <div className="flex items-center justify-between mt-2 text-xs text-surface-500">
                  <span>{n.source}</span>
                  <span>{n.published_at}</span>
                </div>
              </a>
            ))}
          </div>
        ) : <p className="text-surface-500 text-sm">اخباری یافت نشد</p>}
      </Card>
    </div>
  );
}

// ------ Price Tab ---------------------------------------------------------------------------------------------------------------------------------------------
// ------ Indicator parameter constants (outside component to avoid re-creation) ------
const RSI_PARAMS = { period: 14 } as const;
const SMA_PARAMS = { period: 20 } as const;
const MACD_PARAMS = { fast: 12, slow: 26, signal: 9 } as const;

// ------ Helper: fetch indicator last value ------------------------------------------------------
function useLastIndicator(symbol: string, indicator: string, params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams({ indicator, ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) }).toString();
  return useQuery({
    queryKey: ["indicator", symbol, indicator, params],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { values: number[] | Record<string, number[]> } }>(
          `/market/indicator/${encodeURIComponent(symbol)}?${qs}`
        );
        if (res?.success && res.data?.values) return res.data.values;
      } catch {}
      return null;
    },
    enabled: !!symbol,
  });
}

function PriceTab({ symbol, quote }: { symbol: string; quote: QuoteData }) {
  const { data: ohlcv } = useQuery({
    queryKey: ["ohlcv", symbol],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: { date: string; open: number; high: number; low: number; close: number; volume: number }[] }>(
          `/market/history/${encodeURIComponent(symbol)}?limit=200`
        );
        if (res?.success && Array.isArray(res.data)) return res.data;
      } catch {}
      return [];
    },
    enabled: !!symbol,
  });

  // ------ Fetch technical indicators ------------------------------------------------------------------
  const rsiResult = useLastIndicator(symbol, "rsi", RSI_PARAMS);
  const smaResult = useLastIndicator(symbol, "sma", SMA_PARAMS);
  const macdResult = useLastIndicator(symbol, "macd", MACD_PARAMS);

  const rsiLast = useMemo(() => {
    const v = rsiResult.data;
    if (Array.isArray(v) && v.length > 0) return Number(v[v.length - 1]);
    return null;
  }, [rsiResult.data]);

  const smaLast = useMemo(() => {
    const v = smaResult.data;
    if (Array.isArray(v) && v.length > 0) return Math.round(v[v.length - 1]);
    return null;
  }, [smaResult.data]);

  const macdSignal = useMemo(() => {
    const v = macdResult.data;
    if (v && typeof v === "object" && !Array.isArray(v) && Array.isArray(v.macd) && Array.isArray(v.signal) && v.macd.length > 0) {
      const lastMacd = v.macd[v.macd.length - 1];
      const lastSignal = v.signal[v.signal.length - 1];
      if (lastMacd > lastSignal) return { text: "سیگنال خرید", type: "positive" as const };
      if (lastMacd < lastSignal) return { text: "سیگنال فروش", type: "negative" as const };
      return { text: "خنثی", type: "neutral" as const };
    }
    return null;
  }, [macdResult.data]);

  const candleData = useMemo(() => {
    if (ohlcv && ohlcv.length > 0) {
      return ohlcv.map((bar) => ({
        t: bar.date,
        o: bar.open || bar.close,
        h: bar.high || bar.close,
        l: bar.low || bar.close,
        c: bar.close || 0,
        v: bar.volume || 0,
      }));
    }
    // Fallback to random data if API returns nothing
    const base = quote.price_close;
    const bars: { t: string; o: number; h: number; l: number; c: number; v: number }[] = [];
    let price = base * 0.85;
    for (let i = 60; i >= 0; i--) {
      const change = (Math.random() - 0.48) * 0.04;
      const open = price;
      const close = price * (1 + change);
      const high = Math.max(open, close) * (1 + Math.random() * 0.02);
      const low = Math.min(open, close) * (1 - Math.random() * 0.02);
      bars.push({ t: "۱۴۰۳-" + String((i % 12) + 1).padStart(2, "0") + "-" + String((i % 30) + 1).padStart(2, "0"), o: Math.round(open), h: Math.round(high), l: Math.round(low), c: Math.round(close), v: Math.round(1000000 + Math.random() * 10000000) });
      price = close;
    }
    return bars;
  }, [ohlcv, quote.price_close]);

  const minC = Math.min(...candleData.map(b => b.l));
  const maxC = Math.max(...candleData.map(b => b.h));
  const range = maxC - minC || 1;
  const w = 700, h = 300, pad = 20;

  return (
    <div className="space-y-5">
      <Card title="📈 نمودار قیمت (شمعی)">
        <div className="overflow-x-auto">
          <svg width={w} height={h} className="mx-auto">
            {candleData.map((bar, i) => {
              const x = pad + (i / candleData.length) * (w - pad * 2);
              const bodyH = Math.max(1, Math.abs(bar.c - bar.o) / range * (h - pad * 2));
              const y = h - pad - ((Math.max(bar.c, bar.o) - minC) / range * (h - pad * 2));
              const color = bar.c >= bar.o ? "#22c55e" : "#ef4444";
              return (
                <g key={i}>
                  <line x1={x} x2={x} y1={h - pad - ((bar.h - minC) / range * (h - pad * 2))} y2={h - pad - ((bar.l - minC) / range * (h - pad * 2))} stroke={color} strokeWidth="1" />
                  <rect x={x - 3} y={y - bodyH} width={6} height={Math.max(1, bodyH)} fill={color} opacity="0.9" rx="1" />
                </g>
              );
            })}
          </svg>
        </div>
      </Card>

      <Card title="📊 اندیکاتورهای تکنیکال">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
          <IndicatorBox
            label="RSI (14)"
            value={rsiLast != null ? rsiLast.toFixed(1) : "—"}
            unit=""
            type={rsiLast != null ? (rsiLast > 70 ? "negative" : rsiLast < 30 ? "positive" : "neutral") : "neutral"}
          />
          <IndicatorBox
            label="MACD"
            value={macdSignal?.text ?? "—"}
            unit=""
            type={macdSignal?.type ?? "neutral"}
          />
          <IndicatorBox
            label="SMA (20)"
            value={smaLast != null ? smaLast.toLocaleString() : "—"}
            unit="ریال"
            type="neutral"
          />
          <IndicatorBox label="Volume" value={formatCurrency(quote.volume)} unit="" type={quote.price_change_pct > 0 ? "positive" : "negative"} />
        </div>
      </Card>

      <Card title="📉 سطوح حمایت و مقاومت">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-accent-emerald/10 rounded-xl p-3">
            <p className="text-xs text-accent-emerald mb-1">حمایت ۱</p>
            <p className="font-mono font-bold text-accent-emerald">{(quote.price_close * 0.95).toLocaleString()}</p>
          </div>
          <div className="bg-surface-800 rounded-xl p-3">
            <p className="text-xs text-surface-500 mb-1">قیمت فعلی</p>
            <p className="font-mono font-bold text-surface-100">{quote.price_close.toLocaleString()}</p>
          </div>
          <div className="bg-accent-rose/10 rounded-xl p-3">
            <p className="text-xs text-accent-rose mb-1">مقاومت ۱</p>
            <p className="font-mono font-bold text-accent-rose">{(quote.price_close * 1.05).toLocaleString()}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ------ Codal Tab ---------------------------------------------------------------------------------------------------------------------------------------------
function CodalTab({ codal, brsapiCodal, symbol }: { codal: CodalReport[]; brsapiCodal: BrsapiCodalItem[]; symbol: string }) {
  const showBrsapi = brsapiCodal.length > 0;
  const [mode, setMode] = useState<"brsapi" | "local">(showBrsapi ? "brsapi" : "local");
  const [auditFilter, setAuditFilter] = useState("");

  // Audit stats
  const auditedCount = brsapiCodal.filter((a) => a.audit_status === "audited").length;
  const unauditedCount = brsapiCodal.filter((a) => a.audit_status === "unaudited").length;
  const unknownCount = brsapiCodal.length - auditedCount - unauditedCount;

  const auditSlices = [
    { label: "حسابرسی شده", value: auditedCount, color: "#22c55e" },
    { label: "حسابرسی نشده", value: unauditedCount, color: "#f59e0b" },
  ];
  if (unknownCount > 0) {
    auditSlices.push({ label: "نامشخص", value: unknownCount, color: "#6b7280" });
  }

  // Client-side filter for BrsApi announcements
  const filteredBrsapi = auditFilter
    ? brsapiCodal.filter((item) => item.audit_status === auditFilter)
    : brsapiCodal;

  return (
    <div className="space-y-4">
      {/* Mode toggle + Audit filter */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {showBrsapi && (
              <>
                <button
                  onClick={() => setMode("brsapi")}
                  className={`px-3 py-1.5 rounded-lg text-xs ${mode === "brsapi" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}
                >
                  اطلاعیه‌های برخط
                </button>
                <button
                  onClick={() => setMode("local")}
                  className={`px-3 py-1.5 rounded-lg text-xs ${mode === "local" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}
                >
                  گزارش‌های ذخیره‌شده
                </button>
              </>
            )}
          </div>
          {/* Audit filter toggle */}
          {mode === "brsapi" && showBrsapi && (
            <div className="flex gap-1">
              <button
                onClick={() => setAuditFilter(auditFilter === "audited" ? "" : "audited")}
                className={`px-2 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                  auditFilter === "audited"
                    ? "bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30"
                    : "bg-surface-800 text-surface-400 border border-surface-700 hover:text-surface-200"
                }`}
              >
                ✓ حسابرسی شده
              </button>
              <button
                onClick={() => setAuditFilter(auditFilter === "unaudited" ? "" : "unaudited")}
                className={`px-2 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                  auditFilter === "unaudited"
                    ? "bg-accent-amber/20 text-accent-amber border border-accent-amber/30"
                    : "bg-surface-800 text-surface-400 border border-surface-700 hover:text-surface-200"
                }`}
              >
                ! حسابرسی نشده
              </button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          {!showBrsapi && codal.length > 0 && (
            <span className="text-xs text-surface-500 px-2 py-1.5">گزارش‌های ذخیره‌شده</span>
          )}
          <Link href="/codal/import" className="text-xs text-primary-400 hover:text-primary-300 transition-colors">+ ورود اطلاعات</Link>
        </div>
      </div>

      {/* Audit donut chart */}
      {mode === "brsapi" && showBrsapi && brsapiCodal.length > 0 && (
        <div className="glass-card p-4">
          <p className="text-xs text-surface-500 mb-3">وضعیت حسابرسی اطلاعیه‌ها</p>
          <DonutChart
            slices={auditSlices}
            total={brsapiCodal.length}
            size={80}
            centerLabel="اطلاعیه"
          />
        </div>
      )}

      {mode === "brsapi" && showBrsapi ? (
        /* BrsApi rich announcements */
        <div className="space-y-3">
          {filteredBrsapi.length === 0 ? (
            <div className="text-center py-10 text-surface-500">
              <p className="text-3xl mb-2">🔍</p>
              <p className="text-sm">هیچ اطلاعیه‌ای با وضعیت حسابرسی انتخاب‌شده یافت نشد</p>
            </div>
          ) : (
            filteredBrsapi.map((item, i) => (
              <div key={item.id ?? i} className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-surface-100 leading-relaxed line-clamp-2">
                      {item.title || "بدون عنوان"}
                    </h3>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-surface-500 flex-wrap">
                      <span>📅 {formatDateShamsi(item.date_publish)}</span>
                      {item.time_publish && <span>⏰ {formatTime(item.time_publish)}</span>}
                      {item.company_name && <span>🏢 {item.company_name}</span>}
                      <AuditBadge status={item.audit_status} />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 shrink-0">
                    {item.link_pdf && (
                      <a href={item.link_pdf} target="_blank" rel="noopener noreferrer"
                        className="text-xs bg-accent-rose/10 text-accent-rose px-2.5 py-1 rounded-lg hover:bg-accent-rose/20 transition-colors text-center whitespace-nowrap">📄 PDF</a>
                    )}
                    {item.link_excel && (
                      <a href={item.link_excel} target="_blank" rel="noopener noreferrer"
                        className="text-xs bg-accent-emerald/10 text-accent-emerald px-2.5 py-1 rounded-lg hover:bg-accent-emerald/20 transition-colors text-center whitespace-nowrap">📊 Excel</a>
                    )}
                    {!item.link_pdf && !item.link_excel && item.link_attachment && (
                      <a href={item.link_attachment} target="_blank" rel="noopener noreferrer"
                        className="text-xs bg-primary-600/10 text-primary-300 px-2.5 py-1 rounded-lg hover:bg-primary-600/20 transition-colors text-center whitespace-nowrap">🔗 مشاهده</a>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : codal.length > 0 ? (
        /* Local reports */
        <div className="space-y-2">
          {codal.map((r) => (
            <div key={r.id} className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="font-semibold text-surface-100">
                    {typeof r.summary === "string" ? r.summary : r.summary?.text || r.report_type}
                  </h3>
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-surface-500">
                    <span className="bg-surface-700 px-2 py-0.5 rounded">{r.report_type}</span>
                    <span>سال مالی: {r.fiscal_year}</span>
                    <span>دوره: {r.period}</span>
                    <span>تاریخ انتشار: {r.publish_date}</span>
                  </div>
                </div>
                {r.attachment_url && (
                  <a href={r.attachment_url} target="_blank" rel="noopener noreferrer"
                    className="shrink-0 text-xs bg-primary-600/20 text-primary-300 px-3 py-1.5 rounded-lg hover:bg-primary-600/30 transition-colors">مشاهده</a>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-surface-500">
          <p className="text-4xl mb-3">📋</p>
          <p>گزارش کدالی برای {symbol} یافت نشد</p>
          <Link href="/codal/import" className="inline-block mt-3 text-sm text-primary-400 hover:text-primary-300">ورود اطلاعات کدال ←</Link>
        </div>
      )}
    </div>
  );
}

// ------ Fundamental Tab ---------------------------------------------------------------------------------------------------------------------------
function FundamentalTab({ financials, dividends, profile }: { financials: FinancialQuarter[]; dividends: DividendRecord[]; profile: CompanyProfile | null }) {
  return (
    <div className="space-y-5">
      {financials.length > 0 && (
        <Card title="💰 صورت‌های مالی فصلی">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-3">دوره</th>
                  <th className="pb-2 px-3">درآمد</th>
                  <th className="pb-2 px-3">سود ناخالص</th>
                  <th className="pb-2 px-3">سود عملیاتی</th>
                  <th className="pb-2 px-3">سود خالص</th>
                  <th className="pb-2 px-3">EPS</th>
                </tr>
              </thead>
              <tbody>
                {financials.map((q) => (
                  <tr key={q.period} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 px-3 font-mono text-surface-300">{q.period}</td>
                    <td className="py-2.5 px-3 font-mono text-surface-200">{formatCurrency(q.revenue)}</td>
                    <td className="py-2.5 px-3 font-mono text-accent-emerald">{formatCurrency(q.gross_profit)}</td>
                    <td className="py-2.5 px-3 font-mono text-accent-emerald">{formatCurrency(q.operating_profit)}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-accent-emerald">{formatCurrency(q.net_profit)}</td>
                    <td className="py-2.5 px-3 font-mono text-primary-300">{q.eps.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {dividends.length > 0 && (
        <Card title="💸 تاریخچه سود تقسیمی (DPS)">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-3">تاریخ</th>
                  <th className="pb-2 px-3">سود هر سهم</th>
                  <th className="pb-2 px-3">کل پرداختی</th>
                  <th className="pb-2 px-3">نوع</th>
                  <th className="pb-2 px-3">مجمع</th>
                </tr>
              </thead>
              <tbody>
                {dividends.map((d) => (
                  <tr key={d.date} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 px-3 font-mono text-surface-300">{d.date}</td>
                    <td className="py-2.5 px-3 font-mono text-accent-emerald font-bold">{d.cash_per_share.toLocaleString()}</td>
                    <td className="py-2.5 px-3 font-mono text-surface-200">{formatCurrency(d.total_payout)}</td>
                    <td className="py-2.5 px-3">{d.type}</td>
                    <td className="py-2.5 px-3 text-xs text-surface-400">{d.meeting}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {!financials.length && !dividends.length && (
        <div className="text-center py-12 text-surface-500">اطلاعات بنیادی در دسترس نیست</div>
      )}
    </div>
  );
}

// ------ Signals Tab ---------------------------------------------------------------------------------------------------------------------------------------
function SignalsTab({ signals, symbol }: { signals: SignalItem[]; symbol: string }) {
  return (
    <div className="space-y-3">
      {signals.length > 0 ? signals.map((s) => (
        <div key={s.id} className="glass-card p-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                s.direction === "buy" ? "bg-accent-emerald/15 text-accent-emerald" :
                s.direction === "sell" ? "bg-accent-rose/15 text-accent-rose" : "bg-accent-amber/15 text-accent-amber"
              }`}>{s.signal_type || s.direction}</span>
              <span className="text-xs text-surface-500">اعتماد: {s.confidence}%</span>
            </div>
            <p className="text-sm text-surface-200 mt-1">{s.description}</p>
          </div>
          <span className="text-xs text-surface-600">{s.date}</span>
        </div>
      )) : (
        <div className="text-center py-12 text-surface-500">
          <p className="text-4xl mb-3">📡</p>
          <p>سیگنالی برای {symbol} یافت نشد</p>
        </div>
      )}
    </div>
  );
}

// ------ News Tab ------------------------------------------------------------------------------------------------------------------------------------------------
function NewsTab({ news, symbol }: { news: NewsItem[]; symbol: string }) {
  return (
    <div className="space-y-3">
      {news.length > 0 ? news.map((n, i) => (
        <a
          key={n.id || `news-${i}`}
          href={n.url || "#"}
          target={n.url ? "_blank" : undefined}
          rel={n.url ? "noopener noreferrer" : undefined}
          className="glass-card p-4 block hover:bg-surface-800/50 transition-colors"
        >
          <h3 className="font-semibold text-surface-100">{n.title}</h3>
          <div className="flex items-center gap-3 mt-2 text-xs text-surface-500">
            <span>{n.source}</span>
            <span>{n.published_at}</span>
          </div>
          {n.summary && <p className="text-sm text-surface-400 mt-2 line-clamp-2">{n.summary}</p>}
        </a>
      )) : (
        <div className="text-center py-12 text-surface-500">
          <p className="text-4xl mb-3">📰</p>
          <p>اخباری برای {symbol} یافت نشد</p>
        </div>
      )}
    </div>
  );
}

// ------ Holders Tab ---------------------------------------------------------------------------------------------------------------------------------------
function HoldersTab({ holders, insider }: { holders: MajorHolder[]; insider: InsiderTrade[] }) {
  return (
    <div className="space-y-5">
      {holders.length > 0 && (
        <Card title="👥 سهامداران عمده">
          <div className="space-y-2">
            {holders.map((h, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50">
                <div>
                  <p className="text-sm font-medium text-surface-200">{h.name}</p>
                  <p className="text-xs text-surface-500 mt-0.5">{h.type}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono font-bold text-surface-100">{h.percentage}%</p>
                  <p className="text-xs text-surface-500">{formatCurrency(h.shares)} سهم</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {insider.length > 0 && (
        <Card title="🔄 معاملات داخلی (Insider Trading)">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-2">تاریخ</th>
                  <th className="pb-2 px-2">شخص</th>
                  <th className="pb-2 px-2">سمت</th>
                  <th className="pb-2 px-2">نوع</th>
                  <th className="pb-2 px-2">تعداد</th>
                  <th className="pb-2 px-2">قیمت</th>
                  <th className="pb-2 px-2">ارزش</th>
                </tr>
              </thead>
              <tbody>
                {insider.map((t, i) => (
                  <tr key={i} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2 px-2 font-mono text-surface-300 text-xs">{t.date}</td>
                    <td className="py-2 px-2 text-surface-200">{t.person}</td>
                    <td className="py-2 px-2 text-xs text-surface-400">{t.position}</td>
                    <td className="py-2 px-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${t.type === "buy" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"}`}>
                        {t.type === "buy" ? "خرید" : "فروش"}
                      </span>
                    </td>
                    <td className="py-2 px-2 font-mono text-surface-200">{t.volume.toLocaleString()}</td>
                    <td className="py-2 px-2 font-mono text-surface-200">{t.price.toLocaleString()}</td>
                    <td className="py-2 px-2 font-mono text-surface-200">{formatCurrency(t.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {!holders.length && !insider.length && <div className="text-center py-12 text-surface-500">اطلاعات سهامداران در دسترس نیست</div>}
    </div>
  );
}

// ------ Trades Tab ---------------------------------------------------------------------------------------------------------------------------------------------
function TradesTab({ trades, symbol }: { trades: IntradayTrade[]; symbol: string }) {
  return (
    <div className="space-y-4">
      <Card title="🔄 ریز معاملات" subtitle={symbol + " - آخرین معاملات روز"}>
        {trades.length === 0 ? (
          <div className="text-center py-12 text-surface-500">ریز معامله‌ای برای این نماد در دسترس نیست</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                  <th className="pb-2 px-2">#</th>
                  <th className="pb-2 px-2">زمان</th>
                  <th className="pb-2 px-2">قیمت (ریال)</th>
                  <th className="pb-2 px-2">حجم</th>
                  <th className="pb-2 px-2">ارزش (ریال)</th>
                  <th className="pb-2 px-2">وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => {
                  const tradeValue = t.price * t.volume;
                  return (
                    <tr key={t.id ?? i} className="border-b border-surface-800/50 hover:bg-white/5">
                      <td className="py-2 px-2 font-mono text-surface-500 text-xs">{i + 1}</td>
                      <td className="py-2 px-2 font-mono text-surface-200 text-xs">{t.time || "-"}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{t.price.toLocaleString()}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{t.volume.toLocaleString()}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{tradeValue.toLocaleString()}</td>
                      <td className="py-2 px-2">
                        {t.canceled
                          ? <span className="text-xs px-1.5 py-0.5 rounded bg-accent-rose/15 text-accent-rose">لغو شده</span>
                          : <span className="text-xs px-1.5 py-0.5 rounded bg-accent-emerald/15 text-accent-emerald">عادی</span>
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}


