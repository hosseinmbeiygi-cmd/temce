// TypeScript types — تمیز و ۱۰۰٪ typed

export type AssetType = "gold" | "coin" | "fx" | "fund";
export type Decision = "GREEN" | "YELLOW" | "RED";
export type RiskProfile = "conservative" | "balanced" | "aggressive";
export type Vehicle = "etf" | "cert" | "melted" | "coin" | "jewelry";

export interface ReferenceBlock {
  xau_usd: number;
  usd_irt: number;
  aed_irt: number;
  aed_parity_usd: number;
  aed_gap_pct: number;
  source: "brsapi" | "tgju" | "cache";
  age_seconds: number;
}

export interface AssetBlock {
  symbol: string;
  display_name: string;
  asset_type: AssetType;
  market_price: number;
  fair_value: number | null;
  bubble_abs: number | null;
  bubble_pct: number | null;
  implied_usd: number | null;
  quality_flag: string;
}

export interface FundBlock {
  symbol: string;
  fund_name: string;
  nav_per_unit: number;
  market_price: number;
  bubble_pct: number;
  bpr: number;
  real_buy_value: number;
  real_sell_value: number;
  net_inflow: number;
  nav_change_7d_pct: number | null;
}

export interface ScoreComponents {
  bubble: number;
  bubble_reason: string;
  nav: number;
  nav_reason: string;
  tsetmc: number;
  tsetmc_reason: string;
  technical: number;
  technical_reason: string;
  parity: number;
  parity_reason: string;
  fund_flow: number;
  fund_flow_reason: string;
}

export interface ScoreBlock {
  total: number;
  decision: Decision;
  components: ScoreComponents;
  hard_stop_active: boolean;
  hard_stop_reason: string | null;
}

export interface Snapshot {
  snapshot_at: string;
  references: ReferenceBlock;
  gold: Record<string, AssetBlock>;
  coins: Record<string, AssetBlock>;
  funds: FundBlock[];
  score: ScoreBlock;
  quality_flag: string;
}

export interface DCATranche {
  tranche: number;
  pct: number;
  amount_irt: number;
  trigger: string;
  vehicle: string;
  estimated_fee_irt: number;
}

export interface DCAPlan {
  total_capital_irt: number;
  ladder: DCATranche[];
  recommended_vehicle: Vehicle;
  total_fee_irt: number;
  net_investable_irt: number;
  stop_loss_pct: number;
  take_profit_pct: number;
}

export interface AlertRule {
  id: number;
  name: string;
  rule_type: string;
  symbol: string | null;
  threshold: number;
  channel: "inapp" | "telegram" | "both";
  telegram_chat_id: string | null;
  enabled: boolean;
  cooldown_minutes: number;
  last_fired_at: string | null;
  created_at: string | null;
}

export interface AlertEvent {
  id: number;
  rule_id: number;
  rule_name: string | null;
  symbol: string | null;
  trigger_value: number | null;
  threshold: number | null;
  message: string | null;
  channel: string;
  sent_at: string | null;
  read_at: string | null;
}

export interface HealthResponse {
  brsapi_ok: boolean;
  redis_ok: boolean;
  db_ok: boolean;
  last_snapshot_at: string | null;
  scheduler_jobs: number;
  telegram_configured: boolean;
  active_alert_rules: number;
  unread_alerts: number;
}

export interface BacktestResult {
  total_days: number;
  signal_days: number;
  forward_30d_avg_pct: number;
  positive_count: number;
  negative_count: number;
  hit_rate_pct: number;
  warning: string | null;
}

export interface Watchlist {
  symbols: string[];
  updated_at: string | null;
}
