"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, extractArray } from "@/lib/api";
import { useMarketWebSocket } from "@/hooks/useWebSocket";
import {
  Activity,
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpLeft,
  Bell,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Database,
  Layers3,
  LineChart,
  Newspaper,
  ShieldCheck,
  Sparkles,
  WalletCards,
} from "lucide-react";
import {
  atr,
  beta,
  correlation,
  returns,
  rsi,
  sma,
  weeklyCloses,
  windowSignals,
} from "@/lib/market";

type Timeframe = "1D" | "1W";

const REALTIME_REFRESH_LABEL = "۱–۳s";
const EMAMI_PURE_GOLD_OZ = 0.24; // 8.294 g × 0.900 purity ÷ 31.1035 g/oz

/* ────────────────────────── live prices (BrsApi) ────────────────────────── */

type LiveRow = {
  symbol?: string;
  name?: string;
  price?: number;
  price_irr?: number;
  price_usd?: number;
  change_percent?: number;
  change_value?: number;
  volume?: number;
  market_cap?: number;
  date?: string;
  time?: string;
  timestamp?: string | number;
};

function useLiveMarketData() {
  const trackedSymbols = ["IR_COIN_EMAMI", "IR_GOLD_18K", "XAUUSD", "USD", "IR_COIN_BAHAR"];
  const { prices: wsPrices, connected: wsConnected, error: wsError } = useMarketWebSocket(trackedSymbols);
  // ponytail: WS hook no longer reports latency after the sidebar refactor;
  // add a ping/pong round-trip back into useWebSocket if the badge should show ms again.
  const latencyMs: number | null = null;
  const query = useQuery({
    queryKey: ["multi-asset-live-market"],
    queryFn: async () => {
      const [gold, currency, crypto] = await Promise.all([
        apiGet<{ data?: LiveRow[] }>("/brsapi/gold-coin"),
        apiGet<{ data?: LiveRow[] }>("/brsapi/currency"),
        apiGet<{ data?: LiveRow[] }>("/brsapi/crypto?limit=100&sort_by=rank"),
      ]);
      return {
        rows: [...extractArray<LiveRow>(gold), ...extractArray<LiveRow>(currency), ...extractArray<LiveRow>(crypto)],
        fetchedAt: Date.now(),
      };
    },
    refetchInterval: 3_000,
    staleTime: 2_500,
    retry: 2,
  });
  const bySymbol = useMemo(() => {
    const result = new Map<string, LiveRow>();
    for (const row of query.data?.rows ?? []) if (row.symbol) result.set(row.symbol, row);
    for (const [symbol, row] of wsPrices) {
      result.set(symbol, { ...result.get(symbol), ...row });
    }
    return result;
  }, [query.data?.rows, wsPrices]);
  return {
    bySymbol,
    cryptoRows: (query.data?.rows ?? []).filter((r) => r.price_usd !== undefined),
    wsConnected,
    wsError,
    latencyMs,
    isLoading: query.isLoading,
    isError: query.isError,
    updatedAt: query.dataUpdatedAt,
  };
}

/* ────────────────────────── BrsApi section queries ────────────────────────── */

type SeriesRow = { date?: string; price_close?: number; price_last?: number; price_open?: number; price_high?: number; price_low?: number };

function useGoldHistory(limit = 365) {
  const query = useQuery({
    queryKey: ["multi-asset-history", "IR_GOLD_18K", limit],
    queryFn: () => apiGet<unknown>(`/brsapi/history/IR_GOLD_18K?limit=${limit}`),
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  });
  const rows = useMemo(() => {
    const raw = extractArray<SeriesRow>(query.data)
      .filter((r) => Number.isFinite(Number(r.price_close)) && Number(r.price_close) > 0)
      .reverse(); // API returns newest-first → oldest-first
    return raw;
  }, [query.data]);
  const closes = useMemo(() => rows.map((r) => Number(r.price_close)), [rows]);
  const highs = useMemo(() => rows.map((r) => Number(r.price_high ?? r.price_close)), [rows]);
  const lows = useMemo(() => rows.map((r) => Number(r.price_low ?? r.price_close)), [rows]);
  return { rows, closes, highs, lows, isLoading: query.isLoading, isError: query.isError, updatedAt: query.dataUpdatedAt };
}

function useSeriesHistory(symbol: string, limit = 365, enabled = true) {
  const query = useQuery({
    queryKey: ["multi-asset-history", symbol, limit],
    queryFn: () => apiGet<unknown>(`/brsapi/history/${encodeURIComponent(symbol)}?limit=${limit}`),
    enabled,
    staleTime: 5 * 60_000,
  });
  const pairs = useMemo(
    () =>
      extractArray<SeriesRow>(query.data)
        .filter((r) => Number.isFinite(Number(r.price_close ?? r.price_last)) && Number(r.price_close ?? r.price_last) > 0)
        .map((r) => ({ date: (r.date ?? "").replace(/\//g, "-"), close: Number(r.price_close ?? r.price_last) }))
        .reverse(),
    [query.data],
  );
  return { pairs, closes: pairs.map((p) => p.close), isLoading: query.isLoading, isError: query.isError };
}

type SnapshotRow = {
  symbol?: string;
  name?: string;
  price_last?: number;
  price_last_change_pct?: number;
  pe_ratio?: number;
  eps?: number;
  trade_value?: number;
  trade_volume?: number;
};

type NavRow = { symbol?: string; nav_issue?: number; nav_redemption?: number; date?: string };

function useFundSnapshot(symbol: string) {
  const price = useQuery({
    queryKey: ["multi-asset-fund-price", symbol],
    queryFn: () => apiGet<unknown>(`/brsapi/manage/download/all-symbols?symbol=${encodeURIComponent(symbol)}&limit=1`),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  const nav = useQuery({
    queryKey: ["multi-asset-fund-nav", symbol],
    queryFn: () => apiGet<unknown>(`/brsapi/manage/download/nav?symbol=${encodeURIComponent(symbol)}&limit=1`),
    staleTime: 5 * 60_000,
  });
  const row = extractArray<SnapshotRow>(price.data)[0];
  const navRow = extractArray<NavRow>(nav.data)[0];
  return { row, navRow, isLoading: price.isLoading || nav.isLoading, isError: price.isError };
}

function useSymbolDetail(symbol: string, enabled = true) {
  const query = useQuery({
    queryKey: ["multi-asset-symbol-detail", symbol],
    queryFn: () => apiGet<{ data?: Record<string, number | string | null> }>(`/brsapi/symbol-details/${encodeURIComponent(symbol)}`),
    enabled,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  return { detail: query.data?.data ?? null, isLoading: query.isLoading, isError: query.isError };
}

type FuturesRow = {
  contract_code?: string;
  contract_description?: string;
  price_last?: number;
  price_last_change_pct?: number;
  open_interest?: number;
  margin_initial?: number;
  days_remaining?: number;
};

function useGoldFutures() {
  const query = useQuery({
    queryKey: ["multi-asset-futures"],
    queryFn: () => apiGet<unknown>("/brsapi/manage/download/ime-futures?limit=2000"),
    staleTime: 2 * 60_000,
    refetchInterval: 2 * 60_000,
  });
  const rows = useMemo(
    () =>
      extractArray<FuturesRow>(query.data)
        .filter((r) => r.contract_code && r.contract_description?.includes("طلا") && (r.price_last ?? 0) > 0)
        .slice(0, 6),
    [query.data],
  );
  return { rows, isLoading: query.isLoading };
}

type CodalRow = { symbol?: string; company_name?: string; title?: string; date_publish?: string; code?: string };

function useCodalNews() {
  const query = useQuery({
    queryKey: ["multi-asset-codal"],
    queryFn: () => apiGet<unknown>("/brsapi/codal-announcements?limit=6"),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
  const rows = useMemo(() => extractArray<CodalRow>(query.data).slice(0, 6), [query.data]);
  return { rows, isLoading: query.isLoading, isError: query.isError };
}

function useBrSHealth() {
  const health = useQuery({
    queryKey: ["multi-asset-brs-health"],
    queryFn: () => apiGet<{ data?: Record<string, string | number> }>("/brsapi/health"),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const sync = useQuery({
    queryKey: ["multi-asset-brs-sync"],
    queryFn: () => apiGet<{ data?: Record<string, { last_fetched?: string; age_minutes?: number; status?: string }> }>("/brsapi/sync-status"),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  return { health: health.data?.data ?? null, sync: sync.data?.data ?? null };
}

function useTseIndex() {
  const query = useQuery({
    queryKey: ["multi-asset-index-tse"],
    queryFn: () => apiGet<unknown>("/brsapi/manage/download/index-tse?limit=40"),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  const rows = extractArray<{ index_value?: number; index_change?: number; index_change_pct?: number; state?: string }>(query.data);
  const main = rows.filter((r) => (r.index_value ?? 0) > 1_000_000);
  const computedChange = main.length >= 2 && main[1].index_value ? (main[0].index_value! / main[1].index_value - 1) * 100 : null;
  return { value: main[0]?.index_value ?? null, changePct: main[0]?.index_change_pct || computedChange, isLoading: query.isLoading };
}

/* ────────────────────────── portfolio (localStorage) ────────────────────────── */

type Trade = {
  id: string;
  symbol: string;
  label: string;
  side: "BUY" | "SELL";
  quantity: number;
  entryPrice: number;
  date: string;
};

const TRADES_KEY = "multi-as…s-v1";

function useStoredTrades() {
  const [trades, setTrades] = useState<Trade[]>([]);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(TRADES_KEY);
      if (raw) setTrades(JSON.parse(raw) as Trade[]);
    } catch {
      /* corrupted storage → start empty */
    }
  }, []);
  const save = (trade: Trade) => {
    setTrades((current) => {
      const next = [trade, ...current];
      try {
        window.localStorage.setItem(TRADES_KEY, JSON.stringify(next));
      } catch {
        /* quota errors are non-fatal for this session */
      }
      return next;
    });
  };
  const remove = (id: string) => {
    setTrades((current) => {
      const next = current.filter((t) => t.id !== id);
      try {
        window.localStorage.setItem(TRADES_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };
  return { trades, save, remove };
}

/* ────────────────────────── formatting ────────────────────────── */

function faNumber(value: number, maximumFractionDigits = 0) {
  return value.toLocaleString("fa-IR", { maximumFractionDigits });
}

function faPrice(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "—" : faNumber(value, digits);
}

function faPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${faNumber(value, digits)}٪`;
}

function formatDateTime(value?: string | number | null) {
  if (!value) return "—";
  const date = typeof value === "number" ? new Date(value) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", timeStyle: "medium" }).format(date);
}

/* ────────────────────────── UI primitives ────────────────────────── */

function MetricCard({ item }: { item: { label: string; value: string; change: number | null; unit: string; live: boolean } }) {
  const positive = (item.change ?? 0) >= 0;
  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-card-hover)]">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold text-ink-3">{item.label}</p>
          <p className="mt-1 text-[10px] text-ink-3">{item.unit}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[9px] font-bold ${item.live ? "bg-up/10 text-up" : "bg-soft text-ink-3"}`}>
          {item.live && <span className="ml-1 inline-block size-1.5 animate-pulse rounded-full bg-up" />}
          {item.live ? "LIVE" : "—"}
        </span>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="font-mono text-lg font-black tracking-tight text-ink">{item.value}</span>
        {item.change !== null && (
          <span className={`flex items-center gap-0.5 text-xs font-bold ${positive ? "text-up" : "text-down"}`}>
            {positive ? <ArrowUpLeft className="size-3.5" /> : <ArrowDownLeft className="size-3.5" />}
            {faPct(item.change)}
          </span>
        )}
      </div>
    </div>
  );
}

function StatusPill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "up" | "warn" | "neutral" }) {
  const styles = { up: "bg-up/10 text-up", warn: "bg-warn/10 text-warn", neutral: "bg-soft text-ink-2" };
  return <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${styles[tone]}`}>{children}</span>;
}

function LiveStatusBadge({ connected, latencyMs }: { connected: boolean; latencyMs: number | null }) {
  const latencyLabel = latencyMs === null ? "— ms" : `${faNumber(latencyMs)} ms`;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold ${connected ? "bg-up/10 text-up" : "bg-warn/10 text-warn"}`}>
      <span className={`size-1.5 rounded-full ${connected ? "bg-up animate-pulse" : "bg-warn"}`} aria-hidden="true" />
      {connected ? `LIVE · ${latencyLabel}` : "POLLING · stale"}
    </span>
  );
}

function ChannelBadge({ label, detail, tone }: { label: string; detail: string; tone: "up" | "warn" | "neutral" }) {
  const styles = {
    up: "border-up/25 bg-up/5 text-up",
    warn: "border-warn/25 bg-warn/5 text-warn",
    neutral: "border-line bg-soft text-ink-2",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[10px] font-bold ${styles[tone]}`} title={`${label}: ${detail}`}>
      <span className={`size-1.5 rounded-full ${tone === "up" ? "bg-up animate-pulse" : tone === "warn" ? "bg-warn" : "bg-ink-3"}`} />
      <span>{label}</span>
      <span className="font-normal opacity-80">{detail}</span>
    </span>
  );
}

function SectionCard({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon: typeof Activity; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-ink">{title}</h3>
          {subtitle && <p className="mt-1 text-[11px] text-ink-3">{subtitle}</p>}
        </div>
        <Icon className="size-5 shrink-0 text-primary-500" />
      </div>
      {children}
    </section>
  );
}

function Sparkline({ values, color = "#dcae4b" }: { values: number[]; color?: string }) {
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${100 - value}`).join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-28 w-full">
      <defs>
        <linearGradient id={`fill-${color.replace("#", "")}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity=".3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={`0,100 ${points} 100,100`} fill={`url(#fill-${color.replace("#", "")})`} stroke="none" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function normalizeSeries(values: number[]): number[] {
  if (values.length < 2) return values;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values.slice(-48).map((value) => 15 + ((value - min) / range) * 70);
}

/* ────────────────────────── gold tab sections ────────────────────────── */

function LiveMarketLayer({ live }: { live: ReturnType<typeof useLiveMarketData> }) {
  const latencyLabel = live.latencyMs === null ? "— ms" : `${faNumber(live.latencyMs)} ms`;
  const latencyTone = !live.wsConnected || live.latencyMs === null || live.latencyMs > 1000 ? "warn" : "up";
  const get = (symbol: string) => live.bySymbol.get(symbol);
  const priceOf = (symbol: string) => {
    const row = get(symbol);
    return row?.price ?? row?.price_irr ?? null;
  };
  const usdtIrr = useMemo(() => {
    const usdt = get("USDT");
    const usd = priceOf("USD");
    if (usdt?.price_usd && usd) return usdt.price_usd * usd;
    return usdt?.price_irr || null;
  }, [live.bySymbol]);
  const cards = [
    { label: "سکه امامی", unit: "تومان", value: priceOf("IR_COIN_EMAMI") !== null ? (priceOf("IR_COIN_EMAMI") as number) / 10 : null, change: get("IR_COIN_EMAMI")?.change_percent ?? null, live: Boolean(get("IR_COIN_EMAMI")) },
    { label: "طلای ۱۸ عیار", unit: "تومان / گرم", value: priceOf("IR_GOLD_18K") !== null ? (priceOf("IR_GOLD_18K") as number) / 10 : null, change: get("IR_GOLD_18K")?.change_percent ?? null, live: Boolean(get("IR_GOLD_18K")) },
    { label: "انس جهانی", unit: "دلار", value: priceOf("XAUUSD"), change: get("XAUUSD")?.change_percent ?? null, live: Boolean(get("XAUUSD")) },
    { label: "دلار", unit: "تومان", value: priceOf("USD") !== null ? (priceOf("USD") as number) / 10 : null, change: get("USD")?.change_percent ?? null, live: Boolean(get("USD")) },
    { label: "تتر (مرجع)", unit: "تومان — محاسبه از USDT×USD", value: usdtIrr !== null ? usdtIrr / 10 : null, change: get("USDT")?.change_percent ?? get("USD")?.change_percent ?? null, live: Boolean(usdtIrr) },
  ];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-card px-4 py-3 shadow-[var(--shadow-card)]">
        <span className="mr-1 text-[10px] font-bold text-ink-3">کانال داده</span>
        <LiveStatusBadge connected={live.wsConnected} latencyMs={live.latencyMs} />
        <ChannelBadge label="BrsApi REST" detail={live.updatedAt ? `OK · Refresh ${REALTIME_REFRESH_LABEL}` : "در انتظار"} tone={live.isError ? "warn" : "up"} />
        <ChannelBadge label="WebSocket" detail={live.wsConnected ? `LIVE · ${latencyLabel}` : "fallback polling"} tone={latencyTone} />
      </div>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {cards.map((item) => (
          <MetricCard key={item.label} item={{ ...item, value: faPrice(item.value, 2) }} />
        ))}
      </section>
      {(live.isError || live.wsError) && (
        <div className="flex items-center gap-2 rounded-xl border border-warn/25 bg-warn/5 px-3 py-2 text-[11px] text-warn">
          <AlertTriangle className="size-4 shrink-0" />
          اتصال زنده ناپایدار است؛ دادهٔ آخرین پاسخ موفق نمایش داده می‌شود و تلاش مجدد ادامه دارد.
        </div>
      )}
    </div>
  );
}

function GoldChart({ history, live, timeframe, setTimeframe }: {
  history: ReturnType<typeof useGoldHistory>;
  live: ReturnType<typeof useLiveMarketData>;
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
}) {
  const livePrice = live.bySymbol.get("IR_GOLD_18K")?.price ?? null;
  const series = timeframe === "1W" ? weeklyCloses(history.closes) : history.closes;
  const withLive = livePrice && series.length > 0 && series[series.length - 1] !== livePrice ? [...series, livePrice] : series;
  const normalized = normalizeSeries(withLive);
  const min = withLive.length ? Math.min(...withLive) : null;
  const max = withLive.length ? Math.max(...withLive) : null;
  const last = withLive.length ? withLive[withLive.length - 1] : null;
  const first = withLive.length ? withLive[0] : null;
  const changePct = last && first ? (last / first - 1) * 100 : null;
  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-sm font-black text-ink">نمودار طلای ۱۸ عیار / تومان</h3>
          <p className="mt-1 text-[11px] text-ink-3">کندل‌های واقعی BrsApi — {faNumber(history.closes.length)} روز تاریخچه {live.wsConnected ? "· قیمت زنده روی آخرین نقطه" : ""}</p>
        </div>
        <div className="flex gap-1 rounded-xl bg-soft p-1">
          {(["1D", "1W"] as const).map((tf) => (
            <button key={tf} onClick={() => setTimeframe(tf)} className={`rounded-lg px-3 py-1.5 text-[10px] font-bold ${timeframe === tf ? "bg-card text-primary-600 shadow-sm" : "text-ink-3"}`}>
              {tf === "1D" ? "روزانه" : "هفتگی"}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 rounded-xl bg-soft/60 p-3">
        {history.isLoading ? (
          <p className="py-10 text-center text-xs text-ink-3">در حال دریافت تاریخچه واقعی…</p>
        ) : withLive.length < 2 ? (
          <p className="py-10 text-center text-xs text-warn">دادهٔ تاریخی در دسترس نیست — همگام‌سازی تاریخچه BrsApi انجام نشده است.</p>
        ) : (
          <>
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-xl font-black text-ink">{faPrice(last !== null ? last / 10 : null, 0)}</span>
              {changePct !== null && <span className={`text-xs font-bold ${changePct >= 0 ? "text-up" : "text-down"}`}>{faPct(changePct)} در بازه</span>}
            </div>
            <Sparkline values={normalized} />
            <div className="mt-2 flex justify-between text-[10px] text-ink-3">
              <span>کمینه: {faPrice(min !== null ? min / 10 : null)}</span>
              <span>بیشینه: {faPrice(max !== null ? max / 10 : null)}</span>
              <span>آخرین کندل: {history.rows[history.rows.length - 1]?.date ?? "—"}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SignalValidation({ history }: { history: ReturnType<typeof useGoldHistory> }) {
  const signals = useMemo(() => windowSignals(history.closes), [history.closes]);
  const rsiValue = useMemo(() => rsi(history.closes), [history.closes]);
  const confirmations = signals.filter((s) => s.bullish).length;
  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-black text-ink">اعتبارسنجی مولتی‌ویندو</h3>
          <p className="mt-1 text-[11px] text-ink-3">محاسبه‌شده از بسته‌های واقعی روزانهٔ طلا (مومنتوم + EMA)</p>
        </div>
        <div className="grid size-14 place-items-center rounded-full border-4 border-up/30 text-center">
          <span className="text-sm font-black text-up">{signals.length ? `${faNumber(confirmations)}/${faNumber(signals.length)}` : "—"}</span>
        </div>
      </div>
      {signals.length === 0 ? (
        <p className="py-6 text-center text-xs text-warn">تاریخچه کافی برای محاسبه سیگنال موجود نیست.</p>
      ) : (
        <div className="space-y-2">
          {signals.map((row) => (
            <div key={row.label} className="flex items-center gap-3 rounded-xl bg-soft/70 px-3 py-2">
              <span className="w-10 font-mono text-[11px] font-bold text-ink-3">{row.label}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                <div className={`h-full rounded-full ${row.bullish ? "bg-up" : "bg-warn"}`} style={{ width: `${row.score}%` }} />
              </div>
              <span className={`text-[10px] font-bold ${row.bullish ? "text-up" : "text-warn"}`}>{row.bullish ? "صعودی" : "ضعیف/خنثی"}</span>
              <span className="w-7 text-left font-mono text-[10px] text-ink-3">{row.score}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 rounded-xl bg-soft/70 px-3 py-2 text-[11px]">
            <span className="text-ink-3">RSI(14) روزانه:</span>
            <b className="font-mono text-ink">{rsiValue === null ? "—" : faNumber(rsiValue, 1)}</b>
            {rsiValue !== null && <StatusPill tone={rsiValue > 70 ? "warn" : rsiValue < 30 ? "up" : "neutral"}>{rsiValue > 70 ? "اشباع خرید" : rsiValue < 30 ? "اشباع فروش" : "متعادل"}</StatusPill>}
          </div>
        </div>
      )}
    </div>
  );
}

const GOLD_FUNDS = ["طلا", "عیار", "گوهر", "زر", "زرفام"];

function EtfAnalysisTable() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const funds = GOLD_FUNDS.map((symbol) => ({ symbol, data: useFundSnapshot(symbol) }));
  const rows = funds
    .filter((f) => f.data.row && (f.data.row.price_last ?? 0) > 0)
    .map((f) => {
      const price = f.data.row!.price_last as number;
      const nav = f.data.navRow?.nav_issue ?? f.data.navRow?.nav_redemption ?? null;
      const premium = nav ? (price / nav - 1) * 100 : null;
      return { symbol: f.symbol, name: f.data.row?.name ?? f.symbol, price, nav, premium, volume: f.data.row?.trade_value ?? null, change: f.data.row?.price_last_change_pct ?? null };
    });
  return (
    <SectionCard title="صندوق‌های طلا — قیمت، NAV و حباب" subtitle="NAV از TSETMC (BrsApi) · حباب = قیمت/NAV − ۱" icon={Layers3}>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-warn">داده‌ای از BrsApi دریافت نشد.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-right text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] text-ink-3">
                <th className="pb-3">نماد</th><th className="pb-3">قیمت (ریال)</th><th className="pb-3">NAV (ریال)</th><th className="pb-3">حباب</th><th className="pb-3">تغییر</th><th className="pb-3">ارزش معامله</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.symbol} className="border-b border-line/60 last:border-0">
                  <td colSpan={6} className="p-0">
                    <button type="button" onClick={() => setExpanded(expanded === row.symbol ? null : row.symbol)} className="grid w-full grid-cols-[1.35fr_.9fr_.9fr_.8fr_.7fr_.9fr] items-center gap-2 py-3 text-right hover:bg-soft/60">
                      <span className="font-bold text-ink">{row.symbol}<span className="mr-2 text-[10px] font-normal text-ink-3">{row.name}</span></span>
                      <span className="font-mono text-ink-2">{faPrice(row.price)}</span>
                      <span className="font-mono text-ink-2">{faPrice(row.nav)}</span>
                      <span className={`font-mono font-bold ${row.premium !== null && row.premium > 2 ? "text-warn" : row.premium !== null && row.premium < 0 ? "text-up" : "text-ink-2"}`}>
                        {faPct(row.premium, 1)}{row.premium !== null && Math.abs(row.premium) > 2 && " ⚠️"}
                      </span>
                      <span className={`font-mono ${row.change !== null && row.change >= 0 ? "text-up" : "text-down"}`}>{faPct(row.change, 1)}</span>
                      <span className="font-mono text-ink-2">{row.volume !== null ? faNumber(row.volume / 1e9) + "B" : "—"}</span>
                    </button>
                    {expanded === row.symbol && (
                      <div className="mb-3 rounded-xl bg-soft/70 px-3 py-2 text-[11px] leading-6 text-ink-2">
                        <span className="font-bold text-ink">جزئیات:</span> NAV گزارش‌شده در {funds.find((f) => f.symbol === row.symbol)?.data.navRow?.date ?? "—"} — حباب مثبت یعنی قیمت بازار بالاتر از ارزش خالص دارایی.
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

function IntrinsicDeviationCard({ live }: { live: ReturnType<typeof useLiveMarketData> }) {
  const emami = live.bySymbol.get("IR_COIN_EMAMI")?.price ?? null;
  const gold18 = live.bySymbol.get("IR_GOLD_18K")?.price ?? null;
  const xau = live.bySymbol.get("XAUUSD")?.price ?? null;
  const usd = live.bySymbol.get("USD")?.price ?? null;
  const fund = useFundSnapshot("طلا");
  const rows = [
    emami && xau && usd
      ? { label: "سکه امامی vs ارزش ذاتی", value: (emami / (xau * usd * EMAMI_PURE_GOLD_OZ) - 1) * 100, note: "انس × دلار × ۰٫۲۴ اونس طلای خالص (۸٫۲۹۴ گرم عیار ۹۰۰)" }
      : null,
    gold18 && xau && usd
      ? { label: "طلای ۱۸ گرمی vs انس", value: (gold18 / ((xau * usd * 0.75) / 31.1035) - 1) * 100, note: "انس × دلار × عیار ۷۵۰ ÷ ۳۱٫۱ گرم" }
      : null,
    fund.row?.price_last && fund.navRow?.nav_issue
      ? { label: "صندوق طلا vs NAV", value: (fund.row.price_last / fund.navRow.nav_issue - 1) * 100, note: `NAV گزارش ${fund.navRow.date ?? "—"}` }
      : null,
  ].filter((r): r is NonNullable<typeof r> => r !== null && Number.isFinite(r.value));
  return (
    <SectionCard title="انحراف از ارزش ذاتی" subtitle="محاسبه از قیمت‌های لحظه‌ای BrsApi — واحدها هم‌مقیاس" icon={ArrowUpLeft}>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-warn">برای محاسبه، قیمت انس، دلار و دارایی لازم است؛ هنوز کامل نشده است.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.label} className="grid gap-2 rounded-xl bg-soft/60 p-3 text-xs md:grid-cols-[1.4fr_.8fr_.6fr_1.8fr] md:items-center">
              <span className="font-bold text-ink">{row.label}</span>
              <span className={`font-mono font-bold ${row.value > 0 ? "text-warn" : "text-up"}`}>{faPct(row.value, 1)}</span>
              <StatusPill tone={Math.abs(row.value) > 3 ? "warn" : "neutral"}>{Math.abs(row.value) > 3 ? "قابل توجه" : "عادی"}</StatusPill>
              <span className="text-ink-2">{row.note}</span>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

function FuturesMonitorCard({ futures }: { futures: ReturnType<typeof useGoldFutures> }) {
  return (
    <SectionCard title="پایش آتی طلای IME" subtitle="قراردادهای واقعی بورس کالا/IME — فقط مانیتورینگ، بدون اجرای خودکار" icon={Activity}>
      {futures.isLoading ? (
        <p className="py-6 text-center text-xs text-ink-3">در حال دریافت قراردادها…</p>
      ) : futures.rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-warn">قرارداد آتی طلا با قیمت معتبر در دیتابیس یافت نشد (همگام‌سازی IME لازم است).</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-right text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] text-ink-3">
                <th className="pb-3">قرارداد</th><th className="pb-3">شرح</th><th className="pb-3">آخرین (ریال)</th><th className="pb-3">تغییر</th><th className="pb-3">منافع باز</th><th className="pb-3">وجه تضمین</th>
              </tr>
            </thead>
            <tbody>
              {futures.rows.map((row) => (
                <tr key={row.contract_code} className="border-b border-line/60 last:border-0">
                  <td className="py-3 font-mono font-bold text-ink">{row.contract_code}</td>
                  <td className="py-3 text-ink-2">{row.contract_description}</td>
                  <td className="py-3 font-mono text-ink">{faPrice(row.price_last)}</td>
                  <td className={`py-3 font-mono ${(row.price_last_change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>{faPct(row.price_last_change_pct, 1)}</td>
                  <td className="py-3 font-mono text-ink-2">{faPrice(row.open_interest)}</td>
                  <td className="py-3 font-mono text-ink-2">{faPrice(row.margin_initial)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

function NewsCard({ news }: { news: ReturnType<typeof useCodalNews> }) {
  return (
    <SectionCard title="آخرین اطلاعیه‌های کدال" subtitle="از BrsApi (CODAL_Announcement) — تیترهای واقعی" icon={Newspaper}>
      {news.isLoading ? (
        <p className="py-6 text-center text-xs text-ink-3">در حال دریافت اطلاعیه‌ها…</p>
      ) : news.rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-warn">اطلاعیه‌ای دریافت نشد.</p>
      ) : (
        <div className="space-y-2">
          {news.rows.map((row, index) => (
            <div key={`${row.symbol}-${index}`} className="flex items-start justify-between gap-3 rounded-xl bg-soft/70 px-3 py-2 text-[11px]">
              <div>
                <b className="text-ink">{row.symbol}</b>
                <span className="mr-2 text-ink-2">{row.title}</span>
              </div>
              <span className="shrink-0 font-mono text-[10px] text-ink-3">{row.date_publish}</span>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

function StructuredSignalCard({ history, live }: { history: ReturnType<typeof useGoldHistory>; live: ReturnType<typeof useLiveMarketData> }) {
  const xauusd = useSeriesHistory("XAUUSD", 365);
  const sekke = useFundSnapshot("طلا");
  const signal = useMemo(() => {
    const closes = history.closes;
    if (closes.length < 70) return null;
    const livePrice = live.bySymbol.get("IR_GOLD_18K")?.price ?? null;
    const last = livePrice ?? closes[closes.length - 1];
    const atrValue = atr(history.highs, history.lows, closes) ?? last * 0.02;
    const windows = windowSignals(closes);
    const bullish = windows.filter((w) => w.bullish).length;
    const action = windows.length === 0 ? "NEUTRAL" : bullish > windows.length / 2 ? "BUY" : bullish === 0 ? "SELL" : "HOLD";
    const rsiValue = rsi(closes);
    // Correlation only over dates present in BOTH real series (formats differ).
    const xauByDate = new Map(xauusd.pairs.map((p) => [p.date, p.close]));
    const common = history.rows
      .map((r) => ({ date: (r.date ?? "").replace(/\//g, "-"), close: Number(r.price_close) }))
      .filter((p) => xauByDate.has(p.date));
    const corr = common.length > 30
      ? correlation(returns(common.map((p) => p.close)), returns(common.map((p) => xauByDate.get(p.date) as number)))
      : null;
    const emami = live.bySymbol.get("IR_COIN_EMAMI")?.price ?? null;
    const xau = live.bySymbol.get("XAUUSD")?.price ?? null;
    const usd = live.bySymbol.get("USD")?.price ?? null;
    const bubble = emami && xau && usd ? (emami / (xau * usd * EMAMI_PURE_GOLD_OZ) - 1) * 100 : null;
    const nav = sekke.navRow?.nav_issue ?? null;
    const price = sekke.row?.price_last ?? null;
    const premium = nav && price ? (price / nav - 1) * 100 : null;
    const momentum20 = closes.length > 20 ? (last / closes[closes.length - 21] - 1) * 100 : null;
    return {
      action, last, atrValue, rsiValue, corr, bubble, premium, momentum20,
      stopLoss: action === "SELL" ? last + 2 * atrValue : last - 2 * atrValue,
      target1: action === "SELL" ? last - 2 * atrValue : last + 2 * atrValue,
      target2: action === "SELL" ? last - 4 * atrValue : last + 4 * atrValue,
      windows,
    };
  }, [history, xauusd.pairs, live.bySymbol, sekke]);
  if (!signal) {
    return (
      <SectionCard title="سیگنال ساختاریافتهٔ طلا" subtitle="خروجی محاسبه‌شده از دادهٔ واقعی" icon={Sparkles}>
        <p className="py-6 text-center text-xs text-warn">دادهٔ تاریخی کافی (حداقل ۷۰ روز) برای محاسبهٔ سیگنال موجود نیست.</p>
      </SectionCard>
    );
  }
  const tone = signal.action === "BUY" ? "up" : signal.action === "SELL" ? "warn" : "neutral";
  return (
    <SectionCard title="سیگنال ساختاریافتهٔ طلا (IR_GOLD_18K)" subtitle="محاسبه از تاریخچهٔ واقعی + قیمت لحظه‌ای — ATR-based" icon={Sparkles}>
      <div className="grid gap-3 lg:grid-cols-[1.1fr_1.4fr]">
        <div className="rounded-xl bg-soft/70 p-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-ink-3">دارایی</p>
              <p className="mt-1 font-bold text-ink">طلای ۱۸ عیار · IME/BrsApi</p>
            </div>
            <StatusPill tone={tone}>{signal.action}</StatusPill>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
            <div><span className="text-ink-3">{live.bySymbol.get("IR_GOLD_18K")?.price ? "قیمت زنده" : "آخرین بسته"}</span><b className="mr-2 font-mono text-ink">{faPrice(signal.last / 10)}</b></div>
            <div><span className="text-ink-3">RSI(14)</span><b className="mr-2 font-mono text-ink">{signal.rsiValue === null ? "—" : faNumber(signal.rsiValue, 1)}</b></div>
            <div><span className="text-ink-3">تأیید پنجره‌ها</span><b className="mr-2 text-ink">{faNumber(signal.windows.filter((w) => w.bullish).length)}/{faNumber(signal.windows.length)}</b></div>
            <div><span className="text-ink-3">ATR(14)</span><b className="mr-2 font-mono text-ink">{faPrice(signal.atrValue / 10)}</b></div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div className="rounded-xl border border-line p-2 text-center"><p className="text-[9px] text-ink-3">ورود (آخرین)</p><p className="mt-1 font-mono text-[11px] font-bold text-ink">{faPrice(signal.last / 10)}</p></div>
          <div className="rounded-xl border border-down/20 bg-down/5 p-2 text-center"><p className="text-[9px] text-ink-3">حد ضرر ۲×ATR</p><p className="mt-1 font-mono text-[11px] font-bold text-down">{faPrice(signal.stopLoss / 10)}</p></div>
          <div className="rounded-xl border border-up/20 bg-up/5 p-2 text-center"><p className="text-[9px] text-ink-3">هدف ۱</p><p className="mt-1 font-mono text-[11px] font-bold text-up">{faPrice(signal.target1 / 10)}</p></div>
          <div className="rounded-xl border border-up/20 bg-up/5 p-2 text-center"><p className="text-[9px] text-ink-3">هدف ۲</p><p className="mt-1 font-mono text-[11px] font-bold text-up">{faPrice(signal.target2 / 10)}</p></div>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <span className="rounded-lg bg-soft px-2 py-1.5 text-[10px] text-ink-2">حباب صندوق طلا: <b className={signal.premium !== null && signal.premium < 0 ? "text-up" : "text-warn"}>{faPct(signal.premium, 1)}</b></span>
        <span className="rounded-lg bg-soft px-2 py-1.5 text-[10px] text-ink-2">حباب سکه vs انس×دلار: <b className="text-warn">{faPct(signal.bubble, 1)}</b></span>
        <span className="rounded-lg bg-soft px-2 py-1.5 text-[10px] text-ink-2">همبستگی با انس: <b className="text-primary-600">{signal.corr === null ? "—" : faNumber(signal.corr, 2)}</b></span>
        <span className="rounded-lg bg-soft px-2 py-1.5 text-[10px] text-ink-2">مومنتوم ۲۰ روزه: <b className={(signal.momentum20 ?? 0) >= 0 ? "text-up" : "text-down"}>{faPct(signal.momentum20, 1)}</b></span>
      </div>
      <p className="mt-3 rounded-xl border border-line bg-card p-3 text-[10px] leading-5 text-ink-3">
        این کارت یک قانون محاسبهٔ شفاف روی دادهٔ واقعی است (مومنتوم + میانگین + ATR)؛ سیگنال معاملاتی توصیه‌شده توسط مدل ML نیست.
      </p>
    </SectionCard>
  );
}

function HealthCard({ brs }: { brs: ReturnType<typeof useBrSHealth> }) {
  const sources: [string, string][] = [["gold_coin", "طلا و سکه"], ["currency", "ارز"], ["crypto", "کریپتو"], ["symbols", "نمادهای TSETMC"], ["commodities", "کالا/IME"]];
  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-black text-ink">سلامت داده و منابع</h3>
          <p className="mt-1 text-[11px] text-ink-3">وضعیت واقعی sync هر منبع از BrsApi</p>
        </div>
        <Database className="size-5 text-primary-500" />
      </div>
      <div className="space-y-2">
        {sources.map(([key, label]) => {
          const status = brs.sync?.[key];
          const age = status?.age_minutes;
          const ok = status?.status === "fresh";
          return (
            <div key={key} className="flex items-center justify-between rounded-xl bg-soft/70 px-3 py-2 text-xs">
              <span className="font-semibold text-ink">{label}</span>
              <span className="font-mono text-ink-3">{age === undefined || age === null ? "—" : age < 60 ? `${faNumber(age)} دقیقه` : `${faNumber(age / 60, 1)} ساعت`} پیش</span>
              <span className={ok ? "text-up" : "text-warn"}>{ok ? "سالم" : status ? "قدیمی" : "—"}</span>
            </div>
          );
        })}
        <div className="flex items-center justify-between rounded-xl bg-soft/70 px-3 py-2 text-xs">
          <span className="font-semibold text-ink">اتصال BrsApi</span>
          <span className={brs.health?.status === "connected" ? "text-up" : "text-warn"}>{brs.health?.status === "connected" ? "متصل" : "قطع/سرد"}</span>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────── stocks tab ────────────────────────── */

const STOCK_SYMBOLS = ["فزر", "فملی", "فولاد"];

function StockModule({ live }: { live: ReturnType<typeof useLiveMarketData> }) {
  const index = useTseIndex();
  const goldHistory = useSeriesHistory("IR_GOLD_18K", 250);
  const goldByDate = useMemo(() => new Map(goldHistory.pairs.map((p) => [p.date, p.close])), [goldHistory.pairs]);
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard item={{ label: "شاخص کل بورس", unit: "واحد — TSETMC/BrsApi", value: faPrice(index.value), change: index.changePct, live: !index.isLoading && index.value !== null }} />
        <MetricCard item={{ label: "انس جهانی (مبنای همبستگی)", unit: "دلار", value: faPrice(live.bySymbol.get("XAUUSD")?.price, 2), change: live.bySymbol.get("XAUUSD")?.change_percent ?? null, live: Boolean(live.bySymbol.get("XAUUSD")) }} />
      </div>
      <SectionCard title="زنجیره طلا و کانی‌های فلزی" subtitle="P/E و EPS از TSETMC · همبستگی/بتا محاسبه‌شده از بازده واقعی روزانه با طلا" icon={LineChart}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-right text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] text-ink-3">
                <th className="pb-3">نماد</th><th className="pb-3">قیمت (ریال)</th><th className="pb-3">تغییر</th><th className="pb-3">P/E</th><th className="pb-3">EPS</th><th className="pb-3">همبستگی طلا</th><th className="pb-3">بتا vs طلا</th>
              </tr>
            </thead>
            <tbody>
              {STOCK_SYMBOLS.map((symbol) => (
                <StockRow key={symbol} symbol={symbol} goldByDate={goldByDate} />
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
      <SectionCard title="تابلوی سفارشات (قدرت خریدار/فروشنده)" subtitle="حجم واقعی حقوقی/حقیقی از TSETMC" icon={Activity}>
        <div className="grid gap-3 sm:grid-cols-3">
          {STOCK_SYMBOLS.map((symbol) => (
            <OrderBookCard key={symbol} symbol={symbol} />
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

function StockRow({ symbol, goldByDate }: { symbol: string; goldByDate: Map<string, number> }) {
  const { detail } = useSymbolDetail(symbol);
  const history = useSeriesHistory(symbol, 250);
  const common = useMemo(
    () => history.pairs.filter((p) => goldByDate.has(p.date)),
    [history.pairs, goldByDate],
  );
  const corr = useMemo(
    () => (common.length > 30 ? correlation(returns(common.map((p) => p.close)), returns(common.map((p) => goldByDate.get(p.date) as number))) : null),
    [common, goldByDate],
  );
  const bta = useMemo(
    () => (common.length > 30 ? beta(returns(common.map((p) => p.close)), returns(common.map((p) => goldByDate.get(p.date) as number))) : null),
    [common, goldByDate],
  );
  return (
    <tr className="border-b border-line/60 last:border-0">
      <td className="py-3 font-bold text-ink">{symbol}<div className="mt-0.5 text-[10px] font-normal text-ink-3">{String(detail?.name ?? "—")}</div></td>
      <td className="py-3 font-mono text-ink-2">{faPrice(detail?.price_last as number | undefined)}</td>
      <td className={`py-3 font-mono ${Number(detail?.price_last_change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>{faPct(detail?.price_last_change_pct as number | undefined, 1)}</td>
      <td className="py-3 font-mono text-ink-2">{detail?.pe_ratio ? faNumber(Number(detail.pe_ratio), 1) : "—"}</td>
      <td className="py-3 font-mono text-ink-2">{detail?.eps ? faNumber(Number(detail.eps)) : "—"}</td>
      <td className="py-3 font-mono font-bold text-primary-600">{corr === null ? "—" : faNumber(corr, 2)}</td>
      <td className="py-3 font-mono text-ink-2">{bta === null ? "—" : faNumber(bta, 2)}</td>
    </tr>
  );
}

function OrderBookCard({ symbol }: { symbol: string }) {
  const { detail } = useSymbolDetail(symbol);
  const buy = Number(detail?.buy_real_volume ?? 0) + Number(detail?.buy_legal_volume ?? 0);
  const sell = Number(detail?.sell_real_volume ?? 0) + Number(detail?.sell_legal_volume ?? 0);
  const ratio = sell > 0 ? buy / sell : null;
  return (
    <div className={`rounded-xl p-3 ${ratio === null ? "bg-soft/70" : ratio >= 1 ? "bg-up/5" : "bg-down/5"}`}>
      <p className="text-[10px] text-ink-3">{symbol} — حجم سفارشات</p>
      <p className={`mt-1 font-mono text-lg font-black ${ratio === null ? "text-ink-3" : ratio >= 1 ? "text-up" : "text-down"}`}>{ratio === null ? "—" : faNumber(ratio, 2)}</p>
      <p className="text-[10px] text-ink-3">{ratio === null ? "دادهٔ تابلو موجود نیست" : ratio >= 1 ? "قدرت خریدار" : "فشار فروشنده"}</p>
    </div>
  );
}

/* ────────────────────────── crypto tab ────────────────────────── */

function CryptoModule({ live }: { live: ReturnType<typeof useLiveMarketData> }) {
  const coins = live.cryptoRows.slice(0, 10);
  const usdt = live.bySymbol.get("USDT");
  const usd = live.bySymbol.get("USD")?.price ?? null;
  const xau = live.bySymbol.get("XAUUSD")?.price ?? null;
  const paxg = live.bySymbol.get("PAXG");
  const paxgPremium = paxg?.price_usd && xau ? (paxg.price_usd / xau - 1) * 100 : null;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard item={{ label: "تتر مرجع BrsApi", unit: "تومان — USDT×نرخ دلار", value: faPrice(usdt?.price_usd && usd ? (usdt.price_usd * usd) / 10 : null, 0), change: usdt?.change_percent ?? null, live: Boolean(usdt) }} />
        <MetricCard item={{ label: "PAXG vs انس", unit: "پریمیوم طلای توکنیزه", value: faPct(paxgPremium, 2), change: paxg?.change_percent ?? null, live: Boolean(paxg) }} />
      </div>
      <SectionCard title="بالاترین ارزهای دیجیتال (BrsApi)" subtitle="قیمت دلاری و تغییر ۲۴ ساعتهٔ واقعی" icon={Sparkles}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[650px] text-right text-xs">
            <thead>
              <tr className="border-b border-line text-[10px] text-ink-3">
                <th className="pb-3">ارز</th><th className="pb-3">نماد</th><th className="pb-3">قیمت (دلار)</th><th className="pb-3">تغییر ۲۴h</th><th className="pb-3">ارزش بازار</th>
              </tr>
            </thead>
            <tbody>
              {coins.length === 0 ? (
                <tr><td colSpan={5} className="py-6 text-center text-warn">دادهٔ کریپتو دریافت نشد.</td></tr>
              ) : (
                coins.map((row) => (
                  <tr key={row.symbol} className="border-b border-line/60 last:border-0">
                    <td className="py-3 font-bold text-ink">{row.name}</td>
                    <td className="py-3 font-mono text-ink-2">{row.symbol}</td>
                    <td className="py-3 font-mono text-ink-2">{faPrice(row.price_usd, 4)}</td>
                    <td className={`py-3 font-mono font-bold ${(row.change_percent ?? 0) >= 0 ? "text-up" : "text-down"}`}>{faPct(row.change_percent, 2)}</td>
                    <td className="py-3 font-mono text-ink-2">{row.market_cap ? `${faNumber(row.market_cap / 1e9)}B$` : "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[10px] text-ink-3">اسپرد صرافی‌های داخلی (نوبیتکس/تبدیل) در BrsApi موجود نیست؛ برای این جدول منبع داده‌ای وجود ندارد و عمداً حذف شده است.</p>
      </SectionCard>
    </div>
  );
}

/* ────────────────────────── portfolio tab ────────────────────────── */

const TRADE_ASSETS: { symbol: string; label: string }[] = [
  { symbol: "IR_COIN_EMAMI", label: "سکه امامی (فیزیکی)" },
  { symbol: "IR_GOLD_18K", label: "طلای ۱۸ عیار" },
  { symbol: "USD", label: "دلار" },
  { symbol: "طلا", label: "صندوق کالای پارسیان" },
  { symbol: "عیار", label: "صندوق طلای عیار مفید" },
  { symbol: "گوهر", label: "صندوق کالای کیان" },
  { symbol: "زر", label: "صندوق کالای امید ثروت" },
  { symbol: "زرافشان", label: "زرافشان" },
];

function priceForSymbol(symbol: string, live: ReturnType<typeof useLiveMarketData>, fundCache: Map<string, number | null>): number | null {
  const row = live.bySymbol.get(symbol);
  const direct = row?.price ?? row?.price_irr ?? null;
  if (direct) return direct;
  const fund = fundCache.get(symbol);
  if (fund) return fund;
  const usdt = live.bySymbol.get("USDT");
  const usd = live.bySymbol.get("USD")?.price ?? null;
  if (symbol === "USDT" && usdt?.price_usd && usd) return usdt.price_usd * usd;
  return null;
}

function PortfolioModule({ trades, remove, live }: { trades: Trade[]; remove: (id: string) => void; live: ReturnType<typeof useLiveMarketData> }) {
  const funds = GOLD_FUNDS.map((symbol) => ({ symbol, data: useFundSnapshot(symbol) }));
  const zarafshan = useSymbolDetail("زرافشان");
  const fundCache = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const fund of funds) map.set(fund.symbol, fund.data.row?.price_last ?? null);
    map.set("زرافشان", (zarafshan.detail?.price_last as number | undefined) ?? null);
    return map;
  }, [funds.map((f) => f.data.row?.price_last).join(","), zarafshan.detail?.price_last]);
  const usdRate = live.bySymbol.get("USD")?.price ?? null;

  const positions = useMemo(() => {
    const grouped = new Map<string, { trade: Trade; quantity: number; cost: number }>();
    for (const trade of trades) {
      const existing = grouped.get(trade.symbol);
      if (trade.side === "SELL") {
        if (existing) {
          existing.quantity = Math.max(0, existing.quantity - trade.quantity);
          if (existing.quantity <= 0) grouped.delete(trade.symbol);
        }
        continue;
      }
      if (existing) {
        const totalQty = existing.quantity + trade.quantity;
        existing.cost = (existing.cost + trade.quantity * trade.entryPrice) / totalQty;
        existing.quantity = totalQty;
      } else {
        grouped.set(trade.symbol, { trade, quantity: trade.quantity, cost: trade.entryPrice });
      }
    }
    const rows = [...grouped.values()].map((entry) => {
      const price = priceForSymbol(entry.trade.symbol, live, fundCache);
      const value = price !== null ? price * entry.quantity : null;
      const pnl = price !== null ? (price / entry.cost - 1) * 100 : null;
      return { ...entry.trade, quantity: entry.quantity, cost: entry.cost, price, value, pnl };
    });
    const total = rows.reduce((sum, row) => sum + (row.value ?? 0), 0);
    return { rows, total: total > 0 ? total : null };
  }, [trades, live.bySymbol, fundCache]);

  const weightedPnl = positions.total
    ? positions.rows.reduce((sum, row) => sum + ((row.pnl ?? 0) * (row.value ?? 0)) / positions.total!, 0)
    : null;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-line bg-card p-5 shadow-[var(--shadow-card)]">
          <p className="text-xs text-ink-3">ارزش کل پورتفولیو (ریالی)</p>
          <p className="mt-2 font-mono text-2xl font-black text-ink">{positions.total === null ? "—" : `${faNumber(positions.total / 10)} تومان`}</p>
          {weightedPnl !== null && <p className={`mt-2 font-mono text-sm font-bold ${weightedPnl >= 0 ? "text-up" : "text-down"}`}>بازده ترکیبی: {faPct(weightedPnl, 1)}</p>}
          {positions.total === null && <p className="mt-2 text-[10px] text-ink-3">با ثبت اولین معاملهٔ دستی محاسبه می‌شود.</p>}
        </div>
        <div className="rounded-2xl border border-line bg-card p-5 shadow-[var(--shadow-card)]">
          <p className="text-xs text-ink-3">ارزش دلاری</p>
          <p className="mt-2 font-mono text-2xl font-black text-ink">{positions.total === null || !usdRate ? "—" : `$${faNumber(positions.total / usdRate)}`}</p>
          <p className="mt-1 text-[10px] text-ink-3">مبنای تبدیل: نرخ دلار BrsApi {faPrice(usdRate)} ریال</p>
        </div>
      </div>
      <SectionCard title="پوزیشن‌ها" subtitle="ارزش‌گذاری با قیمت لحظه‌ای BrsApi · P/L از قیمت ثبت‌شدهٔ شما" icon={WalletCards}>
        {positions.rows.length === 0 ? (
          <p className="py-6 text-center text-xs text-ink-3">هنوز معامله‌ای ثبت نشده — از فرم «ثبت دستی معامله» استفاده کنید.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-right text-xs">
              <thead>
                <tr className="border-b border-line text-[10px] text-ink-3">
                  <th className="pb-3">دارایی</th><th className="pb-3">حجم</th><th className="pb-3">قیمت ورود</th><th className="pb-3">قیمت فعلی</th><th className="pb-3">ارزش</th><th className="pb-3">وزن</th><th className="pb-3">P/L</th><th className="pb-3"></th>
                </tr>
              </thead>
              <tbody>
                {positions.rows.map((row) => (
                  <tr key={row.id} className="border-b border-line/60 last:border-0">
                    <td className="py-3"><div className="font-bold text-ink">{row.label}</div><div className="mt-0.5 font-mono text-[10px] text-ink-3">{row.symbol}</div></td>
                    <td className="py-3 font-mono text-ink-2">{faNumber(row.quantity)}</td>
                    <td className="py-3 font-mono text-ink-2">{faPrice(row.cost)}</td>
                    <td className="py-3 font-mono text-ink">{faPrice(row.price)}</td>
                    <td className="py-3 font-mono font-bold text-ink">{faPrice(row.value)}</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-line"><div className="h-full rounded-full bg-primary-500" style={{ width: `${row.value && positions.total ? (row.value / positions.total) * 100 : 0}%` }} /></div>
                        <span className="font-mono text-[10px] text-ink-3">{row.value && positions.total ? faNumber((row.value / positions.total) * 100, 1) : "—"}٪</span>
                      </div>
                    </td>
                    <td className={`py-3 font-mono font-bold ${(row.pnl ?? 0) >= 0 ? "text-up" : "text-down"}`}>{faPct(row.pnl, 1)}</td>
                    <td className="py-3"><button type="button" onClick={() => remove(row.id)} className="text-[10px] text-warn hover:underline">حذف</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

function ManualTradeEntry({ onSaved }: { onSaved: (entry: Trade) => void }) {
  const [form, setForm] = useState({ symbol: "IR_COIN_EMAMI", side: "BUY" as "BUY" | "SELL", quantity: 1, entryPrice: 0, date: new Date().toISOString().slice(0, 10) });
  const [saved, setSaved] = useState(false);
  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };
  const label = TRADE_ASSETS.find((a) => a.symbol === form.symbol)?.label ?? form.symbol;
  const valid = form.quantity > 0 && form.entryPrice > 0;
  return (
    <SectionCard title="ثبت دستی معامله" subtitle="بدون ارسال سفارش؛ فقط ثبت برای محاسبهٔ عملکرد و ریسک" icon={WalletCards}>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-[10px] text-ink-3">دارایی
          <select value={form.symbol} onChange={(event) => update("symbol", event.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs text-ink">
            {TRADE_ASSETS.map((asset) => <option key={asset.symbol} value={asset.symbol}>{asset.label}</option>)}
          </select>
        </label>
        <label className="text-[10px] text-ink-3">نوع
          <select value={form.side} onChange={(event) => update("side", event.target.value as "BUY" | "SELL")} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs text-ink">
            <option value="BUY">خرید</option><option value="SELL">فروش</option>
          </select>
        </label>
        <label className="text-[10px] text-ink-3">تاریخ
          <input type="date" value={form.date} onChange={(event) => update("date", event.target.value)} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs text-ink" />
        </label>
        <label className="text-[10px] text-ink-3">حجم / تعداد
          <input type="number" min={0} value={form.quantity || ""} onChange={(event) => update("quantity", Number(event.target.value))} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs font-mono text-ink" />
        </label>
        <label className="text-[10px] text-ink-3">قیمت ورود (ریال)
          <input type="number" min={0} value={form.entryPrice || ""} onChange={(event) => update("entryPrice", Number(event.target.value))} className="mt-1 w-full rounded-xl border border-line bg-soft px-3 py-2 text-xs font-mono text-ink" />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[10px] text-ink-3">{valid ? `${form.side === "BUY" ? "خرید" : "فروش"} ${faNumber(form.quantity)} ${label} در {faPrice(form.entryPrice)} ریال` : "حجم و قیمت ورود را وارد کنید."}</span>
        <button
          type="button"
          disabled={!valid}
          onClick={() => {
            onSaved({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, symbol: form.symbol, label, side: form.side, quantity: form.quantity, entryPrice: form.entryPrice, date: form.date });
            setSaved(true);
          }}
          className="rounded-xl bg-primary-600 px-4 py-2 text-xs font-bold text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saved ? "ثبت شد ✓" : "ثبت معامله دستی"}
        </button>
      </div>
    </SectionCard>
  );
}

/* ────────────────────────── page ────────────────────────── */

type Tab = "gold" | "stocks" | "crypto" | "portfolio";

export default function GoldMarketPage() {
  const [tab, setTab] = useState<Tab>("gold");
  const [timeframe, setTimeframe] = useState<Timeframe>("1D");
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const live = useLiveMarketData();
  const history = useGoldHistory();
  const futures = useGoldFutures();
  const news = useCodalNews();
  const brs = useBrSHealth();
  const { trades, save, remove } = useStoredTrades();

  const portfolioValue = useMemo(() => {
    let total = 0;
    let known = true;
    for (const trade of trades) {
      if (trade.side !== "BUY") continue;
      const price = priceForSymbol(trade.symbol, live, new Map());
      if (price === null) { known = false; continue; }
      total += price * trade.quantity;
    }
    return trades.length === 0 ? null : { total, known };
  }, [trades, live.bySymbol]);

  const goldSync = brs.sync?.gold_coin;

  return (
    <AppLayout title="بازار طلا" subtitle="تحلیل یکپارچه طلا، سهام، کریپتو و سبد — همهٔ داده‌ها از BrsApi.ir">
      <div className="space-y-5">
        <section className="rounded-3xl border border-primary-500/20 bg-gradient-to-br from-primary-950 via-card to-card p-5 text-white shadow-[var(--shadow-card-hover)] lg:p-6">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusPill>Real-time channel</StatusPill>
                <StatusPill>منبع واحد: BrsApi.ir</StatusPill>
                <StatusPill tone="warn">بدون داده ساختگی</StatusPill>
              </div>
              <h2 className="text-xl font-black tracking-tight lg:text-2xl">بازار طلا — کنسول تصمیم‌گیری</h2>
              <p className="mt-1 text-xs text-brand-200/80">آخرین همگام‌سازی طلا: {formatDateTime(goldSync?.last_fetched)} — وضعیت: {goldSync?.status === "fresh" ? "تازه" : goldSync ? `${faNumber((goldSync.age_minutes ?? 0) / 60, 1)} ساعت پیش` : "—"}</p>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3"><p className="text-[10px] text-brand-200/70">ارزش سبد</p><p className="mt-1 font-mono text-base font-black">{portfolioValue?.known ? `${faNumber(portfolioValue.total / 10)} تومان` : "—"}</p></div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3"><p className="text-[10px] text-brand-200/70">معاملات ثبت‌شده</p><p className="mt-1 font-mono text-base font-black">{faNumber(trades.length)}</p></div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-3"><p className="text-[10px] text-brand-200/70">تاریخچهٔ طلا</p><p className="mt-1 font-mono text-base font-black">{faNumber(history.closes.length)} روز</p></div>
            </div>
          </div>
        </section>

        <nav className="flex gap-2 overflow-x-auto rounded-2xl border border-line bg-card p-2">
          {([
            ["gold", "طلا", CircleDollarSign],
            ["stocks", "سهام", LineChart],
            ["crypto", "کریپتو", Sparkles],
            ["portfolio", "پورتفولیو", WalletCards],
          ] as const).map(([key, label, Icon]) => (
            <button key={key} onClick={() => setTab(key)} className={`flex min-w-[110px] flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${tab === key ? "bg-primary-600 text-white shadow" : "text-ink-3 hover:bg-soft hover:text-ink"}`}>
              <Icon className="size-4" />{label}
            </button>
          ))}
        </nav>

        {tab === "gold" && (
          <>
            <LiveMarketLayer live={live} />
            <section className="grid gap-5 xl:grid-cols-[1.65fr_1fr]">
              <GoldChart history={history} live={live} timeframe={timeframe} setTimeframe={setTimeframe} />
              <SignalValidation history={history} />
            </section>
            <section className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
              <EtfAnalysisTable />
              <HealthCard brs={brs} />
            </section>
            <section className="grid gap-5 xl:grid-cols-2">
              <IntrinsicDeviationCard live={live} />
              <FuturesMonitorCard futures={futures} />
            </section>
            <NewsCard news={news} />
            <StructuredSignalCard history={history} live={live} />
          </>
        )}

        {tab === "stocks" && <StockModule live={live} />}
        {tab === "crypto" && <CryptoModule live={live} />}
        {tab === "portfolio" && (
          <>
            <PortfolioModule trades={trades} remove={remove} live={live} />
            <ManualTradeEntry onSaved={save} />
          </>
        )}

        <section className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
          <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-ink">قیمت‌های لحظه‌ای تحت رصد</h3>
                <p className="mt-1 text-[11px] text-ink-3">مستقیم از BrsApi — بدون مقدار نمونه</p>
              </div>
              <WalletCards className="size-5 text-primary-500" />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-right text-xs">
                <thead>
                  <tr className="border-b border-line text-[10px] text-ink-3">
                    <th className="pb-3">نماد</th><th className="pb-3">نام</th><th className="pb-3">قیمت (ریال)</th><th className="pb-3">تغییر</th><th className="pb-3">زمان</th>
                  </tr>
                </thead>
                <tbody>
                  {["IR_COIN_EMAMI", "IR_COIN_BAHAR", "IR_GOLD_18K", "IR_GOLD_MELTED", "XAUUSD", "USD"].map((symbol) => {
                    const row = live.bySymbol.get(symbol);
                    return (
                      <tr key={symbol} className="border-b border-line/60 last:border-0">
                        <td className="py-3 font-mono font-bold text-ink">{symbol}</td>
                        <td className="py-3 text-ink-2">{row?.name ?? "—"}</td>
                        <td className="py-3 font-mono font-bold text-ink">{faPrice(row?.price ?? row?.price_irr ?? null, 0)}</td>
                        <td className={`py-3 font-mono font-bold ${(row?.change_percent ?? 0) >= 0 ? "text-up" : "text-down"}`}>{row ? faPct(row.change_percent) : "—"}</td>
                        <td className="py-3 font-mono text-[10px] text-ink-3">{row?.date ? `${row.date} ${row.time ?? ""}` : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div className="space-y-5">
            <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-ink">کنترل‌های حیاتی</h3>
                  <p className="mt-1 text-[11px] text-ink-3">معاملات خودکار غیرفعال است</p>
                </div>
                <ShieldCheck className="size-5 text-up" />
              </div>
              <div className="space-y-2">
                <div className="flex cursor-pointer items-center justify-between rounded-xl bg-soft/70 px-3 py-2.5 text-xs">
                  <span className="flex items-center gap-2 text-ink"><ShieldCheck className="size-4 text-up" />فقط سیگنال و ثبت دستی</span>
                  <input type="checkbox" checked readOnly className="accent-primary-600" />
                </div>
                <label className="flex cursor-pointer items-center justify-between rounded-xl bg-soft/70 px-3 py-2.5 text-xs">
                  <span className="flex items-center gap-2 text-ink"><Bell className="size-4 text-warn" />هشدارهای قیمت و ریسک</span>
                  <input type="checkbox" checked={alertsEnabled} onChange={(event) => setAlertsEnabled(event.target.checked)} className="accent-primary-600" />
                </label>
              </div>
            </div>
            <div className={`rounded-2xl border p-4 ${brs.health?.status === "connected" ? "border-up/25 bg-up/5" : "border-warn/25 bg-warn/5"}`}>
              <div className="flex items-start gap-3">
                {brs.health?.status === "connected" ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-up" /> : <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" />}
                <div>
                  <h3 className="text-sm font-black text-ink">وضعیت اتصال BrsApi</h3>
                  <p className="mt-1 text-xs leading-6 text-ink-2">
                    {brs.health?.status === "connected"
                      ? `متصل — ${faNumber(Number(brs.health.commodity_prices ?? 0))} رکورد کالا، ${faNumber(Number(brs.health.crypto_prices ?? 0))} کریپتو، ${faNumber(Number(brs.health.symbol_snapshots ?? 0))} اسنپ‌شات نماد`
                      : "اتصال BrsApi برقرار نیست؛ داده‌ها از آخرین کش نمایش داده می‌شود."}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-card px-4 py-3 text-[10px] text-ink-3">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex items-center gap-1.5"><Clock3 className="size-3.5" />تاریخچهٔ طلا: {faNumber(history.closes.length)} روز واقعی</span>
            <span className="flex items-center gap-1.5"><Activity className="size-3.5 text-up" />منبع: BrsApi.ir — بدون موک</span>
          </div>
          <span className="flex items-center gap-1.5"><CheckCircle2 className={`size-3.5 ${brs.health?.status === "connected" ? "text-up" : "text-warn"}`} />وضعیت سیستم: {brs.health?.status === "connected" ? "عملیاتی" : "محدود"}</span>
        </footer>
      </div>
    </AppLayout>
  );
}
