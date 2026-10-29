"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
import {
  DEFAULT_FRESHNESS_MS,
  getDataAsOf,
  isDataAsOfFresh,
  parseIsoInstant,
} from "@/lib/api-envelope";
import type {
  IndexQuote,
  MarketSession,
  NewsItem,
  QuoteItem,
  TickerItem,
  Top5Symbol,
  TopStock,
} from "@/lib/market-mock";
import { getMarketSession } from "@/lib/market-mock";

/** Minimal shapes for the new live hooks (kept local to avoid mock coupling). */
export interface FlowRow {
  symbol: string;
  name?: string;
  realNet: number;
  legalNet: number;
}

export interface ImpactRow {
  symbol: string;
  name: string;
  impact: number;
}

export interface SectorCell {
  name: string;
  changePct: number;
  count: number;
}

export interface IntradayPoint {
  time: string;
  value: number;
}

export interface GlobalQuote {
  id: string;
  title: string;
  subtitle: string;
  price: number;
  unit: string;
  changePct: number;
  spark: number[];
}

export interface FlowSummary {
  realNetB: number;
  legalNetB: number;
  queueBuy: number;
  queueSell: number;
}

export interface CalendarEvent {
  id: string;
  title: string;
  date: string; // ISO YYYY-MM-DD
  time?: string;
  country?: string;
  category?: string;
  importance?: number;
}

export interface MarketOverviewData {
  breadth: { up: number; down: number; flat: number };
  tradeValueB: number;
  volumeM: number;
  avgChangePct: number;
}

/**
 * Contract for live-data hooks. No hook in this module ever falls back to
 * mock/sample data silently — widgets must render `LiveDataBanner` when
 * `isLive` is false (after loading finished), so a backend outage or an
 * empty feed is always explicit to the user.
 */
export interface LiveDataResult<T> {
  data: T;
  /** Data was returned by the backend (empty feed ⇒ false). */
  hasData: boolean;
  /** Data carries a known timestamp inside the freshness window. */
  isFresh: boolean;
  /** Legacy: true when data exists. Use isFresh/isStale for freshness UI. */
  isLive: boolean;
  /** Data exists and its known timestamp is outside the freshness window. */
  isStale: boolean;
  /** True when the last fetch errored. */
  isError: boolean;
  /** True while the first fetch (or a refetch with no cached data) is running. */
  isLoading: boolean;
  /** Source timestamp used for freshness (when the endpoint supplies one). */
  dataAsOf?: string | null;
}

function liveResult<T>(
  data: T,
  opts: {
    hasData: boolean;
    isFresh?: boolean;
    isStale?: boolean;
    isError: boolean;
    isLoading: boolean;
    dataAsOf?: string | null;
  },
): LiveDataResult<T> {
  const hasData = opts.hasData;
  const isFresh = hasData && opts.isFresh === true;
  const isStale = hasData && opts.isStale === true;
  return {
    data,
    hasData,
    isFresh,
    isStale,
    // Kept as an existence alias for the existing empty-state consumers.
    isLive: hasData,
    isError: opts.isError,
    isLoading: opts.isLoading,
    dataAsOf: opts.dataAsOf ?? null,
  };
}

/** Newest of several envelope timestamps (e.g. a hook that joins endpoints). */
function latestAsOf(...values: Array<string | null | undefined>): string | null {
  let latest: string | null = null;
  for (const value of values) {
    if (value == null) continue;
    if (latest === null || value > latest) latest = value;
  }
  return latest;
}

/** Result for an endpoint that returns `data_as_of` in its envelope. */
function envelopeResult<T>(
  data: T,
  hasData: boolean,
  dataAsOf: string | null,
  now: number,
  isError: boolean,
  isLoading: boolean,
): LiveDataResult<T> {
  const isFresh = hasData && dataAsOf != null && isDataAsOfFresh(dataAsOf, { now });
  return liveResult(data, {
    hasData,
    isFresh,
    isStale: hasData && dataAsOf != null && !isFresh,
    isError,
    isLoading,
    dataAsOf,
  });
}

/**
 * Clock ticker for freshness computed at render time.
 *
 * Freshness must decay while a query sits in cache (e.g. a background tab
 * pauses refetching). Computing it only inside `queryFn` freezes `isLive`
 * at fetch time; this ticker re-evaluates it every 15 seconds.
 */
function useNow(intervalMs = 15_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

/**
 * Live market data layer — fetches the real backend endpoints ONLY. Widgets
 * decide how to surface the degraded state via LiveDataBanner; this module
 * never substitutes fake numbers.
 */

// ── Types ────────────────────────────────────────────────────────────────

interface HeatmapCell {
  symbol: string;
  name?: string;
  change: number;
  price?: number;
  value?: number;
  volume?: number;
  market?: string;
}

interface RawIndex {
  id?: number | string;
  name?: string;
  index_value?: number;
  index_change?: number;
  index_change_pct?: number;
  index_equal_weight?: number;
  index_equal_weight_change?: number;
}

interface DashboardOverview {
  total_instruments?: number;
  total_quotes?: number;
  gainers?: number;
  losers?: number;
  unchanged?: number;
  total_value?: number;
  total_volume?: number;
  avg_change_pct?: number;
}

interface PriceRow {
  symbol: string;
  name?: string;
  price?: number;
  change_value?: number;
  change_percent?: number;
  unit?: string;
}

interface CryptoRow extends PriceRow {
  price_irr?: number;
}

// ── Mapping helpers ──────────────────────────────────────────────────────

function sparkFromChange(value: number, n = 8): number[] {
  if (!value) return [0, 0, 0, 0, 0, 0, 0, 0];
  const out: number[] = [];
  let v = value * 0.9;
  for (let i = 0; i < n; i++) {
    v += (value - v) / (n - i + 1);
    out.push(v);
  }
  return out;
}

function mapHeatmapToTicker(cells: HeatmapCell[]): TickerItem[] {
  return cells.slice(0, 24).map((c) => ({
    symbol: c.symbol,
    price: c.price ?? 0,
    changePct: c.change,
    market: c.market || "بورس",
  }));
}

function mapHeatmapToStocks(cells: HeatmapCell[]): TopStock[] {
  return cells.map((c) => ({
    symbol: c.symbol,
    name: c.name ?? "",
    price: c.price ?? 0,
    changePct: c.change,
    tradeValueB: (c.value ?? 0) / 1e12,
  }));
}

function mapIndices(raw: RawIndex[]): IndexQuote[] {
  return raw.map((r) => {
    const change = r.index_change ?? 0;
    return {
      id: String(r.id ?? r.name ?? "idx"),
      name: r.name || "شاخص",
      short: r.name || "شاخص",
      value: r.index_value ?? 0,
      change,
      changePct: r.index_change_pct ?? 0,
      spark: sparkFromChange(change),
    };
  });
}

/** Pick specific symbols from a price list by symbol code. */
function pickSymbols<T extends PriceRow>(rows: T[], symbols: string[]): T[] {
  const bySymbol = new Map(rows.map((r) => [r.symbol, r]));
  return symbols.map((s) => bySymbol.get(s)).filter(Boolean) as T[];
}

const QUOTE_KIND: Record<string, QuoteItem["kind"]> = {
  IR_GOLD_18K: "gold",
  IR_GOLD_24K: "gold",
  IR_COIN_EMAMI: "coin",
  IR_COIN_BAHAR: "coin",
  USD: "dollar",
  USDT: "tether",
  EUR: "euro",
  AED: "dirham",
  GBP: "dollar",
  TRY: "dollar",
};

function mapPriceToQuote(row: PriceRow): QuoteItem | null {
  const kind = QUOTE_KIND[row.symbol];
  if (!kind) return null;
  return {
    id: row.symbol,
    title: row.name || row.symbol,
    subtitle: row.symbol,
    price: row.price ?? 0,
    unit: "تومان",
    change: row.change_value ?? 0,
    changePct: row.change_percent ?? 0,
    spark: sparkFromChange(row.change_percent ?? 0),
    kind,
  };
}

// ── Hooks ────────────────────────────────────────────────────────────────

/**
 * وضعیت زنده بازار (باز/بسته/تعطیل) بر اساس ساعت تهران.
 * هر ثانیه دوباره محاسبه می‌شود تا هم با تغییر ساعت همگام بماند و
 * هم countdown رویداد بعدی (بازگشایی/بستن) در TickerBar دقیق تیک بزند.
 */
export function useMarketSession(): MarketSession {
  // Keep the first render identical on the server and in the browser. Reading
  // the current time during render makes the dashboard hydrate with different
  // text around minute/day boundaries and can replace the whole page.
  const [session, setSession] = useState<MarketSession>({
    dateFa: "—",
    status: "در حال بارگذاری",
    note: "در حال دریافت وضعیت بازار",
    isOpen: false,
    holiday: null,
    nextEventAt: null,
    nextEventLabel: "",
  });

  useEffect(() => {
    setSession(getMarketSession());
    const id = setInterval(() => {
      setSession(getMarketSession());
    }, 1_000);
    return () => clearInterval(id);
  }, []);

  return session;
}

/**
 * Single source of truth for the live symbol snapshot feed. All dashboard
 * lists (ticker, top gainers, TSE/OTC tables, top performers) derive from
 * this one query so the browser makes a single request instead of four.
 */
/** دادهٔ کوئری به‌همراه متادیتای پاکت؛ `data_as_of` مرجع تازگی است. */
interface HeatmapFeed {
  cells: HeatmapCell[];
  dataAsOf: string | null;
}

/** تازگی یک ردیف از `fetched_at` خودش — فقط وقتی پاکت `data_as_of` ندارد. */
function isRowFresh(cell: HeatmapCell, now: number): boolean {
  const raw = (cell as { fetched_at?: string | null }).fetched_at;
  if (!raw) return false;
  const fetched = parseIsoInstant(raw);
  // تاریخ آینده نشانهٔ ساعت اشتباه یا دادهٔ ساختگی است، نه تازگی.
  if (fetched === null || fetched > now + 2 * 60 * 1000) return false;
  return now - fetched <= DEFAULT_FRESHNESS_MS;
}

/** Newest valid `fetched_at` carried by the rows (ISO string), if any. */
function newestRowFetchedAt(cells: HeatmapCell[]): string | null {
  let latestMs = Number.NEGATIVE_INFINITY;
  let latest: string | null = null;
  for (const cell of cells) {
    const raw = (cell as { fetched_at?: string | null }).fetched_at;
    const ms = parseIsoInstant(raw);
    if (ms !== null && ms > latestMs) {
      latestMs = ms;
      latest = raw ?? null;
    }
  }
  return latest;
}

/**
 * Single source of truth for the live symbol snapshot feed.
 *
 * Freshness is computed at render time from `data_as_of` (or the rows'
 * `fetched_at`) using the ticking clock, so cached data becomes stale even
 * when React Query stops refetching in a background tab.
 */
export function useEnrichedHeatmap(limit = 500): LiveDataResult<HeatmapCell[]> {
  const now = useNow();
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-heatmap", limit],
    queryFn: async (): Promise<HeatmapFeed> => {
      const res = await apiGet<{
        success?: boolean;
        data?: HeatmapCell[];
        data_as_of?: string | null;
      }>(`/market/enriched-heatmap?limit=${limit}`);
      // `success:false` هرگز به این‌جا نمی‌رسد (`api.ts` پرتاب می‌کند)، پس
      // آرایهٔ خالی یعنی «موفق و خالی» — نه قطعی سرور.
      return { cells: extractArray<HeatmapCell>(res), dataAsOf: getDataAsOf(res) };
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
  // آرایهٔ خام فقط از کش قدیمی/HMR می‌تواند برسد؛ آن را «خالی» می‌خوانیم.
  const feed = data && !Array.isArray(data) ? data : null;
  const cells = feed?.cells ?? [];
  const hasData = cells.length > 0;
  const knownAsOf = feed?.dataAsOf ?? newestRowFetchedAt(cells);
  const hasClock = now > 0;
  const isFresh =
    hasData &&
    hasClock &&
    (feed?.dataAsOf
      ? isDataAsOfFresh(feed.dataAsOf, { now })
      : cells.every((cell) => isRowFresh(cell, now)));
  const isStale = hasData && hasClock && knownAsOf != null && !isFresh;
  return liveResult(cells, {
    hasData,
    isFresh,
    isStale,
    isError,
    isLoading,
    dataAsOf: knownAsOf,
  });
}

/** Live ticker / sitebar strip — top symbols by value from the heatmap. */
export function useTickerItems(): LiveDataResult<TickerItem[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToTicker([...hm.data].sort((a, b) => (b.value || 0) - (a.value || 0)))
      : [];
  return liveResult(mapped, {
    hasData: mapped.length > 0,
    isFresh: hm.isFresh && mapped.length > 0,
    isStale: hm.isStale && mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
    dataAsOf: hm.dataAsOf,
  });
}

/** Live indices — شاخص کل / هم‌وزن / فرابورس / … from /market/indices. */
export function useIndices(): LiveDataResult<IndexQuote[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-indices"],
    queryFn: async (): Promise<{ rows: IndexQuote[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: RawIndex[]; data_as_of?: string | null }>(
        "/market/indices"
      );
      return {
        rows: mapIndices(extractArray<RawIndex>(res)),
        dataAsOf: getDataAsOf(res),
      };
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live news strip from /news. */
export function useNewsItems(): LiveDataResult<NewsItem[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-news"],
    queryFn: async (): Promise<{ rows: NewsItem[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: { items: NewsItem[] }; data_as_of?: string | null }>(
        "/news?page_size=6"
      );
      const items = res?.data?.items ?? [];
      const rows = items.slice(0, 6).map((n, i) => {
        const publishedAt = (n as NewsItem).published_at ?? (n as { publish_date?: string }).publish_date;
        return {
          id: n.id || `news-${i}`,
          title: n.title,
          source: n.source || "بازار",
          published_at: publishedAt,
          time: publishedAt
            ? new Date(publishedAt).toLocaleTimeString("fa-IR", {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "",
          sentiment: "neutral",
          symbols: [],
        } satisfies NewsItem;
      });
      return { rows, dataAsOf: getDataAsOf(res) ?? latestAsOf(...rows.map((r) => r.published_at)) };
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live market breadth, value & volume from market-dashboard overview. */
export function useMarketOverview(): LiveDataResult<MarketOverviewData | null> {
  const now = useNow();
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-overview"],
    queryFn: async (): Promise<{ value: MarketOverviewData | null; dataAsOf: string | null }> => {
      const res = await apiGet<{
        success: boolean;
        data_as_of?: string | null;
        data: { overview?: { value?: DashboardOverview } };
      }>("/market-dashboard");
      const ov = res?.data?.overview?.value;
      const dataAsOf = getDataAsOf(res);
      if (ov && typeof ov.gainers === "number") {
        return {
          value: {
            breadth: {
              up: ov.gainers ?? 0,
              down: ov.losers ?? 0,
              flat: ov.unchanged ?? 0,
            },
            tradeValueB: (ov.total_value ?? 0) / 1e12,
            volumeM: (ov.total_volume ?? 0) / 1e6,
            avgChangePct: ov.avg_change_pct ?? 0,
          },
          dataAsOf,
        };
      }
      return { value: null, dataAsOf };
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  // Audit FE-04: freshness comes from the envelope's ``data_as_of`` instead of
  // a hard-coded ``false``.
  const value = data?.value ?? null;
  return envelopeResult(value, value != null, data?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live top gainers (≥10) from enriched heatmap — used by TopStocksToday. */
export function useTopStocks(): LiveDataResult<TopStock[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToStocks(hm.data).sort((a, b) => b.changePct - a.changePct)
      : [];
  return liveResult(mapped, {
    hasData: mapped.length > 0,
    isFresh: hm.isFresh && mapped.length > 0,
    isStale: hm.isStale && mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
    dataAsOf: hm.dataAsOf,
  });
}

/** Live top symbols by value, split by market (بورس / فرابورس) — 10 each. */
export function useActiveSymbols(): LiveDataResult<{ tse: Top5Symbol[]; otc: Top5Symbol[] }> {
  const hm = useEnrichedHeatmap();
  const byValue = (rows: HeatmapCell[]) =>
    [...rows]
      .sort((a, b) => (b.value || 0) - (a.value || 0))
      .slice(0, 10)
      .map<Top5Symbol>((c) => ({
        symbol: c.symbol,
        name: c.name ?? "",
        tradeValueB: (c.value ?? 0) / 1e12,
        changePct: c.change,
      }));
  // NB: "فرابورس" contains "بورس" as a substring — an includes("بورس") filter
  // alone leaks OTC rows into the TSE table (a real misclassification the old
  // mock fallback used to hide).
  const market = (c: HeatmapCell) => c.market || "";
  const tse = byValue(hm.data.filter((c) => market(c).includes("بورس") && !market(c).includes("فرابورس")));
  const otc = byValue(hm.data.filter((c) => market(c).includes("فرابورس")));
  return liveResult(
    { tse, otc },
    {
      hasData: tse.length > 0 || otc.length > 0,
      isFresh: hm.isFresh && (tse.length > 0 || otc.length > 0),
      isStale: hm.isStale && (tse.length > 0 || otc.length > 0),
      isError: hm.isError,
      isLoading: hm.isLoading,
      dataAsOf: hm.dataAsOf,
    },
  );
}

/** Live quote cards (طلا / سکه / ارز / تتر / دلار) from brsapi endpoints. */
export function useQuoteCards(): LiveDataResult<QuoteItem[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-quote-cards"],
    queryFn: async (): Promise<{ rows: QuoteItem[]; dataAsOf: string | null }> => {
      const [goldRes, curRes, cryptoRes] = await Promise.all([
        apiGet<{ success: boolean; data: PriceRow[]; data_as_of?: string | null }>("/brsapi/gold-coin"),
        apiGet<{ success: boolean; data: PriceRow[]; data_as_of?: string | null }>("/brsapi/currency"),
        apiGet<{ success: boolean; data: CryptoRow[]; data_as_of?: string | null }>("/brsapi/crypto?limit=200&sort_by=rank"),
      ]);
      const gold = extractArray<PriceRow>(goldRes);
      const cur = extractArray<PriceRow>(curRes);
      const crypto = extractArray<CryptoRow>(cryptoRes);
      const cryptoAsPrice = crypto.map<PriceRow>((c) => ({
        ...c,
        price: c.price_irr ?? c.price,
      }));
      // Show up to 10 quote cards: 2 gold, 2 coins, dollar, tether, euro,
      // dirham + extra currencies. Crypto rows only supply USDT and only when
      // a real IRR price exists (price_irr) — a zero/1$ price would look broken.
      const wanted = [
        "IR_GOLD_18K", "IR_GOLD_24K", "IR_COIN_EMAMI", "IR_COIN_BAHAR",
        "USD", "USDT", "EUR", "AED", "GBP", "TRY",
      ];
      const rows = [
        ...pickSymbols(gold, wanted),
        ...pickSymbols(cur, wanted),
        ...pickSymbols(cryptoAsPrice, wanted).filter(
          (c) => c.symbol === "USDT" && (c.price ?? 0) > 1000
        ),
      ];
      const seen = new Set<string>();
      const quotes: QuoteItem[] = [];
      for (const row of rows) {
        if (seen.has(row.symbol)) continue;
        seen.add(row.symbol);
        const q = mapPriceToQuote(row);
        if (q) quotes.push(q);
        if (quotes.length >= 10) break;
      }
      return {
        rows: quotes,
        dataAsOf: latestAsOf(
          getDataAsOf(goldRes),
          getDataAsOf(curRes),
          getDataAsOf(cryptoRes),
        ),
      };
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live top performers for LiquidityBlocks — shares the same heatmap query. */
export function useTopPerformers(): LiveDataResult<TopStock[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToStocks(hm.data).sort((a, b) => b.changePct - a.changePct)
      : [];
  return liveResult(mapped, {
    hasData: mapped.length > 0,
    isFresh: hm.isFresh && mapped.length > 0,
    isStale: hm.isStale && mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
    dataAsOf: hm.dataAsOf,
  });
}

// ── New live hooks (dashboard wiring) ─────────────────────────────────

/** Live global markets (gold oz / brent / BTC) from BrsApi commodities + crypto. */
export function useGlobalMarkets(): LiveDataResult<GlobalQuote[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-global-markets"],
    queryFn: async (): Promise<{ rows: GlobalQuote[]; dataAsOf: string | null }> => {
      const [comRes, btcRes] = await Promise.all([
        apiGet<{ success: boolean; data: Array<Record<string, unknown>>; data_as_of?: string | null }>("/brsapi/commodities"),
        apiGet<{ success: boolean; data: Array<Record<string, unknown>>; data_as_of?: string | null }>("/brsapi/crypto?limit=50&sort_by=rank"),
      ]);
      const commodities = extractArray<Record<string, unknown>>(comRes);
      const cryptos = extractArray<Record<string, unknown>>(btcRes);
      const find = (rows: Array<Record<string, unknown>>, keys: string[]) =>
        rows.find((r) => {
          const sym = String(r.symbol ?? "").toUpperCase();
          const name = String(r.name ?? "");
          return keys.some((k) => sym.includes(k) || name.includes(k));
        });
      const quotes: GlobalQuote[] = [];
      const push = (id: string, title: string, subtitle: string, unit: string, row?: Record<string, unknown>) => {
        if (!row) return;
        const price = Number(row.price ?? row.price_usd ?? 0);
        const changePct = Number(row.change_percent ?? row.changePct ?? 0);
        if (!price) return;
        quotes.push({ id, title, subtitle, price, unit, changePct, spark: sparkFromChange(changePct) });
      };
      const goldOz = find(commodities, ["GOLD", "XAU"]);
      const brent = find(commodities, ["BRENT", "OIL", "WTI"]);
      const btc = find(cryptos, ["BTC", "BITCOIN"]);
      push("gold-oz", "انس طلا", "کامکس", "دلار", goldOz);
      push("brent", "نفت برنت", "ICE", "دلار", brent);
      push("btc", "بیت‌کوین", "رمزارز", "دلار", btc);
      return {
        rows: quotes,
        dataAsOf: latestAsOf(getDataAsOf(comRes), getDataAsOf(btcRes)),
      };
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live شاخص کل intraday / multi-day history from brsapi_index_values. */
/**
 * Point budget per index-history range button. The endpoint serves intraday
 * snapshots (limit 10..300, ~1 point every 2 minutes during the session).
 */
export const INDEX_RANGE_LIMITS = [30, 60, 120, 180, 300] as const;

export function useIndexIntraday(rangeIdx = 0): LiveDataResult<IntradayPoint[]> {
  const now = useNow();
  // Audit FE-07: the range was only part of the query key — every button hit
  // the same ``limit=60`` URL. The endpoint serves intraday snapshots (limit
  // 10..300), so each button maps to a point budget of roughly 2h/4h/…
  const limit = INDEX_RANGE_LIMITS[Math.min(Math.max(rangeIdx, 0), INDEX_RANGE_LIMITS.length - 1)];
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-index-intraday", rangeIdx],
    queryFn: async (): Promise<{ points: IntradayPoint[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: Array<Record<string, unknown>>; data_as_of?: string | null }>(
        `/market/index-history/%D8%B4%D8%A7%D8%AE%D8%B5%20%DA%A9%D9%84?limit=${limit}`
      );
      const rows = extractArray<Record<string, unknown>>(res);
      return {
        points: rows
          .map((r) => ({
            time: String(r.fetched_at ?? r.created_at ?? "").slice(11, 16) || "—",
            value: Number(r.index_value ?? 0),
          }))
          .filter((p) => p.value > 0),
        dataAsOf: getDataAsOf(res),
      };
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const points = feed?.points ?? [];
  return envelopeResult(points, points.length >= 2, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live sector map from /market/treemap (stocks view aggregates by sector). */
export function useSectorMap(): LiveDataResult<SectorCell[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-sector-map"],
    queryFn: async (): Promise<{ rows: SectorCell[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: { children?: Array<{ name: string; children?: Array<{ change: number }> }> }; data_as_of?: string | null }>(
        "/market/treemap?limit=2000"
      );
      const sectors = res?.data?.children ?? [];
      const rows = sectors
        .map((s) => ({
          name: s.name,
          count: s.children?.length ?? 0,
          changePct:
            s.children && s.children.length > 0
              ? s.children.reduce((acc, c) => acc + (Number(c.change) || 0), 0) / s.children.length
              : 0,
        }))
        .filter((c) => c.count > 0)
        .sort((a, b) => b.changePct - a.changePct)
        .slice(0, 20);
      return { rows, dataAsOf: getDataAsOf(res) };
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live per-symbol real/legal net flow (top movers) for OwnershipChange. */
export function useOwnershipFlows(): LiveDataResult<FlowRow[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-ownership-flows"],
    queryFn: async (): Promise<FlowRow[]> => {
      const res = await apiGet<{ success: boolean; data: Array<{ symbol: string; real_net_b: number; legal_net_b: number }> }>(
        "/market/flow-history?limit=8"
      );
      const rows = extractArray<{ symbol: string; real_net_b: number; legal_net_b: number }>(res);
      return rows.map((r) => ({ symbol: r.symbol, name: r.symbol, realNet: r.real_net_b, legalNet: r.legal_net_b }));
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  const rows = data ?? [];
  return liveResult(rows, {
    hasData: rows.length > 0,
    isFresh: false,
    isStale: false,
    isError,
    isLoading,
  });
}

/** Live market-wide real/legal totals + queue counts for LiquidityBlocks / MarketOverview. */
export interface FlowSummaryResult {
  summary: FlowSummary | null;
  isError: boolean;
}

export function useFlowSummary(): FlowSummaryResult {
  const { data, isError } = useQuery({
    queryKey: ["live-flow-summary"],
    queryFn: async (): Promise<FlowSummary | null> => {
      const res = await apiGet<{ success: boolean; data: { real_net_b: number; legal_net_b: number; queue_buy: number; queue_sell: number } }>(
        "/market/flow-summary"
      );
      const d = res?.data;
      if (d && typeof d.real_net_b === "number") {
        return { realNetB: d.real_net_b, legalNetB: d.legal_net_b, queueBuy: d.queue_buy, queueSell: d.queue_sell };
      }
      return null;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  // Audit FE-02: a failed request is reported as an error, not as a measured
  // zero. Callers must render "—"/hide the sentence instead of ``?? 0``.
  return { summary: data ?? null, isError };
}

/**
 * Live index-impact approximation from the enriched heatmap: the symbols
 * with the largest absolute (change_pct × market cap proxy) split into
 * positive/negative leaders. True TSE index contribution needs the official
 * weights feed; this is the best available real-data proxy.
 */
export function useIndexImpacts(): LiveDataResult<{ positive: ImpactRow[]; negative: ImpactRow[] }> {
  const hm = useEnrichedHeatmap();
  const cells = hm.data;
  const impacts = (() => {
    if (cells.length === 0) return { positive: [], negative: [] };
    const scored = cells
      .map((c) => ({
        symbol: c.symbol,
        name: c.name ?? c.symbol,
        impact: (c.change || 0) * Math.log10(1 + (c.value || 0) / 1e9),
      }))
      .sort((a, b) => b.impact - a.impact);
    return {
      positive: scored.filter((r) => r.impact > 0).slice(0, 5),
      negative: scored.filter((r) => r.impact < 0).slice(-5).reverse(),
    };
  })();
  const hasData = impacts.positive.length > 0 || impacts.negative.length > 0;
  return liveResult(impacts, {
    hasData,
    isFresh: hm.isFresh && hasData,
    isStale: hm.isStale && hasData,
    isError: hm.isError,
    isLoading: hm.isLoading,
    dataAsOf: hm.dataAsOf,
  });
}

/** Live economic/market events from /economic-calendar (upcoming 30 days). */
export function useMarketEvents(): LiveDataResult<CalendarEvent[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-market-events"],
    queryFn: async (): Promise<CalendarEvent[]> => {
      const res = await apiGet<{ success: boolean; data: { events?: Array<Record<string, unknown>> } | Array<Record<string, unknown>> }>(
        "/economic-calendar?min_importance=1"
      );
      const raw = Array.isArray(res?.data) ? res.data : (res?.data?.events ?? []);
      return (raw as Array<Record<string, unknown>>)
        .map((e, i) => ({
          id: String(e.id ?? `ev-${i}`),
          title: String(e.title ?? ""),
          date: String(e.date ?? ""),
          time: e.time ? String(e.time) : undefined,
          country: e.country ? String(e.country) : undefined,
          category: e.category ? String(e.category) : undefined,
          importance: typeof e.importance === "number" ? e.importance : undefined,
        }))
        .slice(0, 8);
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
    retry: 1,
  });
  const rows = data ?? [];
  return liveResult(rows, {
    hasData: rows.length > 0,
    isFresh: false,
    isStale: false,
    isError,
    isLoading,
  });
}

// ── AssetAllocationPie ────────────────────────────────────────────────

export interface AssetSliceLive {
  label: string;
  valueB: number;
  pct: number;
}

/**
 * Live market-wide asset-class allocation from /market/asset-allocation.
 * Classification is name-based on the backend (سهام/سرمایه‌گذاری/صندوق‌ها/
 * اوراق) — an approximation, not an official TSE feed.
 */
export function useAssetAllocation(): LiveDataResult<AssetSliceLive[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-asset-allocation"],
    queryFn: async (): Promise<{ rows: AssetSliceLive[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: Array<{ label: string; value_b: number; pct: number }> }>(
        "/market/asset-allocation?limit=2000"
      );
      return {
        rows: extractArray<{ label: string; value_b: number; pct: number }>(res).map((r) => ({
          label: r.label,
          valueB: r.value_b,
          pct: r.pct,
        })),
        dataAsOf: getDataAsOf(res),
      };
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

// ── TripleChartsGroup aggregates ──────────────────────────────────────

export interface SectorFlowBar {
  name: string;
  valueB: number;
}

export interface ValueDayBar {
  day: string;
  date: string;
  valueB: number;
}

export interface OwnershipDayBar {
  day: string;
  date: string;
  realB: number;
  legalB: number;
}

/** Live per-sector real money flow (today) from /market/cashflow-by-sector. */
export function useCashflowBySector(): LiveDataResult<SectorFlowBar[]> {
  const now = useNow();
  const { data: feed, isError, isLoading } = useQuery({
    queryKey: ["live-cashflow-by-sector"],
    queryFn: async (): Promise<{ rows: SectorFlowBar[]; dataAsOf: string | null }> => {
      const res = await apiGet<{ success: boolean; data: Array<{ name: string; value_b: number }> }>(
        "/market/cashflow-by-sector?limit=500"
      );
      return {
        rows: extractArray<{ name: string; value_b: number }>(res).map((r) => ({
          name: r.name,
          valueB: r.value_b,
        })),
        dataAsOf: getDataAsOf(res),
      };
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = feed?.rows ?? [];
  return envelopeResult(rows, rows.length > 0, feed?.dataAsOf ?? null, now, isError, isLoading);
}

/** Live daily market trade value from /market/value-history. */
export function useValueHistory(): LiveDataResult<ValueDayBar[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-value-history"],
    queryFn: async (): Promise<ValueDayBar[]> => {
      const res = await apiGet<{ success: boolean; data: Array<{ date: string; day: string; value_b: number }> }>(
        "/market/value-history?days=5"
      );
      return extractArray<{ date: string; day: string; value_b: number }>(res).map((r) => ({
        day: r.day,
        date: r.date,
        valueB: r.value_b,
      }));
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
    retry: 1,
  });
  const rows = data ?? [];
  return liveResult(rows, {
    hasData: rows.length > 0,
    isFresh: false,
    isStale: false,
    isError,
    isLoading,
  });
}

/** Live daily real/legal net flow from /market/ownership-history. */
export function useOwnershipHistory(): LiveDataResult<OwnershipDayBar[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-ownership-history"],
    queryFn: async (): Promise<OwnershipDayBar[]> => {
      const res = await apiGet<{ success: boolean; data: Array<{ date: string; day: string; real_b: number; legal_b: number }> }>(
        "/market/ownership-history?days=5"
      );
      return extractArray<{ date: string; day: string; real_b: number; legal_b: number }>(res).map((r) => ({
        day: r.day,
        date: r.date,
        realB: r.real_b,
        legalB: r.legal_b,
      }));
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
    retry: 1,
  });
  const rows = data ?? [];
  return liveResult(rows, {
    hasData: rows.length > 0,
    isFresh: false,
    isStale: false,
    isError,
    isLoading,
  });
}
