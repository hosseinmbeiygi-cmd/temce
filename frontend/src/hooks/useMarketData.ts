"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
import {
  INDICES,
  NEWS,
  QUOTES,
  TICKER_ITEMS,
  TOP_PERFORMERS,
  TOP_STOCKS_TODAY,
  VALUE_VOLUME,
  type IndexQuote,
  type MarketSession,
  type NewsItem,
  type QuoteItem,
  type TickerItem,
  type Top5Symbol,
  type TopStock,
  getMarketSession,
} from "@/lib/market-mock";

/**
 * Live market data layer — fetches the real backend endpoints and falls back
 * to the static mock catalogue when the API is unreachable or empty. Every
 * hook returns the same shape the dashboard widgets already consume, so wiring
 * a widget to live data is a one-line change.
 *
 * All list hooks return ≥10 symbols when live data is available so each
 * dashboard section stays populated during manual testing.
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
function useEnrichedHeatmap(): HeatmapCell[] {
  const { data } = useQuery({
    queryKey: ["live-heatmap"],
    queryFn: async (): Promise<HeatmapCell[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: HeatmapCell[] }>(
          "/market/enriched-heatmap?limit=120"
        );
        const arr = extractArray<HeatmapCell>(res);
        if (arr.length === 0 && (res as unknown as Record<string, unknown>)?.success === false) {
          console.warn("[useEnrichedHeatmap] backend returned success:false", res);
        }
        return arr;
      } catch (e) {
        console.warn("[useEnrichedHeatmap] fetch failed, falling back to mock", e);
        throw e;
      }
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
  return data ?? [];
}

/** Live ticker / sitebar strip — top symbols by value from the heatmap. */
export function useTickerItems(): TickerItem[] {
  const cells = useEnrichedHeatmap();
  if (cells.length > 0) {
    const mapped = mapHeatmapToTicker(
      [...cells].sort((a, b) => (b.value || 0) - (a.value || 0))
    );
    if (mapped.length > 0) return mapped;
  }
  return TICKER_ITEMS;
}

/** Live indices — شاخص کل / هم‌وزن / فرابورس / … from /market/indices. */
export function useIndices(): IndexQuote[] {
  const { data } = useQuery({
    queryKey: ["live-indices"],
    queryFn: async (): Promise<IndexQuote[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: RawIndex[] }>("/market/indices");
        const raw = extractArray<RawIndex>(res);
        const mapped = mapIndices(raw);
        if (mapped.length > 0) return mapped;
      } catch {
        /* fall through to mock */
      }
      return INDICES;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  return data ?? INDICES;
}

/** Live news strip from /news. */
export function useNewsItems(): NewsItem[] {
  const { data } = useQuery({
    queryKey: ["live-news"],
    queryFn: async (): Promise<NewsItem[]> => {
      try {
        const res = await apiGet<{ success: boolean; data: { items: NewsItem[] } }>(
          "/news?page_size=6"
        );
        const items = res?.data?.items ?? [];
        if (items.length > 0) {
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
            };
          });
        }
      } catch {
        /* fall through to mock */
      }
      return NEWS;
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
  });
  return data ?? NEWS;
}

/** Live market breadth, value & volume from market-dashboard overview. */
export function useMarketOverview() {
  const { data } = useQuery({
    queryKey: ["live-overview"],
    queryFn: async (): Promise<{
      breadth: { up: number; down: number; flat: number };
      tradeValueB: number;
      volumeM: number;
      avgChangePct: number;
    } | null> => {
      try {
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
      } catch {
        /* fall through to mock */
      }
      return null;
    },
    refetchInterval: 180_000,
    staleTime: 90_000,
  });

  const fallback = {
    breadth: VALUE_VOLUME.breadth,
    tradeValueB: VALUE_VOLUME.tradeValueB,
    volumeM: VALUE_VOLUME.volumeM,
    avgChangePct: VALUE_VOLUME.avgChangePct ?? 0,
  };
  return data ?? fallback;
}

/** Live top gainers (≥10) from enriched heatmap — used by TopStocksToday. */
export function useTopStocks(): TopStock[] {
  const cells = useEnrichedHeatmap();
  if (cells.length > 0) {
    const mapped = mapHeatmapToStocks(cells).sort(
      (a, b) => b.changePct - a.changePct
    );
    if (mapped.length >= 10) return mapped.slice(0, 12);
    if (mapped.length > 0) return mapped;
  }
  return TOP_STOCKS_TODAY;
}

/** Live top symbols by value, split by market (بورس / فرابورس) — 10 each. */
export function useActiveSymbols(): { tse: Top5Symbol[]; otc: Top5Symbol[] } {
  const cells = useEnrichedHeatmap();
  if (cells.length > 0) {
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
    const tse = byValue(cells.filter((c) => (c.market || "").includes("بورس")));
    const otc = byValue(cells.filter((c) => (c.market || "").includes("فرابورس")));
    if (tse.length >= 5 || otc.length >= 5) return { tse, otc };
  }
  return { tse: VALUE_VOLUME.top5Tse, otc: VALUE_VOLUME.top5Otc };
}

/** Live quote cards (طلا / سکه / ارز / تتر / دلار) from brsapi endpoints. */
export function useQuoteCards(): QuoteItem[] {
  const { data } = useQuery({
    queryKey: ["live-quote-cards"],
    queryFn: async (): Promise<QuoteItem[]> => {
      try {
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
        // a real IRR price exists (price_irr) — otherwise the mock tether is
        // kept, because a zero/1$ price would look broken.
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
        if (quotes.length >= 3) {
          // Keep tether visible — if the live crypto feed had no usable USDT
          // IRR price, fall back to the mock tether card so the row stays full.
          if (!quotes.some((q) => q.kind === "tether")) {
            const mockTether = QUOTES.find((q) => q.kind === "tether");
            if (mockTether) quotes.push(mockTether);
          }
          return quotes;
        }
      } catch {
        /* fall through to mock */
      }
      return QUOTES;
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  return data ?? QUOTES;
}

/** Live top performers for LiquidityBlocks — shares the same heatmap query. */
export function useTopPerformers(): TopStock[] {
  const cells = useEnrichedHeatmap();
  if (cells.length > 0) {
    const mapped = mapHeatmapToStocks(cells).sort(
      (a, b) => b.changePct - a.changePct
    );
    if (mapped.length >= 10) return mapped.slice(0, 10);
    if (mapped.length > 0) return mapped;
  }
  return TOP_PERFORMERS;
}
