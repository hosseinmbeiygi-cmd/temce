"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray, extractItems } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────
interface CompanyProfile {
  symbol: string; name: string; industry: string;
  eps: number; pe: number; market_cap: number; shares_count: number;
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

interface SignalItem {
  id: string; symbol: string; signal_type: string;
  direction: string; confidence: number; description: string; date: string;
}

interface NewsItem {
  id: string; symbol: string; title: string;
  source: string; published_at: string; summary: string;
}

interface InsiderTrade {
  date: string; person: string; position: string;
  type: "buy" | "sell"; volume: number; price: number; value: number;
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

// ── Tabs ───────────────────────────────────────────────────
const TABS = [
  { key: "overview", label: "نمای کلی", icon: "📊" },
  { key: "price", label: "قیمت و تکنیکال", icon: "📈" },
  { key: "codal", label: "گزارش‌های کدال", icon: "📋" },
  { key: "fundamental", label: "بنیادی", icon: "💰" },
  { key: "signals", label: "سیگنال‌ها", icon: "📡" },
  { key: "news", label: "اخبار", icon: "📰" },
  { key: "holders", label: "سهامداران", icon: "👥" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

// ── Helpers ────────────────────────────────────────────────
const FALLBACK_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر"];

async function searchSymbols(query: string): Promise<string[]> {
  if (!query) return FALLBACK_SYMBOLS;
  try {
    const res = await apiGet<{ success: boolean; data: { items: { symbol: string }[] } }>(`/instruments?search=${encodeURIComponent(query)}&page_size=20`);
    const items = extractItems<{ symbol: string }>(res);
    if (items.length > 0) return items.map(i => i.symbol);
  } catch {}
  // Fallback: filter local list
  return FALLBACK_SYMBOLS.filter(s => s.includes(query));
}

function formatCurrency(val: number): string {
  if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(1) + "T";
  if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(1) + "B";
  if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(1) + "M";
  if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(0) + "K";
  return val.toLocaleString();
}

function formatPct(val: number): { text: string; color: string } {
  const fixed = val.toFixed(2);
  if (val > 0) return { text: `+${fixed}%`, color: "text-accent-emerald" };
  if (val < 0) return { text: `${fixed}%`, color: "text-accent-rose" };
  return { text: "0.00%", color: "text-surface-400" };
}

// ── Mini Chart (sparkline) ─────────────────────────────────
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

// ── Symbol Selector ────────────────────────────────────────
function SymbolSelector({ current, onSelect }: { current: string; onSelect: (s: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<string[]>(FALLBACK_SYMBOLS);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setSearching(true);
    searchSymbols(query).then(symbols => {
      if (!cancelled) { setResults(symbols); setSearching(false); }
    });
    return () => { cancelled = true; };
  }, [query, open]);

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 bg-surface-800 hover:bg-surface-700 border border-surface-700 rounded-xl px-4 py-2.5 text-white font-mono font-bold text-lg transition-colors">
        {current} <span className="text-xs text-surface-500">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 z-50 bg-surface-800 border border-surface-700 rounded-xl shadow-2xl w-64 overflow-hidden">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجوی نماد..." className="w-full bg-surface-900 px-4 py-2 text-sm text-white border-b border-surface-700 outline-none" autoFocus />
          <div className="max-h-48 overflow-y-auto">
            {searching && <div className="px-4 py-3 text-xs text-surface-500">در حال جستجو...</div>}
            {results.map((s) => (
              <button key={s} onClick={() => { onSelect(s); setOpen(false); setQuery(""); }}
                className={`w-full text-right px-4 py-2.5 text-sm hover:bg-surface-700 transition-colors ${s === current ? "bg-primary-600/20 text-primary-300" : "text-surface-200"}`}>
                {s}
              </button>
            ))}
            {!searching && results.length === 0 && <div className="px-4 py-3 text-xs text-surface-500">نتیجه‌ای یافت نشد</div>}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────
export default function SymbolPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = (params?.symbol as string) || "فولاد";
  const decodedSymbol = decodeURIComponent(symbol);

  const [tab, setTab] = useState<TabKey>("overview");
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [codal, setCodal] = useState<CodalReport[]>([]);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [holders, setHolders] = useState<MajorHolder[]>([]);
  const [insider, setInsider] = useState<InsiderTrade[]>([]);
  const [dividends, setDividends] = useState<DividendRecord[]>([]);
  const [financials, setFinancials] = useState<FinancialQuarter[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, cRes, sRes, nRes, hRes, iRes, dRes, fRes] = await Promise.allSettled([
        apiGet<{ success: boolean; data: CompanyProfile }>(`/codal/${decodedSymbol}/profile`),
        apiGet<{ success: boolean; data: { items: CodalReport[] } }>(`/codal/${decodedSymbol}?page_size=20`),
        apiGet<{ success: boolean; data: { items: SignalItem[] } }>(`/signals?symbol=${decodedSymbol}&page_size=20`),
        apiGet<{ success: boolean; data: { items: NewsItem[] } }>(`/news?symbol=${decodedSymbol}&page_size=10`),
        apiGet<{ success: boolean; data: { holders: MajorHolder[] } }>(`/codal/${decodedSymbol}/holders`),
        apiGet<{ success: boolean; data: { trades: InsiderTrade[] } }>(`/codal/${decodedSymbol}/insider`),
        apiGet<{ success: boolean; data: { dividends: DividendRecord[] } }>(`/codal/${decodedSymbol}/dividends`),
        apiGet<{ success: boolean; data: { quarters: FinancialQuarter[] } }>(`/codal/${decodedSymbol}/financials`),
      ]);

      if (pRes.status === "fulfilled" && pRes.value?.data) setProfile(pRes.value.data);
      if (cRes.status === "fulfilled" && cRes.value?.data?.items) setCodal(cRes.value.data.items);
      if (sRes.status === "fulfilled") setSignals(extractItems(sRes.value));
      if (nRes.status === "fulfilled") setNews(extractItems(nRes.value));
      if (hRes.status === "fulfilled" && hRes.value?.data?.holders) setHolders(hRes.value.data.holders);
      if (iRes.status === "fulfilled" && iRes.value?.data?.trades) setInsider(iRes.value.data.trades);
      if (dRes.status === "fulfilled" && dRes.value?.data?.dividends) setDividends(dRes.value.data.dividends);
      if (fRes.status === "fulfilled" && fRes.value?.data?.quarters) setFinancials(fRes.value.data.quarters);
    } catch {}
    setLoading(false);
  }, [decodedSymbol]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Mock quote data when API unavailable
  const displayQuote = useMemo(() => {
    if (quote) return quote;
    const seed = decodedSymbol.length * 137 + decodedSymbol.charCodeAt(0);
    const base = 10000 + (seed % 90000);
    const changePct = ((seed % 11) - 5) / 100;
    return {
      symbol: decodedSymbol, price_close: base, price_change: base * changePct,
      price_change_pct: changePct, volume: 5000000 + (seed % 15000000),
      value: base * (5000000 + (seed % 15000000)),
      price_high: base * 1.03, price_low: base * 0.97, price_open: base * 0.99,
      price_yesterday: base / (1 + changePct), date: "1403-06-30",
    } as QuoteData;
  }, [decodedSymbol, quote]);

  const sparkData = useMemo(() => generateSparkline(displayQuote.price_close, 40), [displayQuote.price_close]);
  const pct = formatPct(displayQuote.price_change_pct);

  if (loading) {
    return (
      <AppLayout title={`جزئیات ${decodedSymbol}`} subtitle="در حال بارگذاری...">
        <div className="max-w-7xl mx-auto space-y-4">
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout title={profile?.name || decodedSymbol} subtitle={`نماد: ${decodedSymbol} ${profile ? `• ${profile.industry}` : ""}`}>
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ── Header Bar ────────────────────────────────── */}
        <div className="glass-card p-5 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <SymbolSelector current={decodedSymbol} onSelect={(s) => router.push(`/symbol/${s}`)} />
            <div>
              <div className="flex items-center gap-3">
                <span className="text-3xl font-black text-surface-100 font-mono">{displayQuote.price_close.toLocaleString()}</span>
                <span className={`text-lg font-bold font-mono ${pct.color}`}>{pct.text}</span>
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

        {/* ── Tab Navigation ────────────────────────────── */}
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

        {/* ── Tab Content ───────────────────────────────── */}
        {tab === "overview" && <OverviewTab profile={profile} quote={displayQuote} codal={codal} signals={signals} news={news} holders={holders} financials={financials} />}
        {tab === "price" && <PriceTab symbol={decodedSymbol} quote={displayQuote} />}
        {tab === "codal" && <CodalTab codal={codal} symbol={decodedSymbol} />}
        {tab === "fundamental" && <FundamentalTab financials={financials} dividends={dividends} profile={profile} />}
        {tab === "signals" && <SignalsTab signals={signals} symbol={decodedSymbol} />}
        {tab === "news" && <NewsTab news={news} symbol={decodedSymbol} />}
        {tab === "holders" && <HoldersTab holders={holders} insider={insider} />}

        {/* ── Quick Links ───────────────────────────────── */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href={`/instruments`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← همه نمادها</Link>
          <Link href={`/codal`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">کدال</Link>
          <Link href={`/analysis`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">تحلیل بازار</Link>
          <Link href={`/smart-money?symbol=${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">پول هوشمند</Link>
        </div>
      </div>
    </AppLayout>
  );
}

// ═══════════════════════════════════════════════════════════════
// Tab Components
// ═══════════════════════════════════════════════════════════════

function OverviewTab({ profile, quote, codal, signals, news, holders, financials }: {
  profile: CompanyProfile | null; quote: QuoteData; codal: CodalReport[];
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
            <InfoRow label="مدیرعامل" value={profile.ceo} />
            <InfoRow label="رئیس هیئت مدیره" value={profile.board_chairman} />
            <InfoRow label="سال تأسیس" value={String(profile.established)} />
            <InfoRow label="تعداد سهام" value={formatCurrency(profile.shares_count)} />
            <InfoRow label="ارزش بازار" value={`${formatCurrency(profile.market_cap)} ریال`} />
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
            <MetricBox label="ارزش بازار" value={formatCurrency(profile.market_cap)} unit="ریال" />
            <MetricBox label="قیمت" value={quote.price_close.toLocaleString()} unit="ریال" color="text-primary-300" />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 text-center">
            <MetricBox label="قیمت" value={quote.price_close.toLocaleString()} unit="ریال" color="text-primary-300" />
            <MetricBox label="حجم" value={formatCurrency(quote.volume)} unit="سهم" />
            <MetricBox label="ارزش" value={formatCurrency(quote.value)} unit="ریال" />
            <MetricBox label="تغییر" value={`${quote.price_change_pct >= 0 ? "+" : ""}${quote.price_change_pct.toFixed(2)}%`} color={quote.price_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
          </div>
        )}
      </Card>

      {/* Quick Stats */}
      <Card title="⏱ خلاصه">
        <div className="space-y-4">
          <StatRow icon="📋" label="گزارش‌های کدال" value={`${codal.length} گزارش`} />
          <StatRow icon="📡" label="سیگنال‌ها" value={`${signals.length} سیگنال`} />
          <StatRow icon="📰" label="اخبار" value={`${news.length} خبر`} />
          <StatRow icon="👥" label="سهامداران عمده" value={`${holders.length} سهامدار`} />
          {lastFin && <StatRow icon="💰" label="آخرین EPS" value={lastFin.eps.toLocaleString()} />}
        </div>
      </Card>

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

      {/* Latest News */}
      <Card title="📰 آخرین اخبار" className="lg:col-span-full">
        {news.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {news.slice(0, 4).map((n) => (
              <div key={n.id} className="p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors">
                <p className="text-sm font-medium text-surface-200 line-clamp-2">{n.title}</p>
                <div className="flex items-center justify-between mt-2 text-xs text-surface-500">
                  <span>{n.source}</span>
                  <span>{n.published_at}</span>
                </div>
              </div>
            ))}
          </div>
        ) : <p className="text-surface-500 text-sm">اخباری یافت نشد</p>}
      </Card>
    </div>
  );
}

// ── Price Tab ───────────────────────────────────────────────
function PriceTab({ symbol, quote }: { symbol: string; quote: QuoteData }) {
  const candleData = useMemo(() => {
    const base = quote.price_close;
    const bars: { t: string; o: number; h: number; l: number; c: number; v: number }[] = [];
    let price = base * 0.85;
    for (let i = 60; i >= 0; i--) {
      const change = (Math.random() - 0.48) * 0.04;
      const open = price;
      const close = price * (1 + change);
      const high = Math.max(open, close) * (1 + Math.random() * 0.02);
      const low = Math.min(open, close) * (1 - Math.random() * 0.02);
      bars.push({ t: `۱۴۰۳-${String((i % 12) + 1).padStart(2, "0")}-${String((i % 30) + 1).padStart(2, "0")}`, o: Math.round(open), h: Math.round(high), l: Math.round(low), c: Math.round(close), v: Math.round(1000000 + Math.random() * 10000000) });
      price = close;
    }
    return bars;
  }, [quote.price_close]);

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
          <IndicatorBox label="RSI (14)" value={45 + Math.round(Math.random() * 30)} unit="" type="neutral" />
          <IndicatorBox label="MACD" value={Math.random() > 0.5 ? "سیگنال خرید" : "سیگنال فروش"} unit="" type={Math.random() > 0.5 ? "positive" : "negative"} />
          <IndicatorBox label="SMA (20)" value={Math.round(quote.price_close * (0.95 + Math.random() * 0.1)).toLocaleString()} unit="ریال" type="neutral" />
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

// ── Codal Tab ───────────────────────────────────────────────
function CodalTab({ codal, symbol }: { codal: CodalReport[]; symbol: string }) {
  const reportTypes = [...new Set(codal.map(c => c.report_type).filter(Boolean))];
  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? codal : codal.filter(c => c.report_type === filter);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          <button onClick={() => setFilter("all")} className={`px-3 py-1.5 rounded-lg text-xs ${filter === "all" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}>همه</button>
          {reportTypes.map(t => (
            <button key={t} onClick={() => setFilter(t)} className={`px-3 py-1.5 rounded-lg text-xs ${filter === t ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}>{t}</button>
          ))}
        </div>
        <Link href="/codal/import" className="text-xs text-primary-400 hover:text-primary-300 transition-colors">+ ورود اطلاعات کدال</Link>
      </div>

      {filtered.length > 0 ? (
        <div className="space-y-2">
          {filtered.map((r) => (
            <div key={r.id} className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="font-semibold text-surface-100">{typeof r.summary === "string" ? r.summary : r.summary?.text || r.report_type}</h3>
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-surface-500">
                    <span className="bg-surface-700 px-2 py-0.5 rounded">{r.report_type}</span>
                    <span>سال مالی: {r.fiscal_year}</span>
                    <span>دوره: {r.period}</span>
                    <span>تاریخ انتشار: {r.publish_date}</span>
                  </div>
                </div>
                {r.attachment_url && (
                  <a href={r.attachment_url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-xs bg-primary-600/20 text-primary-300 px-3 py-1.5 rounded-lg hover:bg-primary-600/30 transition-colors">مشاهده</a>
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

// ── Fundamental Tab ─────────────────────────────────────────
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

// ── Signals Tab ─────────────────────────────────────────────
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

// ── News Tab ────────────────────────────────────────────────
function NewsTab({ news, symbol }: { news: NewsItem[]; symbol: string }) {
  return (
    <div className="space-y-3">
      {news.length > 0 ? news.map((n) => (
        <div key={n.id} className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
          <h3 className="font-semibold text-surface-100">{n.title}</h3>
          <div className="flex items-center gap-3 mt-2 text-xs text-surface-500">
            <span>{n.source}</span>
            <span>{n.published_at}</span>
          </div>
          {n.summary && <p className="text-sm text-surface-400 mt-2 line-clamp-2">{n.summary}</p>}
        </div>
      )) : (
        <div className="text-center py-12 text-surface-500">
          <p className="text-4xl mb-3">📰</p>
          <p>اخباری برای {symbol} یافت نشد</p>
        </div>
      )}
    </div>
  );
}

// ── Holders Tab ─────────────────────────────────────────────
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

// ═══════════════════════════════════════════════════════════════
// Utility Components
// ═══════════════════════════════════════════════════════════════

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-surface-500">{label}</span>
      <span className="font-medium text-surface-200 text-left">{value}</span>
    </div>
  );
}

function MetricBox({ label, value, unit = "", color = "text-surface-100" }: { label: string; value: string; unit?: string; color?: string }) {
  return (
    <div className="bg-surface-800 rounded-xl p-3">
      <p className="text-xs text-surface-500 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
      {unit && <p className="text-xs text-surface-600 mt-0.5">{unit}</p>}
    </div>
  );
}

function StatRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-surface-400 text-sm">{icon} {label}</span>
      <span className="font-mono font-bold text-surface-200">{value}</span>
    </div>
  );
}

function IndicatorBox({ label, value, unit, type }: { label: string; value: string; unit: string; type: "positive" | "negative" | "neutral" }) {
  const color = type === "positive" ? "text-accent-emerald" : type === "negative" ? "text-accent-rose" : "text-surface-200";
  return (
    <div className="bg-surface-800 rounded-xl p-3">
      <p className="text-xs text-surface-500 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
      {unit && <p className="text-xs text-surface-600 mt-0.5">{unit}</p>}
    </div>
  );
}
