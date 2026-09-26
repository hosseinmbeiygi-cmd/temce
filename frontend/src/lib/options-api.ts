/** Typed clients for the /api/options frontend surface (mission phases 3–5). */

import { apiGet, apiPost } from "./api";

// ── Shared shapes ──────────────────────────────────────────────

export interface OptionSignal {
  strategy_id: string;
  strategy_name_fa: string;
  direction: "credit" | "debit";
  market_bias: string;
  underlying: string;
  entry_price: number;
  take_profit: number;
  stop_loss: number;
  risk_reward: number;
  confidence: number;
  iv_rank: number;
  liquidity_ok: boolean;
  iran_notes: string[];
  [key: string]: unknown;
}

export interface SignalsResponse {
  signals: OptionSignal[];
  iv_rank: number;
  legal_disclaimer: string;
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  expiry_date: string;
  exit_reason: "expiry" | "stop" | "target";
  strike: number;
  premium: number;
  payoff: number;
  pnl_net: number;
  underlying_entry: number;
  underlying_expiry: number;
}

export interface BacktestMetrics {
  n_trades: number;
  win_rate: number;
  total_pnl: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  profit_factor: number;
  annualized_return_pct: number;
  avg_win: number;
  avg_loss: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  metrics: BacktestMetrics;
  equity_curve: number[];
  equity_dates: string[];
  trades: BacktestTrade[];
  legal_disclaimer: string;
}

export interface PredictResponse {
  expected_move: {
    spot: number;
    sigma: number;
    days_to_expiry: number;
    lower_68: number;
    upper_68: number;
    lower_95: number;
    upper_95: number;
    median_terminal: number;
    mean_terminal: number;
    analytic_lower_68: number;
    analytic_upper_68: number;
    n_paths: number;
  };
  max_pain?: {
    max_pain_strike: number;
    total_payout_at_max_pain: number;
    payout_by_strike: Record<string, number>;
  };
  put_call_ratio?: number;
  vol_forecast?: {
    realized_vol_annual: number;
    garch_omega: number;
    garch_alpha: number;
    garch_beta: number;
    unconditional_vol_annual: number;
    n_observations: number;
  };
  probabilities?: {
    probability_of_profit: number;
    probability_of_touch_upper: number;
    probability_of_touch_lower: number;
    breakeven_upper: number;
    breakeven_lower: number;
  };
  legal_disclaimer: string;
}

// ── API calls ──────────────────────────────────────────────────

export interface SignalFilters {
  market_condition?: string;
  iv_rank?: number;
  min_oi?: number;
  min_volume?: number;
  max_spread_pct?: number;
  guarded?: boolean;
}

export function fetchOptionsSignals(filters: SignalFilters = {}) {
  const params = new URLSearchParams({
    market_condition: filters.market_condition ?? "neutral",
    iv_rank: String(filters.iv_rank ?? 50),
    min_oi: String(filters.min_oi ?? 10),
    min_volume: String(filters.min_volume ?? 5),
    max_spread_pct: String(filters.max_spread_pct ?? 10),
    guarded: String(filters.guarded ?? true),
  });
  return apiGet<SignalsResponse & { success: boolean }>(`/api/options/signals?${params.toString()}`);
}

export function runOptionsBacktest(body: {
  symbol: string;
  strategy?: string;
  days_to_expiry?: number;
  limit?: number;
}) {
  return apiPost<{ success: boolean; data?: BacktestResponse; error?: { message?: string } }>(
    "/api/options/backtest",
    body,
    undefined,
    300_000
  );
}

export function runOptionsPredict(body: {
  spot: number;
  sigma: number;
  days_to_expiry: number;
  strikes?: number[];
  call_oi?: number[];
  put_oi?: number[];
  call_volume?: number;
  put_volume?: number;
  log_returns?: number[];
  horizon_days?: number;
}) {
  return apiPost<{ success: boolean; data?: PredictResponse; error?: { message?: string } }>(
    "/api/options/predict",
    body
  );
}
