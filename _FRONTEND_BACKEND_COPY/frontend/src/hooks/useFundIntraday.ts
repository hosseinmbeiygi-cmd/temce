"use client";

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────

export interface IntradayTick {
  time: string;
  price: number | null;
  volume: number;
  canceled: boolean;
}

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

export interface IntradaySymbolPayload {
  trade_date: string | null;
  ticks: IntradayTick[];
  summary: IntradaySummary | null;
  error?: string;
}

export interface Candle {
  minute: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  value: number;
  vwap: number;
  trades: number;
}

export interface CandlesSymbolPayload {
  trade_date: string | null;
  candles: Candle[];
  error?: string;
}

export interface TopFundItem {
  rank: number;
  symbol: string;
  name: string;
  fund_type: string | null;
  market: string | null;
  nav: number | null;
  nav_change_pct: number | null;
  market_value: number | null;
  trade_volume: number | null;
  trade_value: number | null;
  metric_value: number;
}

export interface TopFundsResponse {
  metric: string;
  total_considered: number;
  items: TopFundItem[];
}

export type TopMetric =
  | "market_value"
  | "trade_volume"
  | "trade_value"
  | "nav_change_pct"
  | "intraday_volume";

// ── Hooks ────────────────────────────────────────────────────────────

/** Fetch raw intraday ticks for one or more symbols. */
export function useFundIntraday(
  symbols: string[],
  options: { date?: string; limit?: number; includeCanceled?: boolean } = {}
): UseQueryResult<{ symbols: Record<string, IntradaySymbolPayload> }> {
  const { date, limit = 5000, includeCanceled = false } = options;
  return useQuery({
    queryKey: ["fund-intraday", symbols, date, limit, includeCanceled],
    enabled: symbols.length > 0,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("symbols", symbols.join(","));
      if (date) params.set("date", date);
      params.set("limit", String(limit));
      if (includeCanceled) params.set("include_canceled", "true");
      return apiGet<{ symbols: Record<string, IntradaySymbolPayload> }>(
        `/funds/intraday?${params.toString()}`
      );
    },
    staleTime: 60_000,
  });
}

/** Fetch OHLCV candles (1m by default, or N-minute). */
export function useFundCandles(
  symbols: string[],
  options: { date?: string; intervalMinutes?: number; includeCanceled?: boolean } = {}
): UseQueryResult<{ symbols: Record<string, CandlesSymbolPayload> }> {
  const { date, intervalMinutes = 1, includeCanceled = false } = options;
  return useQuery({
    queryKey: ["fund-candles", symbols, date, intervalMinutes, includeCanceled],
    enabled: symbols.length > 0,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("symbols", symbols.join(","));
      if (date) params.set("date", date);
      params.set("interval_minutes", String(intervalMinutes));
      if (includeCanceled) params.set("include_canceled", "true");
      return apiGet<{ symbols: Record<string, CandlesSymbolPayload> }>(
        `/funds/intraday/candles?${params.toString()}`
      );
    },
    staleTime: 60_000,
  });
}

/** Top funds by a chosen metric. */
export function useTopFunds(
  metric: TopMetric,
  top: number = 20,
  filters: { fundType?: string; market?: string } = {}
): UseQueryResult<TopFundsResponse> {
  return useQuery({
    queryKey: ["top-funds", metric, top, filters.fundType, filters.market],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("metric", metric);
      params.set("top", String(top));
      if (filters.fundType) params.set("fund_type", filters.fundType);
      if (filters.market) params.set("market", filters.market);
      return apiGet<TopFundsResponse>(`/funds/top?${params.toString()}`);
    },
    staleTime: 120_000,
  });
}
