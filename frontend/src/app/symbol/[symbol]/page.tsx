"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import Link from "next/link";
import { AuditBadge } from "@/components/AuditBadge";
import { DonutChart } from "@/components/DonutChart";
import { EmptyTab } from "@/components/EmptyTab";
import { IndicatorBox } from "@/components/IndicatorBox";
import { InfoRow } from "@/components/InfoRow";
import { MetricBox } from "@/components/MetricBox";
import { PreBuyTab } from "@/components/prebuy/PreBuyTab";
import { RealLegalCard } from "@/components/RealLegalCard";
import { StatRow } from "@/components/StatRow";
import AppLayout from "@/components/layout/AppLayout";
import StockIntelligencePanel from "@/components/StockIntelligencePanel";
import TradingViewChart from "@/components/charts/TradingViewChart";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import SymbolSelector from "@/components/SymbolSelector";
import { apiGet, apiPost, extractItems } from "@/lib/api";
import { formatDateShamsi, formatTime } from "@/lib/dates";
import type { CandleDataPoint } from "@/lib/types";

// ------ ML / prediction types (backend responses) ----------------------------------------------------------------------------------
interface MlModelBrief {
  id: string;
  name: string;
}

interface MLPredictionResult {
  prediction?: number;
  predicted_change_pct?: number;
  confidence?: number;
  direction?: string;
  last_price?: number;
  feature_importance?: Record<string, number>;
}

interface MLBacktestFold {
  metrics?: Record<string, number>;
  r2?: number;
  mae?: number;
  rmse?: number;
  directional_accuracy?: number;
  train_size?: number | null;
  test_size?: number | null;
}

interface MLBacktestResult {
  folds?: MLBacktestFold[];
  feature_importance?: Record<string, number>;
  n_folds?: number;
  aggregate_metrics?: Record<string, number>;
}

interface DataPreviewInfo {
  ohlcv_rows?: number;
  history_rows?: number;
  trade_flow_rows?: number;
  trade_rows?: number;
  estimated_features?: string | number;
}

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
  date: string; cash_per_share: number; total_payout: number | null; type: string; meeting: string;
}

interface FinancialQuarter {
  period: string; revenue: number; cost: number; gross_profit: number;
  operating_profit: number; net_profit: number; eps: number;
}

// ------ Tabs ---------------------------------------------------------------------------------------------------------------------------------------------------------
const TABS = [
  { key: "overview", label: "نمای کلی", icon: "📊" },
  { key: "prebuy", label: "برگهٔ خرید", icon: "✅" },
  { key: "price", label: "قیمت و تکنیکال", icon: "📈" },
  { key: "codal", label: "گزارش‌های کدال", icon: "📋" },
  { key: "fundamental", label: "بنیادی", icon: "💰" },
  { key: "signals", label: "سیگنال‌ها", icon: "📡" },
  { key: "news", label: "اخبار", icon: "📰" },
  { key: "holders", label: "سهامداران", icon: "👥" },
  { key: "trades", label: "ریز معاملات", icon: "🔄" },
  { key: "ml", label: "پیش‌بینی ML", icon: "🧠" },
  { key: "backtest", label: "بک‌تست", icon: "🧪" },
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
  return val.toLocaleString("en-US");
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
        apiGet<{ success: boolean; data: { items: IntradayTrade[] } }>(`/trades/${encodeURIComponent(decodedSymbol)}?limit=2000`),
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
        const closes = sparkRes.value.data.map((d: { close?: number }) => d.close || 0);
        if (closes.length > 0) {
          setSparkHistory(closes.reverse()); // chronological order for sparkline
        }
      }
    } catch {}
    setLoading(false);
  }, [decodedSymbol]);

  useEffect(() => {
    const timer = setTimeout(fetchAll, 0);
    return () => clearTimeout(timer);
  }, [fetchAll]);

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
      {/* ── Enterprise Intelligence (v2 — ۹ تب نهادی) ── */}
      <div className="mb-6">
        <StockIntelligencePanel symbol={decodedSymbol} />
      </div>
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ------ Header Bar ------------------------------------------------------------------------------------------------------ */}
        {displayQuote ? (
          <div className="glass-card p-5 flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <SymbolSelector value={decodedSymbol} onChange={(s) => router.push(`/symbol/${s}`)} />
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-black text-surface-100 font-mono">{displayQuote.price_close.toLocaleString("en-US")}</span>
                  <span className={`text-lg font-bold font-mono ${pct.color}`}>{pct.text}</span>
                  {displayState && (
                    <span className={`text-xs font-bold px-2 py-1 rounded-lg ${stateColor}`}>{displayState}</span>
                  )}
                </div>
                <div className="flex items-center gap-4 mt-1 text-xs text-surface-500">
                  <span>حجم: {formatCurrency(displayQuote.volume)}</span>
                  <span>ارزش: {formatCurrency(displayQuote.value)} ریال</span>
                  <span>دیروز: {displayQuote.price_yesterday.toLocaleString("en-US")}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <Sparkline data={sparkData} width={150} height={40} color={displayQuote.price_change_pct >= 0 ? "#22c55e" : "#ef4444"} />
              <div className="grid grid-cols-3 gap-4 text-center">
                <div><div className="text-xs text-surface-500">بالا</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_high.toLocaleString("en-US")}</div></div>
                <div><div className="text-xs text-surface-500">پایین</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_low.toLocaleString("en-US")}</div></div>
                <div><div className="text-xs text-surface-500">باز</div><div className="font-mono font-bold text-surface-200">{displayQuote.price_open.toLocaleString("en-US")}</div></div>
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
        {tab === "prebuy" && <PreBuyTab symbol={decodedSymbol} />}
        {tab === "price" && (displayQuote ? <PriceTab symbol={decodedSymbol} quote={displayQuote} /> : <EmptyTab message="داده‌های قیمتی برای نمایش وجود ندارد" />)}
        {tab === "codal" && <CodalTab codal={codal} brsapiCodal={brsapiCodal} symbol={decodedSymbol} />}
        {tab === "fundamental" && <FundamentalTab financials={financials} dividends={dividends} profile={profile} />}
        {tab === "signals" && <SignalsTab signals={signals} symbol={decodedSymbol} />}
        {tab === "news" && <NewsTab news={news} symbol={decodedSymbol} />}
        {tab === "holders" && <HoldersTab holders={holders} insider={insider} />}
        {tab === "trades" && <TradesTab trades={trades} symbol={decodedSymbol} />}
        {tab === "ml" && <MLTab symbol={decodedSymbol} />}
        {tab === "backtest" && <BacktestTab symbol={decodedSymbol} />}

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
        <span className="text-accent-emerald font-mono">{low.toLocaleString("en-US")}</span>
        <span className="text-surface-500">آستانه مجاز</span>
        <span className="text-accent-rose font-mono">{high.toLocaleString("en-US")}</span>
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
        قیمت فعلی: <span className="font-mono text-surface-200">{current.toLocaleString("en-US")}</span>
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

  // Clear the comparison target when the input is emptied (adjust state during render)
  const [prevCompareWith, setPrevCompareWith] = useState(compareWith);
  if (compareWith !== prevCompareWith) {
    setPrevCompareWith(compareWith);
    if (!compareWith) setTargetProfile(null);
  }

  // Fetch comparison data
  useEffect(() => {
    if (!compareWith) return;
    let cancelled = false;
    // Defer so the state update doesn't run synchronously during commit
    const loadingTimer = setTimeout(() => { if (!cancelled) setLoadingCompare(true); }, 0);
    apiGet<{ success: boolean; data: CompanyProfile }>(`/codal/${compareWith}/profile`)
      .then(res => { if (!cancelled && res?.data) setTargetProfile(res.data); })
      .catch(() => { if (!cancelled) setTargetProfile(null); })
      .finally(() => { if (!cancelled) setLoadingCompare(false); });
    return () => { cancelled = true; clearTimeout(loadingTimer); };
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
      ours: currentProfile.price_last?.toLocaleString("en-US") ?? "—",
      theirs: targetProfile?.price_last?.toLocaleString("en-US") ?? null,
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
      ours: currentProfile.eps.toLocaleString("en-US"),
      theirs: targetProfile ? targetProfile.eps.toLocaleString("en-US") : null,
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
            <InfoRow label="حجم مبنا" value={profile.base_volume ? profile.base_volume.toLocaleString("en-US") : "-"} />
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
            <MetricBox label="EPS" value={profile.eps.toLocaleString("en-US")} unit="ریال" />
            <MetricBox label="P/E" value={profile.pe.toFixed(1)} unit="×" />
            {profile.group_pe != null && profile.group_pe !== 0 && (
              <MetricBox label="P/E گروه" value={profile.group_pe.toFixed(1)} unit="×" />
            )}
            <MetricBox label="شناوری" value={profile.free_float_pct != null ? `${profile.free_float_pct.toFixed(1)}%` : "-"} unit="" />
            <MetricBox label="ارزش بازار" value={formatCurrency(profile.market_cap)} unit="ریال" />
            <MetricBox label="قیمت پایانی" value={quote?.price_close?.toLocaleString("en-US") ?? "—"} unit="ریال" color="text-primary-300" />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 text-center">
            <MetricBox label="قیمت" value={quote?.price_close?.toLocaleString("en-US") ?? "—"} unit="ریال" color="text-primary-300" />
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
          {lastFin && <StatRow icon="💰" label="آخرین EPS" value={lastFin.eps.toLocaleString("en-US")} />}
          {profile?.base_volume != null && profile.base_volume > 0 && (
            <StatRow icon="📦" label="حجم مبنا" value={profile.base_volume.toLocaleString("en-US")} />
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
              <MetricBox label="EPS" value={profile.eps.toLocaleString("en-US")} unit="ریال" color={profile.eps >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
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
              <p className="font-mono font-bold text-accent-rose">{(profile.price_max ?? quote?.price_high ?? 0).toLocaleString("en-US")}</p>
            </div>
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">پایین‌ترین قیمت روز</p>
              <p className="font-mono font-bold text-accent-emerald">{(profile.price_min ?? quote?.price_low ?? 0).toLocaleString("en-US")}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3 text-center">
            <div className="bg-surface-800 rounded-xl p-3">
              <p className="text-xs text-surface-500 mb-1">EPS</p>
              <p className="font-mono font-bold text-primary-300">{profile.eps.toLocaleString("en-US")}</p>
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

const CANDLE_TYPES = [
  { value: "1", label: "لحظه‌ای", icon: "⚡" },
  { value: "2", label: "تعدیل‌نشده", icon: "📊" },
  { value: "3", label: "تعدیل‌شده", icon: "🔁" },
] as const;
type CandleTypeValue = (typeof CANDLE_TYPES)[number]["value"];

function PriceTab({ symbol, quote }: { symbol: string; quote: QuoteData }) {
  const [candleType, setCandleType] = useState<CandleTypeValue>("3");

  // Candlestick series from brsapi_candlesticks — realtime (type=1, 2-min bars)
  // polls every 60s so the intraday chart stays live during market hours.
  const { data: candles } = useQuery({
    queryKey: ["candles", symbol, candleType],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: CandleDataPoint[] }>(
          `/market/candles/${encodeURIComponent(symbol)}?type=${candleType}&limit=300`
        );
        if (res?.success && Array.isArray(res.data)) return res.data;
      } catch {}
      return [];
    },
    enabled: !!symbol,
    refetchInterval: candleType === "1" ? 60_000 : 5 * 60_000,
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

  const candleData = useMemo<CandleDataPoint[]>(() => {
    if (!candles || candles.length === 0) return [];
    return candles.map((bar) => ({
      date: bar.date,
      time: bar.time,
      open: Number(bar.open) || 0,
      high: Number(bar.high) || 0,
      low: Number(bar.low) || 0,
      close: Number(bar.close) || 0,
      volume: Number(bar.volume) || 0,
    }));
  }, [candles]);

  return (
    <div className="space-y-5">
      <Card
        title="📈 نمودار قیمت (شمعی)"
        actions={
          <div className="flex items-center gap-1">
            {CANDLE_TYPES.map(({ value, label, icon }) => (
              <button
                key={value}
                onClick={() => setCandleType(value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  candleType === value
                    ? "bg-primary-600 text-white shadow-md"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700"
                }`}
              >
                {icon} {label}
              </button>
            ))}
          </div>
        }
      >
        {candleData.length > 0 ? (
          <TradingViewChart data={candleData} symbol={symbol} height={480} />
        ) : (
          <div className="text-center py-14 text-surface-500">
            <p className="text-3xl mb-2">🕯️</p>
            <p className="text-sm">داده کندلی برای {symbol} در دسترس نیست — ابتدا سینک کندل را اجرا کنید</p>
          </div>
        )}
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
            value={smaLast != null ? smaLast.toLocaleString("en-US") : "—"}
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
            <p className="font-mono font-bold text-accent-emerald">{(quote.price_close * 0.95).toLocaleString("en-US")}</p>
          </div>
          <div className="bg-surface-800 rounded-xl p-3">
            <p className="text-xs text-surface-500 mb-1">قیمت فعلی</p>
            <p className="font-mono font-bold text-surface-100">{quote.price_close.toLocaleString("en-US")}</p>
          </div>
          <div className="bg-accent-rose/10 rounded-xl p-3">
            <p className="text-xs text-accent-rose mb-1">مقاومت ۱</p>
            <p className="font-mono font-bold text-accent-rose">{(quote.price_close * 1.05).toLocaleString("en-US")}</p>
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
          <Link href={`/codal/analysis/${encodeURIComponent(symbol)}`} className="text-xs text-accent-emerald hover:text-accent-emerald/80 transition-colors">📊 تحلیل بنیادی</Link>
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
                    <td className="py-2.5 px-3 font-mono text-primary-300">{q.eps.toLocaleString("en-US")}</td>
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
                    <td className="py-2.5 px-3 font-mono text-accent-emerald font-bold">{d.cash_per_share.toLocaleString("en-US")}</td>
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
                    <td className="py-2 px-2 font-mono text-surface-200">{t.volume.toLocaleString("en-US")}</td>
                    <td className="py-2 px-2 font-mono text-surface-200">{t.price.toLocaleString("en-US")}</td>
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
  const [page, setPage] = useState(1);
  const pageSize = 100;
  const totalPages = Math.ceil(trades.length / pageSize);
  const pageTrades = trades.slice((page - 1) * pageSize, page * pageSize);

  // Summary stats
  const totalVolume = trades.reduce((s, t) => s + (t.volume || 0), 0);
  const totalValue = trades.reduce((s, t) => s + (t.price * t.volume || 0), 0);
  const canceledCount = trades.filter(t => t.canceled).length;
  const avgPrice = trades.length > 0 ? trades.reduce((s, t) => s + t.price, 0) / trades.length : 0;

  return (
    <div className="space-y-4">
      {/* Summary */}
      {trades.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-bold text-surface-100">{trades.length.toLocaleString("en-US")}</p>
            <p className="text-[10px] text-surface-500">کل معاملات</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-bold text-accent-emerald">{formatCurrency(totalVolume)}</p>
            <p className="text-[10px] text-surface-500">حجم کل</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-bold text-primary-300">{formatCurrency(totalValue)}</p>
            <p className="text-[10px] text-surface-500">ارزش کل</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className={`text-lg font-bold ${canceledCount > 0 ? "text-accent-rose" : "text-surface-400"}`}>{canceledCount}</p>
            <p className="text-[10px] text-surface-500">لغو شده</p>
          </div>
        </div>
      )}

      <Card title="🔄 ریز معاملات" subtitle={symbol + " - آخرین معاملات روز"}>
        {trades.length === 0 ? (
          <div className="text-center py-12 text-surface-500">
            <p className="text-4xl mb-3">🔄</p>
            <p>ریز معامله‌ای برای {symbol} در دسترس نیست</p>
            <p className="text-xs text-surface-600 mt-1">ممکن است داده‌های intraday هنوز sync نشده باشند</p>
          </div>
        ) : (
          <>
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
                  {pageTrades.map((t, i) => {
                    const tradeValue = t.price * t.volume;
                    const rowIdx = (page - 1) * pageSize + i + 1;
                    return (
                      <tr key={t.id ?? i} className="border-b border-surface-800/50 hover:bg-white/5">
                        <td className="py-2 px-2 font-mono text-surface-500 text-xs">{rowIdx}</td>
                        <td className="py-2 px-2 font-mono text-surface-200 text-xs">{t.time || "-"}</td>
                        <td className="py-2 px-2 font-mono text-surface-200">{t.price.toLocaleString("en-US")}</td>
                        <td className="py-2 px-2 font-mono text-surface-200">{t.volume.toLocaleString("en-US")}</td>
                        <td className="py-2 px-2 font-mono text-surface-200">{tradeValue.toLocaleString("en-US")}</td>
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
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-1 mt-4">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="px-3 py-1.5 rounded-lg bg-surface-800 text-surface-300 text-xs disabled:opacity-40">قبلی</button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
                  if (p > totalPages) return null;
                  return <button key={p} onClick={() => setPage(p)} className={`px-3 py-1.5 rounded-lg text-xs ${p === page ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-300"}`}>{p}</button>;
                })}
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="px-3 py-1.5 rounded-lg bg-surface-800 text-surface-300 text-xs disabled:opacity-40">بعدی</button>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

// ------ ML Prediction Tab ------------------------------------------------------------------------------------------------------------------------------------
function MLTab({ symbol }: { symbol: string }) {
  const [selectedModel, setSelectedModel] = useState("xgboost");
  const [prediction, setPrediction] = useState<MLPredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [featureGroups, setFeatureGroups] = useState<string[]>(["price", "technical"]);

  const { data: models = [] } = useQuery({
    queryKey: ["ml-models-list"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: MlModelBrief[] }>("/ml/models");
        return res?.data ?? [];
      } catch { return []; }
    },
    staleTime: 300_000,
  });

  const { data: dataPreview } = useQuery({
    queryKey: ["ml-data-preview", symbol],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: DataPreviewInfo }>(`/ml/data-preview/${encodeURIComponent(symbol)}`);
        return res?.data ?? null;
      } catch { return null; }
    },
    staleTime: 60_000,
  });

  const toggleFeatureGroup = (fg: string) => {
    if (fg === "all") { setFeatureGroups(["price", "technical", "trades", "microstructure"]); return; }
    setFeatureGroups(prev => {
      const next = prev.includes(fg) ? prev.filter(x => x !== fg) : [...prev, fg];
      return next.length === 0 ? ["price"] : next;
    });
  };

  const handlePredict = useCallback(async () => {
    if (!selectedModel) return;
    setLoading(true);
    setPrediction(null);
    try {
      const res = await apiPost<{ success: boolean; data: MLPredictionResult }>("/ml/predict-real", {
        model_id: selectedModel, symbol,
      });
      if (res?.success && res.data) setPrediction(res.data);
    } catch (e) { console.error("ML predict failed:", e); }
    setLoading(false);
  }, [selectedModel, symbol]);

  const fmtPct = (v: number) => (v >= 0 ? "+" : "") + (v * 100).toFixed(2) + "%";

  return (
    <div className="space-y-4">
      {/* Data Preview */}
      {dataPreview && (
        <Card title="📊 موجودی داده" subtitle={symbol}>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {[
              { label: "OHLCV", value: dataPreview.ohlcv_rows?.toLocaleString("fa-IR") ?? "0", ok: (dataPreview.ohlcv_rows ?? 0) > 0 },
              { label: "تاریخچه", value: dataPreview.history_rows?.toLocaleString("fa-IR") ?? "0", ok: (dataPreview.history_rows ?? 0) > 0 },
              { label: "حقیقی/حقوقی", value: dataPreview.trade_flow_rows?.toLocaleString("fa-IR") ?? "0", ok: (dataPreview.trade_flow_rows ?? 0) > 0 },
              { label: "ریزمعاملات", value: dataPreview.trade_rows?.toLocaleString("fa-IR") ?? "0", ok: (dataPreview.trade_rows ?? 0) > 0 },
              { label: "ویژگی‌ها", value: dataPreview.estimated_features ?? "—", ok: true },
            ].map(d => (
              <div key={d.label} className="bg-surface-800/50 rounded-xl p-2.5 text-center">
                <p className={`text-sm font-black font-mono ${d.ok ? "text-accent-emerald" : "text-surface-500"}`}>{d.value}</p>
                <p className="text-[8px] text-surface-500">{d.label}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Controls */}
      <Card title="🧠 پیش‌بینی ML" subtitle="انتخاب مدل و گروه ویژگی">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Model */}
          <div>
            <label className="text-[10px] text-surface-500 font-bold mb-1 block">🤖 مدل</label>
            <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
              className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 text-xs text-surface-200 focus:outline-none focus:border-primary-500">
              {(models.length > 0 ? models : [
                { id: "xgboost", name: "xgboost" }, { id: "lightgbm", name: "lightgbm" },
                { id: "catboost", name: "catboost" }, { id: "random_forest", name: "random_forest" },
              ]).map((m: MlModelBrief) => <option key={m.id || m.name} value={m.id || m.name}>{m.name || m.id}</option>)}
            </select>
          </div>

          {/* Feature Groups */}
          <div>
            <label className="text-[10px] text-surface-500 font-bold mb-1 block">🧩 گروه ویژگی</label>
            <div className="flex flex-wrap gap-1">
              {["price", "technical", "trades", "microstructure"].map(fg => (
                <button key={fg} onClick={() => toggleFeatureGroup(fg)}
                  className={`px-2 py-1 rounded-lg text-[9px] font-medium border transition-all ${
                    featureGroups.includes(fg)
                      ? "bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan"
                      : "bg-surface-800/50 border-surface-700/50 text-surface-500"
                  }`}>
                  {fg}
                </button>
              ))}
            </div>
          </div>

          {/* Predict Button */}
          <div className="flex items-end">
            <button onClick={handlePredict} disabled={loading}
              className="w-full py-2.5 bg-primary-600 text-white rounded-xl text-xs font-bold hover:bg-primary-500 disabled:opacity-50 transition-all flex items-center justify-center gap-2">
              {loading ? <><span className="material-icons animate-spin text-sm">refresh</span> در حال پیش‌بینی...</> : "🔮 پیش‌بینی"}
            </button>
          </div>
        </div>
      </Card>

      {/* Prediction Result */}
      {prediction && (
        <Card title="🎯 نتیجه پیش‌بینی" subtitle={`${selectedModel} • ${symbol}`}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="glass-card p-3 text-center">
              <p className={`text-2xl font-black font-mono ${(prediction.prediction ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                {fmtPct(prediction.prediction ?? 0)}
              </p>
              <p className="text-[9px] text-surface-500">📈 تغییر پیش‌بینی</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-2xl font-black font-mono text-surface-200">
                {prediction.confidence != null ? (prediction.confidence * 100).toFixed(0) + "%" : "—"}
              </p>
              <p className="text-[9px] text-surface-500">🎯 اطمینان</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className={`text-2xl font-black ${prediction.predicted_change_pct != null ? (prediction.predicted_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500"}`}>
                {prediction.predicted_change_pct != null ? fmtPct(prediction.predicted_change_pct) : prediction.direction === "up" ? "📈 صعود" : prediction.direction === "down" ? "📉 نزول" : "—"}
              </p>
              <p className="text-[9px] text-surface-500">جهت پیش‌بینی</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-2xl font-black font-mono text-surface-400">{prediction.last_price?.toLocaleString("fa-IR") ?? "—"}</p>
              <p className="text-[9px] text-surface-500">💰 قیمت آخر</p>
            </div>
          </div>

          {/* Feature Importance */}
          {prediction.feature_importance && Object.keys(prediction.feature_importance).length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] text-surface-400 font-bold mb-2">🔥 اهمیت ویژگی‌ها</p>
              <div className="space-y-1">
                {Object.entries(prediction.feature_importance)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 10)
                  .map(([feat, val]) => (
                    <div key={feat} className="flex items-center gap-2">
                      <span className="text-[9px] text-surface-400 w-28 truncate text-right font-mono">{feat}</span>
                      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
                        <div className="h-full bg-accent-amber rounded-full" style={{ width: `${(val as number) * 100}%` }} />
                      </div>
                      <span className="text-[9px] font-mono text-surface-500 w-10 text-left">{(val as number * 100).toFixed(0)}%</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {!prediction && !loading && (
        <div className="glass-card p-10 text-center text-surface-500">
          <p className="text-4xl mb-3">🧠</p>
          <p className="font-bold text-surface-400">پیش‌بینی ML برای {symbol}</p>
          <p className="text-sm mt-1">مدل و گروه ویژگی را انتخاب کنید و دکمه پیش‌بینی را بزنید</p>
        </div>
      )}
    </div>
  );
}

// ------ Backtest Tab -----------------------------------------------------------------------------------------------------------------------------------------
function BacktestTab({ symbol }: { symbol: string }) {
  const [btModel, setBtModel] = useState("xgboost");
  const [btSplits, setBtSplits] = useState(5);
  const [btResult, setBtResult] = useState<MLBacktestResult | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btFeatureGroups, setBtFeatureGroups] = useState<string[]>(["price", "technical"]);

  const { data: models = [] } = useQuery({
    queryKey: ["ml-models-list"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: MlModelBrief[] }>("/ml/models");
        return res?.data ?? [];
      } catch { return []; }
    },
    staleTime: 300_000,
  });

  const toggleFeatureGroup = (fg: string) => {
    setBtFeatureGroups(prev => {
      const next = prev.includes(fg) ? prev.filter(x => x !== fg) : [...prev, fg];
      return next.length === 0 ? ["price"] : next;
    });
  };

  const handleRunBacktest = useCallback(async () => {
    setBtLoading(true);
    setBtResult(null);
    try {
      const res = await apiPost<{ success: boolean; data: MLBacktestResult }>("/ml/backtest", {
        symbol,
        model_type: btModel,
        n_splits: btSplits,
        feature_groups: btFeatureGroups,
      });
      if (res?.success && res.data) {
        setBtResult(res.data);
        toast.success("✅ بک‌تست انجام شد");
      }
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "خطا در بک‌تست"); }
    setBtLoading(false);
  }, [btModel, btSplits, btFeatureGroups, symbol]);

  // Parse nested response
  const agg = (btResult?.aggregate_metrics ?? btResult ?? {}) as unknown as Record<string, unknown>;
  const folds = btResult?.folds ?? [];
  const mean_r2 = (agg.mean_r2 as number | undefined) ?? null;
  const mean_mae = (agg.mean_mae as number | undefined) ?? null;
  const mean_rmse = (agg.mean_rmse as number | undefined) ?? null;
  const dir_acc = (agg.mean_directional_accuracy as number | undefined) ?? null;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card title="🧪 بک‌تست Walk-Forward" subtitle={symbol}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] text-surface-500 font-bold mb-1 block">🤖 مدل</label>
            <select value={btModel} onChange={e => setBtModel(e.target.value)}
              className="w-full bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 text-xs text-surface-200 focus:outline-none focus:border-primary-500">
              {(models.length > 0 ? models : [
                { id: "xgboost", name: "xgboost" }, { id: "lightgbm", name: "lightgbm" },
                { id: "catboost", name: "catboost" }, { id: "random_forest", name: "random_forest" },
              ]).map((m: MlModelBrief) => <option key={m.id || m.name} value={m.id || m.name}>{m.name || m.id}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-surface-500 font-bold mb-1 block">📐 Fold‌ها</label>
            <div className="flex gap-1">
              {[3, 5, 10].map(n => (
                <button key={n} onClick={() => setBtSplits(n)}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                    btSplits === n ? "bg-primary-600/30 text-primary-300" : "bg-surface-800 text-surface-500 hover:text-surface-300"
                  }`}>{n}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-surface-500 font-bold mb-1 block">🧩 ویژگی‌ها</label>
            <div className="flex flex-wrap gap-1">
              {["price", "technical", "trades", "microstructure"].map(fg => (
                <button key={fg} onClick={() => toggleFeatureGroup(fg)}
                  className={`px-2 py-1 rounded-lg text-[9px] font-medium border transition-all ${
                    btFeatureGroups.includes(fg)
                      ? "bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan"
                      : "bg-surface-800/50 border-surface-700/50 text-surface-500"
                  }`}>{fg}</button>
              ))}
            </div>
          </div>
          <div className="flex items-end">
            <button onClick={handleRunBacktest} disabled={btLoading}
              className="w-full py-2.5 bg-accent-amber/15 text-accent-amber border border-accent-amber/30 rounded-xl text-xs font-bold hover:bg-accent-amber/25 transition-all disabled:opacity-50 flex items-center justify-center gap-2">
              {btLoading ? <><span className="material-icons animate-spin text-sm">refresh</span> در حال اجرا...</> : "🚀 اجرای بک‌تست"}
            </button>
          </div>
        </div>
      </Card>

      {/* Loading */}
      {btLoading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      )}

      {/* Results */}
      {btResult && !btLoading && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {[
              { icon: "📊", label: "R² میانگین", value: mean_r2 != null ? mean_r2.toFixed(4) : "—", color: (mean_r2 ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose" },
              { icon: "📉", label: "MAE", value: mean_mae != null ? mean_mae.toFixed(4) : "—", color: "text-surface-200" },
              { icon: "📉", label: "RMSE", value: mean_rmse != null ? mean_rmse.toFixed(4) : "—", color: "text-surface-200" },
              { icon: "🎯", label: "دقت جهت", value: dir_acc != null ? (dir_acc * 100).toFixed(1) + "%" : "—", color: (dir_acc ?? 0) >= 0.5 ? "text-accent-emerald" : "text-accent-rose" },
              { icon: "📐", label: "Fold‌ها", value: `${folds.length}/${btResult.n_folds ?? "?"}`, color: "text-surface-200" },
            ].map(m => (
              <div key={m.label} className="glass-card p-3 text-center hover:scale-[1.02] transition-transform">
                <p className={`text-lg font-black font-mono ${m.color}`}>{m.value}</p>
                <p className="text-[8px] text-surface-500">{m.icon} {m.label}</p>
              </div>
            ))}
          </div>

          {/* Fold Details */}
          {folds.length > 0 && (
            <Card title="📋 جزئیات Fold‌ها" subtitle={`${folds.length} fold • ${btModel}`}>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-[10px]">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 px-2">Fold</th>
                      <th className="pb-2 px-2 text-center font-mono">R²</th>
                      <th className="pb-2 px-2 text-center font-mono">MAE</th>
                      <th className="pb-2 px-2 text-center font-mono">RMSE</th>
                      <th className="pb-2 px-2 text-center">دقت جهت</th>
                      <th className="pb-2 px-2 text-center">آموزش</th>
                      <th className="pb-2 px-2 text-center">تست</th>
                    </tr>
                  </thead>
                  <tbody>
                    {folds.map((fold: MLBacktestFold, i: number) => {
                      const fm = fold.metrics ?? fold;
                      return (
                        <tr key={i} className="border-b border-surface-800/30 hover:bg-white/5">
                          <td className="py-2 px-2 font-bold text-surface-200">Fold {i + 1}</td>
                          <td className={`py-2 px-2 text-center font-mono ${(fm.r2 ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {fm.r2?.toFixed(4) ?? "—"}
                          </td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">{fm.mae?.toFixed(4) ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">{fm.rmse?.toFixed(4) ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">
                            {fm.directional_accuracy != null ? (fm.directional_accuracy * 100).toFixed(1) + "%" : "—"}
                          </td>
                          <td className="py-2 px-2 text-center font-mono text-surface-400">{fold.train_size ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-400">{fold.test_size ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Feature Importance */}
          {btResult.feature_importance && Object.keys(btResult.feature_importance).length > 0 && (
            <Card title="🔥 اهمیت ویژگی‌ها">
              <div className="space-y-1">
                {Object.entries(btResult.feature_importance)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 15)
                  .map(([feat, val]) => (
                    <div key={feat} className="flex items-center gap-2">
                      <span className="text-[9px] text-surface-400 w-28 truncate text-right font-mono">{feat}</span>
                      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
                        <div className="h-full bg-accent-amber rounded-full" style={{ width: `${(val as number) * 100}%` }} />
                      </div>
                      <span className="text-[9px] font-mono text-surface-500 w-10 text-left">{(val as number * 100).toFixed(0)}%</span>
                    </div>
                  ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {!btResult && !btLoading && (
        <div className="glass-card p-10 text-center text-surface-500">
          <p className="text-4xl mb-3">🧪</p>
          <p className="font-bold text-surface-400">بک‌تست Walk-Forward برای {symbol}</p>
          <p className="text-sm mt-1">مدل، تعداد fold و گروه ویژگی را انتخاب کنید</p>
        </div>
      )}
    </div>
  );
}


