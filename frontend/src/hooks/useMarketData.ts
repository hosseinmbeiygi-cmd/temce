"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
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
  /** True when the backend returned usable live data. */
  isLive: boolean;
  /** True when the last fetch errored. */
  isError: boolean;
  /** True while the first fetch (or a refetch with no cached data) is running. */
  isLoading: boolean;
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
function useEnrichedHeatmap(): LiveDataResult<HeatmapCell[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-heatmap"],
    queryFn: async (): Promise<HeatmapCell[]> => {
      const res = await apiGet<{ success: boolean; data: HeatmapCell[] }>(
        "/market/enriched-heatmap?limit=120"
      );
      const arr = extractArray<HeatmapCell>(res);
      if (arr.length === 0 && (res as unknown as Record<string, unknown>)?.success === false) {
        console.warn("[useEnrichedHeatmap] backend returned success:false", res);
      }
      return arr;
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
  const cells = data ?? [];
  return { data: cells, isLive: cells.length > 0, isError, isLoading };
}

/** Live ticker / sitebar strip — top symbols by value from the heatmap. */
export function useTickerItems(): LiveDataResult<TickerItem[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToTicker([...hm.data].sort((a, b) => (b.value || 0) - (a.value || 0)))
      : [];
  return {
    data: mapped,
    isLive: mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
  };
}

/** Live indices — شاخص کل / هم‌وزن / فرابورس / … from /market/indices. */
export function useIndices(): LiveDataResult<IndexQuote[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-indices"],
    queryFn: async (): Promise<IndexQuote[]> => mapIndices(
      extractArray<RawIndex>(
        await apiGet<{ success: boolean; data: RawIndex[] }>("/market/indices")
      )
    ),
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}

/** Live news strip from /news. */
export function useNewsItems(): LiveDataResult<NewsItem[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-news"],
    queryFn: async (): Promise<NewsItem[]> => {
      const res = await apiGet<{ success: boolean; data: { items: NewsItem[] } }>(
        "/news?page_size=6"
      );
      const items = res?.data?.items ?? [];
      return items.slice(0, 6).map((n, i) => {
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
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}

/** Live market breadth, value & volume from market-dashboard overview. */
export function useMarketOverview(): LiveDataResult<MarketOverviewData | null> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-overview"],
    queryFn: async (): Promise<MarketOverviewData | null> => {
      const res = await apiGet<{
        success: boolean;
        data: { overview?: { value?: DashboardOverview } };
      }>("/market-dashboard");
      const ov = res?.data?.overview?.value;
      if (ov && typeof ov.gainers === "number") {
        return {
          breadth: {
            up: ov.gainers ?? 0,
            down: ov.losers ?? 0,
            flat: ov.unchanged ?? 0,
          },
          tradeValueB: (ov.total_value ?? 0) / 1e12,
          volumeM: (ov.total_volume ?? 0) / 1e6,
          avgChangePct: ov.avg_change_pct ?? 0,
        };
      }
      return null;
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  return { data: data ?? null, isLive: data != null, isError, isLoading };
}

/** Live top gainers (≥10) from enriched heatmap — used by TopStocksToday. */
export function useTopStocks(): LiveDataResult<TopStock[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToStocks(hm.data).sort((a, b) => b.changePct - a.changePct)
      : [];
  return {
    data: mapped,
    isLive: mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
  };
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
  return {
    data: { tse, otc },
    isLive: tse.length > 0 || otc.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
  };
}

/** Live quote cards (طلا / سکه / ارز / تتر / دلار) from brsapi endpoints. */
export function useQuoteCards(): LiveDataResult<QuoteItem[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-quote-cards"],
    queryFn: async (): Promise<QuoteItem[]> => {
      const [goldRes, curRes, cryptoRes] = await Promise.all([
        apiGet<{ success: boolean; data: PriceRow[] }>("/brsapi/gold-coin"),
        apiGet<{ success: boolean; data: PriceRow[] }>("/brsapi/currency"),
        apiGet<{ success: boolean; data: CryptoRow[] }>("/brsapi/crypto?limit=200&sort_by=rank"),
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
      return quotes;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}

/** Live top performers for LiquidityBlocks — shares the same heatmap query. */
export function useTopPerformers(): LiveDataResult<TopStock[]> {
  const hm = useEnrichedHeatmap();
  const mapped =
    hm.data.length > 0
      ? mapHeatmapToStocks(hm.data).sort((a, b) => b.changePct - a.changePct)
      : [];
  return {
    data: mapped,
    isLive: mapped.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
  };
}

// ── New live hooks (dashboard wiring) ─────────────────────────────────

/** Live global markets (gold oz / brent / BTC) from BrsApi commodities + crypto. */
export function useGlobalMarkets(): LiveDataResult<GlobalQuote[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-global-markets"],
    queryFn: async (): Promise<GlobalQuote[]> => {
      const [comRes, btcRes] = await Promise.all([
        apiGet<{ success: boolean; data: Array<Record<string, unknown>> }>("/brsapi/commodities"),
        apiGet<{ success: boolean; data: Array<Record<string, unknown>> }>("/brsapi/crypto?limit=50&sort_by=rank"),
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
      return quotes;
    },
    refetchInterval: 300_000,
    staleTime: 120_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}

/** Live شاخص کل intraday / multi-day history from brsapi_index_values. */
export function useIndexIntraday(rangeIdx = 0): LiveDataResult<IntradayPoint[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-index-intraday", rangeIdx],
    queryFn: async (): Promise<IntradayPoint[]> => {
      const res = await apiGet<{ success: boolean; data: Array<Record<string, unknown>> }>(
        "/market/index-history/%D8%B4%D8%A7%D8%AE%D8%B5%20%DA%A9%D9%84?limit=60"
      );
      const rows = extractArray<Record<string, unknown>>(res);
      return rows
        .map((r) => ({
          time: String(r.fetched_at ?? r.created_at ?? "").slice(11, 16) || "—",
          value: Number(r.index_value ?? 0),
        }))
        .filter((p) => p.value > 0);
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const points = data ?? [];
  return { data: points, isLive: points.length >= 2, isError, isLoading };
}

/** Live sector map from /market/treemap (stocks view aggregates by sector). */
export function useSectorMap(): LiveDataResult<SectorCell[]> {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-sector-map"],
    queryFn: async (): Promise<SectorCell[]> => {
      const res = await apiGet<{ success: boolean; data: { children?: Array<{ name: string; children?: Array<{ change: number }> }> } }>(
        "/market/treemap?limit=2000"
      );
      const sectors = res?.data?.children ?? [];
      return sectors
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
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
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
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}

/** Live market-wide real/legal totals + queue counts for LiquidityBlocks / MarketOverview. */
export function useFlowSummary(): FlowSummary | null {
  const { data } = useQuery({
    queryKey: ["live-flow-summary"],
    queryFn: async (): Promise<FlowSummary | null> => {
      try {
        const res = await apiGet<{ success: boolean; data: { real_net_b: number; legal_net_b: number; queue_buy: number; queue_sell: number } }>(
          "/market/flow-summary"
        );
        const d = res?.data;
        if (d && typeof d.real_net_b === "number") {
          return { realNetB: d.real_net_b, legalNetB: d.legal_net_b, queueBuy: d.queue_buy, queueSell: d.queue_sell };
        }
      } catch {
        /* fall through to null */
      }
      return null;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  return data ?? null;
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
  return {
    data: impacts,
    isLive: impacts.positive.length > 0 || impacts.negative.length > 0,
    isError: hm.isError,
    isLoading: hm.isLoading,
  };
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
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
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
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-asset-allocation"],
    queryFn: async (): Promise<AssetSliceLive[]> => {
      const res = await apiGet<{ success: boolean; data: Array<{ label: string; value_b: number; pct: number }> }>(
        "/market/asset-allocation?limit=2000"
      );
      return extractArray<{ label: string; value_b: number; pct: number }>(res).map((r) => ({
        label: r.label,
        valueB: r.value_b,
        pct: r.pct,
      }));
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
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
  const { data, isError, isLoading } = useQuery({
    queryKey: ["live-cashflow-by-sector"],
    queryFn: async (): Promise<SectorFlowBar[]> => {
      const res = await apiGet<{ success: boolean; data: Array<{ name: string; value_b: number }> }>(
        "/market/cashflow-by-sector?limit=500"
      );
      return extractArray<{ name: string; value_b: number }>(res).map((r) => ({
        name: r.name,
        valueB: r.value_b,
      }));
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
    retry: 1,
  });
  const rows = data ?? [];
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
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
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
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
  return { data: rows, isLive: rows.length > 0, isError, isLoading };
}
