// Shared types for the options trading page

export interface StrategyLeg {
  side: string;
  type: string;
  strike?: number;
  premium?: number;
  quantity: number;
}

export interface StrategyInfo {
  id: string;
  name: string;
  name_fa: string;
  category: string;
  market: string;
  risk: string;
  legs: number;
  score?: number;
}

export interface StrategyAnalysis {
  strategy_name: string;
  strategy_name_fa: string;
  legs: StrategyLeg[];
  max_profit: number;
  max_loss: number;
  break_even: number[];
  initial_cost: number;
  market_condition: string;
  risk_level: string;
  description: string;
  description_fa: string;
  best_for: string;
  example: unknown;
  profit_at_expiry: { price: number; profit: number }[];
}

export interface OptionContract {
  symbol: string;
  name: string;
  type: string;
  strike: number;
  price: number;
  volume: number;
  oi: number;
  days_to_expiry: number;
  underlying_price: number;
  bid: number;
  ask: number;
  open: number;
  high: number;
  low: number;
  trades: number;
}

export interface ChainData {
  underlying: string;
  underlying_price: number;
  calls: OptionContract[];
  puts: OptionContract[];
  total_contracts: number;
  analysis?: Record<string, unknown>;
}

export interface LiveSymbol {
  symbol: string;
  contracts: number;
  volume: number;
  price: number;
}

export interface GreeksResult {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  intrinsic_value: number;
  time_value: number;
  explanation: Record<string, string>;
}

export interface PricingResult {
  call_price: number;
  put_price: number;
  call_delta: number;
  put_delta: number;
  d1: number;
  d2: number;
}

export interface ArbitrageParity {
  parity_violated: boolean;
  left_side: number;
  right_side: number;
  difference: number;
  theoretical_call: number;
  theoretical_put: number;
  action?: string;
  action_fa?: string;
  profit?: number;
}

export interface VolatilityAnalysis {
  iv_data: { strike: number; iv: number }[];
  avg_iv: number;
  iv_range: { min: number; max: number };
  implied_volatility: number;
  historical_volatility: number;
  has_volatility_smile: boolean;
  interpretation: string;
}

export interface PortfolioAnalysis {
  portfolio_delta: number;
  portfolio_gamma: number;
  portfolio_theta: number;
  portfolio_vega: number;
  portfolio_rho: number;
  net_cost: number;
  delta_explanation: string;
  hedging_suggestion: string;
}

export interface CostResult {
  gross_pnl: number;
  commission: number;
  net_pnl: number;
  net_pnl_pct: number;
  breakeven: number;
}

export interface SizingResult {
  max_contracts: number;
  total_cost: number;
  pct_of_capital: number;
}

export interface IvRankResult {
  rank: number;
  percentile: number;
  interpretation: string;
  interpretation_fa: string;
}

export interface ChecklistItem {
  check: string;
  check_fa: string;
  detail: string;
}

export interface GlossaryItem {
  fa: string;
  en: string;
  desc: string;
}

export interface MistakeItem {
  mistake: string;
  solution: string;
}

export type TabId = "dashboard" | "analyze" | "chain" | "analytics" | "professional" | "learn";
