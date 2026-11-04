export interface FundScore {
  total: number;
  // The legacy six-dimension engine was removed; these are optional so
  // consumers that still render a breakdown can degrade without breaking
  // the type contract when only ``total`` is available.
  financial?: number;
  liquidity?: number;
  management?: number;
  risk?: number;
  cost?: number;
  transparency?: number;
}

export interface FundIssue {
  id: number;
  title: string;
  description: string;
  category: string;
  priority: "A1" | "A2" | "B" | "C";
  severity: number;
  solution: string;
}

export interface FundAnalysis {
  symbol: string;
  name: string;
  scores: FundScore;
  issues: FundIssue[];
  recommendation: "STRONG_BUY" | "BUY" | "WATCHLIST" | "HOLD" | "REDUCE" | "SELL" | "AVOID";
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  strengths: string[];
  weaknesses: string[];
  summary: string;
  nextSteps: string[];
}

// ── Fund interface from the page ──
export interface Fund {
  symbol: string;
  name: string;
  isin: string;
  fund_type?: string;
  market?: "tse" | "ime" | string;
  data_source?: string;
  snapshot_date?: string;
  nav_source?: string;
  nav_date?: string;
  nav: number;
  nav_change: number;
  nav_change_pct: number;
  price_last: number;
  price_close: number;
  price_yesterday: number;
  price_max: number;
  price_min: number;
  trade_volume: number;
  trade_value: number;
  trade_count: number;
  shares_count: number;
  base_volume: number | null;
  market_value: number;
  buy_real_volume: number;
  buy_legal_volume: number;
  sell_real_volume: number;
  sell_legal_volume: number;
  time: string;
  total_score?: number;
}
