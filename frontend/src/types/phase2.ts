// Phase 2 — market coverage contract.
//
// Mirrors `src/gold_desk/phase2_schemas.py`. Every monetary value is **Rial**
// unless the field name says `_usd` or `base_currency` says otherwise. `null`
// means the source did not provide the field; the UI renders «—», never zero.
//
// Phase 2 is read-only: `MarketCapabilities` has no true trading/payment flag.
// A client must not infer a buy/payment surface from these payloads.

import type { TerminalReferences } from "./phase1";

export type Phase2Quality = "LIVE" | "DELAYED" | "SAMPLE" | "EDUCATIONAL" | "NO_DATA";
export type SourceStatus = "connected" | "partial" | "not_connected";
export type CoverageStatus = "complete" | "incomplete" | "no_data";
export type PeriodKey = "1m" | "3m" | "6m" | "9m" | "1y";

export interface MarketCapabilities {
  orders: boolean;
  wallet: boolean;
  delivery: boolean;
  checkout: boolean;
  payment: boolean;
  preview_only: boolean;
}

// ── Tehran shop / banking board ─────────────────────────────────

export interface TehranRow {
  key: string;
  label: string;
  kind: "gold" | "coin" | "used" | "exchange";
  price_basis: "gram" | "coin";
  purity: number | null;
  tehran_price: number | null;
  official_symbol: string | null;
  official_label: string | null;
  official_price: number | null;
  spread_vs_official_pct: number | null;
  spread_vs_official_amount: number | null;
  change_pct: number | null;
  change_amount: number | null;
  intrinsic: number | null;
  bubble_pct: number | null;
  bubble_amount: number | null;
  implied_usd: number | null;
  as_of: string | null;
  source: string;
  source_detail: string;
  quality: Phase2Quality;
  intrinsic_quality: Phase2Quality;
  note: string | null;
  data_gaps: string[];
}

export interface TehranBoardResponse {
  generated_at: string;
  unit: "rial";
  references: TerminalReferences;
  source_status: SourceStatus;
  rows: TehranRow[];
  capabilities: MarketCapabilities;
}

// ── Online platforms (price comparison only) ────────────────────

export interface PlatformQuote {
  platform: string;
  platform_slug: string;
  buy_price: number | null;
  sell_price: number | null;
  low_price: number | null;
  high_price: number | null;
  intrinsic_18k: number | null;
  bubble_pct: number | null;
  implied_usd: number | null;
  as_of: string | null;
  source: string;
  source_detail: string;
  quality: Phase2Quality;
  data_gaps: string[];
}

export interface PlatformsResponse {
  generated_at: string;
  unit: "rial";
  source_status: SourceStatus;
  platform_count: number;
  rows: PlatformQuote[];
  notice: string;
  capabilities: MarketCapabilities;
}

// ── Returns matrix ──────────────────────────────────────────────

export interface PeriodReturn {
  period: PeriodKey;
  value: number | null;
  status: CoverageStatus;
  start_date: string | null;
  end_date: string | null;
  start_price: number | null;
  end_price: number | null;
  observations: number;
  reason: string | null;
}

export interface AssetReturnRow {
  key: string;
  label: string;
  asset_type: "gold" | "currency" | "index" | "fund_index" | "inflation" | "crypto";
  native_currency: "IRR" | "USD";
  returns: Record<PeriodKey, PeriodReturn>;
  correlation_90d: number | null;
  correlation_observations: number;
  correlation_status: CoverageStatus;
  correlation_reason: string | null;
  quality: Phase2Quality;
  source: string;
  data_gaps: string[];
}

export interface ReturnsMatrixResponse {
  generated_at: string;
  base_currency: "IRR" | "USD";
  periods: PeriodKey[];
  correlation_against: "USD/IRR";
  method: string;
  rows: AssetReturnRow[];
  capabilities: MarketCapabilities;
}

// ── Fund market map ─────────────────────────────────────────────

export interface FundMapCell {
  symbol: string;
  name: string;
  size: number;
  size_share_pct: number | null;
  change_pct: number | null;
  price: number | null;
  quality: Phase2Quality;
  as_of: string | null;
  href: string;
  data_gaps: string[];
}

export interface FundMapSummaryItem {
  label: string;
  symbol: string | null;
  value: number;
  share_pct: number | null;
}

export interface FundMapSummary {
  total_value: number;
  currency: "rial";
  size_metric: "trade_value" | "market_value";
  items: FundMapSummaryItem[];
  other_value: number;
  other_share_pct: number | null;
  cells_count: number;
}

export interface FundMapResponse {
  generated_at: string;
  size_metric: "trade_value" | "market_value";
  color_scale_pct: number;
  cells: FundMapCell[];
  summary: FundMapSummary;
  capabilities: MarketCapabilities;
}
