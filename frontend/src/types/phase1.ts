// Phase 1 — data terminal API contract.
//
// Mirrors `src/gold_desk/phase1_schemas.py`. Every monetary value is **Rial**
// unless the field name says otherwise (`xau_usd` is USD/oz). A `null` means the
// source did not provide the field; the reason is in `data_gaps` and the UI must
// render «—», never zero.

export type Phase1Quality = "LIVE" | "DELAYED" | "SAMPLE" | "EDUCATIONAL" | "NO_DATA";

export interface TerminalCapabilities {
  orders: boolean;
  wallet: boolean;
  delivery: boolean;
  preview_only: boolean;
}

export interface TerminalReferences {
  xau_usd: number | null;
  usd_irt_rial: number | null;
  as_of: string | null;
  source: string;
  quality: Phase1Quality;
  unit: "rial";
  data_gaps: string[];
}

export interface TickerItem {
  key: string;
  label: string;
  price: number | null;
  unit: "ounce" | "rial";
  change_pct: number | null;
  change_amount: number | null;
  as_of: string | null;
  source: string;
  source_detail: string;
  quality: Phase1Quality;
  status: "ok" | "no_data" | "under_construction";
  note: string | null;
}

export interface PhysicalRow {
  symbol: string;
  label: string;
  kind: "gold" | "coin";
  price_basis: "gram" | "mesghal" | "coin";
  price: number | null;
  change_pct: number | null;
  change_amount: number | null;
  intrinsic: number | null;
  bubble_pct: number | null;
  bubble_amount: number | null;
  implied_usd: number | null;
  as_of: string | null;
  source: string;
  source_detail: string;
  quality: Phase1Quality;
  intrinsic_quality: Phase1Quality;
  data_gaps: string[];
}

export interface FundComposition {
  coin_pct: number | null;
  bar_pct: number | null;
  cash_pct: number | null;
  other_pct: number | null;
  as_of: string | null;
  source: string | null;
}

export interface FundRow {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  change_amount: number | null;
  last_trade_date: string | null;
  last_trade_time: string | null;
  volume: number | null;
  turnover: number | null;
  market_cap: number | null;
  nav: number | null;
  nav_issue: number | null;
  nav_redemption: number | null;
  nav_date: string | null;
  nav_time: string | null;
  nav_as_of: string | null;
  nav_source: string;
  intrinsic_price: number | null;
  bubble_nominal_pct: number | null;
  bubble_nominal_amount: number | null;
  bubble_intrinsic_pct: number | null;
  bubble_intrinsic_amount: number | null;
  bubble_real_pct: number | null;
  composition: FundComposition | null;
  composition_status: "available" | "needs_composition";
  implied_usd: number | null;
  as_of: string | null;
  source: string;
  source_detail: string;
  quality: Phase1Quality;
  nav_quality: Phase1Quality;
  data_gaps: string[];
}

export interface CertificateRow {
  contract_code: string;
  commodity: string | null;
  description: string | null;
  price: number | null;
  change_pct: number | null;
  change_amount: number | null;
  volume: number | null;
  turnover: number | null;
  contract_size: number | null;
  contract_size_unit: string | null;
  intrinsic: number | null;
  bubble_pct: number | null;
  bubble_amount: number | null;
  implied_usd: number | null;
  as_of: string | null;
  source_date: string | null;
  source: string;
  source_detail: string;
  quality: Phase1Quality;
  intrinsic_quality: Phase1Quality;
  data_gaps: string[];
}

export interface GoldTerminal {
  generated_at: string;
  unit: "rial";
  references: TerminalReferences;
  ticker: TickerItem[];
  physical: PhysicalRow[];
  funds: FundRow[];
  certificates: CertificateRow[];
  capabilities: TerminalCapabilities;
}

export interface WhatIfInputs {
  xau_usd: number;
  usd_irt_rial: number;
  usd_irt_toman: number;
}

export interface WhatIfPhysicalItem {
  symbol: string;
  label: string;
  market_price: number | null;
  base_intrinsic: number | null;
  preview_intrinsic: number | null;
  base_bubble_pct: number | null;
  preview_bubble_pct: number | null;
  base_bubble_amount: number | null;
  preview_bubble_amount: number | null;
  base_implied_usd: number | null;
  preview_implied_usd: number | null;
  quality: Phase1Quality;
  preview_quality: Phase1Quality;
  data_gaps: string[];
}

export interface WhatIfFundEffect {
  symbol: string;
  name: string;
  nav: number | null;
  market_price: number | null;
  nominal_bubble_pct_before: number | null;
  nominal_bubble_pct_after: number | null;
  real_bubble_pct_before: number | null;
  real_bubble_pct_after: number | null;
  implied_usd_before: number | null;
  implied_usd_after: number | null;
  data_gaps: string[];
}

export interface GoldWhatIf {
  generated_at: string;
  inputs: WhatIfInputs;
  physical: WhatIfPhysicalItem[];
  funds: WhatIfFundEffect[];
  capabilities: TerminalCapabilities;
}
