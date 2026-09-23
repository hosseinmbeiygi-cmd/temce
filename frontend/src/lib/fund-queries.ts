"use client";

/**
 * Typed read layer for every funds endpoint.
 *
 * The funds API answers in three different envelopes — bare object,
 * `{ data }`, and `{ success, data }` — so unwrapping lives here once and
 * no component has to guess.
 */

import { useQuery } from "@tanstack/react-query";
import type { FundNavBreak, FundNavDashboard } from "@/lib/fund-nav";
import type { FofLatest } from "@/lib/fund-compliance";
import type { JournalEntry, TrialBalance, UnitMovement } from "@/lib/fund-ledger";
import { apiGet, apiPost } from "@/lib/api";

export const unwrap = <T,>(res: unknown): T | null => {
  if (res === null || res === undefined) return null;
  const r = res as Record<string, unknown>;
  if ("data" in r) return (r.data as T) ?? null;
  return r as T;
};

/** v2 routes key funds as `tse:<symbol>`; a prefixed id is passed through. */
export const fundIdOf = (symbol: string) => (symbol.includes(":") ? symbol : `tse:${symbol}`);

const enc = encodeURIComponent;

export function useFundQuery<T>(key: unknown[], path: string, opts?: { enabled?: boolean; staleTime?: number; refetchInterval?: number }) {
  return useQuery({
    queryKey: key,
    queryFn: async () => unwrap<T>(await apiGet<unknown>(path)),
    enabled: opts?.enabled ?? true,
    staleTime: opts?.staleTime ?? 60_000,
    refetchInterval: opts?.refetchInterval,
  });
}

// ── Market list / overview ──────────────────────────────────────────────────

export interface FundRow {
  symbol: string;
  name: string;
  isin: string;
  fund_type: string;
  market: string;
  // Nullable because the API now reports «خوانده نشد» as null instead of 0 — a zero price,
  // volume or market value is a measurement, and the fund pages must not rank or chart one
  // that was never taken. nav_source says which of NAV / traded price the number is.
  nav: number | null;
  nav_change: number | null;
  nav_change_pct: number | null;
  nav_source?: string | null;
  nav_date?: string;
  price_last: number | null;
  price_close: number | null;
  price_yesterday: number | null;
  price_max: number | null;
  price_min: number | null;
  trade_volume: number | null;
  trade_value: number | null;
  trade_count: number | null;
  shares_count: number | null;
  base_volume: number | null;
  market_value: number | null;
  buy_real_volume: number | null;
  sell_real_volume: number | null;
  buy_legal_volume: number | null;
  sell_legal_volume: number | null;
  time?: string;
}

export interface FundListResponse {
  total: number;
  limit: number;
  offset: number;
  items: FundRow[];
}

/**
 * Sort key for a field the API may leave unmeasured.
 *
 * Absence sinks below every reading instead of competing as zero — `null - 3` would otherwise
 * rank a fund with no NAV data among the losers of the day.
 */
export const rankNum = (v: number | null | undefined): number => v ?? Number.NEGATIVE_INFINITY;

export const useFundList = (market?: string) =>
  useFundQuery<FundListResponse>(
    ["funds", "list", market ?? "all"],
    `/funds?limit=500${market && market !== "all" ? `&market=${market}` : ""}`,
    { refetchInterval: 120_000, staleTime: 30_000 }
  );

export interface FundOverview {
  updated_at: string;
  summary: { fund_count: number; category_count: number; avg_change_pct: number; total_trade_value: number; top_category?: { name: string } | null };
  categories: { name: string; count: number; avg_change_pct: number; trade_value: number; real_inflow: number; share_pct: number }[];
  top_funds: Record<string, { symbol: string; name: string; change_pct: number; trade_value: number; real_inflow: number }[]>;
  trade_breakdown: { name: string; value: number; pct: number }[];
  returns: { name: string; m1?: number | null; m3?: number | null; m6?: number | null; y1?: number | null }[];
  cashflow: Record<string, Record<string, number>>;
  cashflow_periods: string[];
}

export const useFundOverview = () =>
  useFundQuery<FundOverview>(["funds", "overview"], "/funds/overview", { staleTime: 120_000 });

// ── Single fund ─────────────────────────────────────────────────────────────

export interface FundAnalysis {
  symbol: string;
  name: string;
  scores: {
    financial: number;
    liquidity: number;
    management: number;
    risk: number;
    cost: number;
    transparency: number;
    total: number;
  };
  recommendation: string;
  risk_level: string;
  issues_count: number;
  summary: string;
}

export interface FundDetail extends FundRow {
  found?: boolean;
  error?: string;
  nav_history?: { date: string; nav: number; source?: string }[];
  analysis?: FundAnalysis;
}

export const useFundDetail = (symbol: string) =>
  useFundQuery<FundDetail>(["funds", "detail", symbol], `/funds/${enc(symbol)}`, { refetchInterval: 60_000, staleTime: 30_000 });

export const useFundNavHistory = (symbol: string) =>
  useFundQuery<{ symbol: string; history: { date: string; nav: number; source?: string }[]; points: number; latest: Record<string, unknown> | null; oldest: Record<string, unknown> | null }>(
    ["funds", "nav", "v1", symbol],
    `/funds/${enc(symbol)}/nav`,
    { staleTime: 300_000 }
  );

export const useFundV2NavHistory = (symbol: string) =>
  useFundQuery<{ points?: { date: string; nav_issue?: number | null; nav_redemption?: number | null; nav_statistical?: number | null }[]; freshness?: Freshness }>(
    ["funds", "v2", "nav", symbol],
    `/funds/v2/${enc(fundIdOf(symbol))}/nav-history`,
    { staleTime: 300_000 }
  );

export const useFundAnalysis = (symbol: string) =>
  useFundQuery<FundAnalysis>(["funds", "analysis", symbol], `/funds/${enc(symbol)}/analysis`, { staleTime: 600_000 });

// ── Intraday ────────────────────────────────────────────────────────────────

export interface IntradaySummary {
  count: number;
  first_price: number;
  last_price: number;
  price_min: number;
  price_max: number;
  volume: number;
  value: number;
  first_time: string;
  last_time: string;
}

export interface IntradayTick {
  time: string;
  price: number | null;
  volume: number;
  canceled: boolean;
}

/** `{ symbols: { SYM: { trade_date, ticks[], summary } } }` — one request per symbol set. */
export const useFundIntraday = (symbol: string, enabled = true) =>
  useFundQuery<{ symbols: Record<string, { trade_date: string | null; ticks?: IntradayTick[]; summary?: IntradaySummary | null; error?: string }> }>(
    ["funds", "intraday", symbol],
    `/funds/intraday?symbols=${enc(symbol)}&limit=2000`,
    { enabled, refetchInterval: 30_000, staleTime: 10_000 }
  );

export interface Candle {
  m?: string;
  time?: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  vol?: number;
  val?: number;
  n?: number;
  [k: string]: unknown;
}

export const useFundCandles = (symbol: string, intervalMinutes = 5, enabled = true) =>
  useFundQuery<{ symbols: Record<string, { trade_date: string | null; candles?: Candle[]; error?: string }> }>(
    ["funds", "candles", symbol, intervalMinutes],
    `/funds/intraday/candles?symbols=${enc(symbol)}&interval_minutes=${intervalMinutes}`,
    { enabled, staleTime: 30_000 }
  );

// ── v2 read-through ─────────────────────────────────────────────────────────

export type Freshness = "live" | "estimated" | "stale" | string;

export const useFundV2Valuation = (symbol: string) =>
  useFundQuery<Record<string, unknown> & { freshness?: Freshness; coverage_pct?: number; nav_estimated?: number | null; nav_official?: number | null }>(
    ["funds", "v2", "valuation", symbol],
    `/funds/v2/${enc(fundIdOf(symbol))}/valuation`,
    { refetchInterval: 60_000, staleTime: 30_000 }
  );

export const useFundV2Holdings = (symbol: string) =>
  useFundQuery<{ holdings?: Record<string, unknown>[]; diffs?: Record<string, unknown>[]; freshness?: Freshness }>(
    ["funds", "v2", "holdings", symbol],
    `/funds/v2/${enc(fundIdOf(symbol))}/holdings`,
    { staleTime: 600_000 }
  );

export interface FundScore {
  total: number;
  components: Record<string, number>;
  metrics: Record<string, number | null>;
  points_used?: number;
  points_available?: number;
}

export const useFundV2Score = (symbol: string) =>
  useFundQuery<FundScore>(["funds", "v2", "score", symbol], `/funds/v2/${enc(fundIdOf(symbol))}/score`, { staleTime: 600_000 });

export const useFundV2Backtest = (symbol: string) =>
  useFundQuery<{ strategies?: Record<string, Record<string, number>>; available?: boolean }>(
    ["funds", "v2", "backtest", symbol],
    `/funds/v2/${enc(fundIdOf(symbol))}/backtest`,
    { staleTime: 3_600_000 }
  );

export interface FundRanking {
  rank: number;
  fund_id: string;
  symbol: string;
  name: string;
  fund_type: string;
  score_date: string | null;
  total_score: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
}

export const useFundRankings = (limit = 100) =>
  useFundQuery<{ rankings?: FundRanking[] }>(["funds", "v2", "rankings", limit], `/funds/v2/rankings?limit=${limit}`, {
    staleTime: 600_000,
  });

export interface PortfolioDiff {
  fund_id: string;
  fund_symbol: string | null;
  instrument_symbol: string | null;
  period: string | null;
  weight_change_pct: number | null;
  flow_direction: string | null;
}

export const usePortfolioDiffs = (symbol?: string, flow?: string) =>
  useFundQuery<{ diffs?: PortfolioDiff[] }>(
    ["funds", "v2", "portfolio-diffs", symbol ?? "all", flow ?? "all"],
    `/funds/v2/portfolio-diffs?limit=300${symbol ? `&fund_id=${enc(fundIdOf(symbol))}` : ""}${flow ? `&flow=${flow}` : ""}`,
    { staleTime: 600_000 }
  );

export const useFundUniverse = () =>
  useFundQuery<{ funds?: Record<string, unknown>[]; freshness?: Freshness }>(["funds", "v2", "universe"], "/funds/v2/universe", {
    staleTime: 300_000,
  });

// ── Data quality (market-wide) ──────────────────────────────────────────────

export interface CoverageRow {
  fund_id?: string;
  symbol?: string;
  name?: string;
  coverage_status?: string;
  [k: string]: unknown;
}

export const useFundCoverage = (status?: string) =>
  useFundQuery<{ summary: Record<string, number>; count: number; items: CoverageRow[] }>(
    ["funds", "v2", "coverage", status ?? "all"],
    `/funds/v2/coverage?limit=1000${status ? `&status=${status}` : ""}`,
    { staleTime: 300_000 }
  );

export const useFundQuarantine = (reviewed = false) =>
  useFundQuery<{ count: number; items: Record<string, unknown>[] }>(
    ["funds", "v2", "quarantine", reviewed],
    `/funds/v2/quarantine?reviewed=${reviewed}&limit=200`,
    { staleTime: 120_000 }
  );

export const useFundAliases = (symbol: string) =>
  useFundQuery<{ fund_id: string; aliases: Record<string, unknown>[] }>(
    ["funds", "v2", "aliases", symbol],
    `/funds/v2/aliases/${enc(fundIdOf(symbol))}`,
    { staleTime: 600_000 }
  );

export const useFundMonitoring = () =>
  useFundQuery<Record<string, unknown>>(["funds", "v2", "monitoring"], "/funds/v2/monitoring", { staleTime: 120_000 });

// ── NAV engine / reconciliation ─────────────────────────────────────────────

export const useNavDashboard = (symbol: string) =>
  useFundQuery<FundNavDashboard>(["funds", "nav", "dashboard", symbol], `/funds/v2/nav/${enc(fundIdOf(symbol))}/dashboard`, { staleTime: 120_000 });

export const useNavBreaks = () =>
  useFundQuery<{ breaks?: FundNavBreak[] } | FundNavBreak[]>(["funds", "nav", "breaks"], "/funds/v2/nav/breaks?limit=200", { staleTime: 120_000 });

export const useClassNav = (symbol: string) =>
  useFundQuery<Record<string, unknown>>(["funds", "nav", "class", symbol], `/funds/v2/nav/${enc(fundIdOf(symbol))}/class-nav`, {
    staleTime: 300_000,
  });

export const useFundFof = (symbol: string) =>
  useFundQuery<FofLatest>(["funds", "nav", "fof", symbol], `/funds/v2/nav/${enc(fundIdOf(symbol))}/fof`, {
    staleTime: 300_000,
  });

export const useNavEvidence = (symbol: string) =>
  useFundQuery<Record<string, unknown>>(["funds", "nav", "evidence", symbol], `/funds/v2/nav/${enc(fundIdOf(symbol))}/evidence`, {
    staleTime: 300_000,
  });

export const useShadowAcceptance = (symbol: string) =>
  useFundQuery<Record<string, unknown>>(
    ["funds", "nav", "shadow", symbol],
    `/funds/v2/nav/${enc(fundIdOf(symbol))}/shadow-acceptance`,
    { staleTime: 300_000 }
  );

// ── Ledger / compliance / regulator ─────────────────────────────────────────

export const useTrialBalance = (symbol: string) =>
  useFundQuery<TrialBalance>(["funds", "ledger", "tb", symbol], `/funds/v2/ledger/${enc(fundIdOf(symbol))}/trial-balance`, {
    staleTime: 300_000,
  });

export const useLedgerEntries = (symbol: string) =>
  useFundQuery<{ entries?: JournalEntry[] } | JournalEntry[]>(["funds", "ledger", "entries", symbol], `/funds/v2/ledger/${enc(fundIdOf(symbol))}/entries?limit=200`, {
    staleTime: 300_000,
  });

export const useUnitMovements = (symbol: string) =>
  useFundQuery<{ movements?: UnitMovement[] } | UnitMovement[]>(
    ["funds", "ledger", "movements", symbol],
    `/funds/v2/ledger/${enc(fundIdOf(symbol))}/unit-movements?limit=200`,
    { staleTime: 300_000 }
  );

export const useComplianceResource = <T = Record<string, unknown>>(symbol: string, resource: string) =>
  useFundQuery<T>(["funds", "compliance", symbol, resource], `/funds/v2/compliance/${enc(fundIdOf(symbol))}/${resource}`, {
    staleTime: 300_000,
    enabled: Boolean(resource),
  });

export const useGlobalCompliance = (resource: string) =>
  useFundQuery<Record<string, unknown>>(["funds", "compliance", "global", resource], `/funds/v2/compliance/${resource}`, {
    staleTime: 300_000,
    enabled: Boolean(resource),
  });

export const useRegulatorEvidence = (symbol: string) =>
  useFundQuery<Record<string, unknown>>(["funds", "regulator", "evidence", symbol], `/funds/v2/regulator/${enc(fundIdOf(symbol))}/evidence`, {
    staleTime: 300_000,
  });

export const useAccessLogs = () =>
  useFundQuery<Record<string, unknown>>(["funds", "regulator", "access-logs"], "/funds/v2/regulator/access-logs?limit=200", {
    staleTime: 300_000,
  });

// ── Actions (POST) ──────────────────────────────────────────────────────────

export const runNavCalculation = (symbol: string) =>
  apiPost<Record<string, unknown>>(`/funds/v2/nav/${enc(fundIdOf(symbol))}/calculate`);

export const runNavReconciliation = (symbol: string) =>
  apiPost<Record<string, unknown>>(`/funds/v2/nav/${enc(fundIdOf(symbol))}/reconcile`);

export const runFundUpdate = (symbol: string) => apiPost<{ error?: string }>(`/funds/${enc(symbol)}/update`);
