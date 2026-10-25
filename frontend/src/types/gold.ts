// TypeScript types — تمیز و ۱۰۰٪ typed

export type AssetType = "gold" | "coin" | "fx" | "fund";
// C1: موتور وقتی وزنِ داده‌دارِ موجود زیر MIN_SCORE_COVERAGE_WEIGHT باشد
// decision را NO_DATA می‌گذارد (total عددی می‌ماند تا نمودار نشکند).
export type Decision = "GREEN" | "YELLOW" | "RED" | "NO_DATA";
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
  // Backend schema (src/gold_desk/schemas.py FundBlock) declares
  // ``bubble_pct: float | None`` — NAV/price gaps make it null on the wire.
  bubble_pct: number | null;
  bpr: number;
  real_buy_value: number;
  real_sell_value: number;
  net_inflow: number;
  nav_change_7d_pct: number | null;
  // ETF / antigravity pages use these too; keep them on the shared FundBlock
  // so getETFSnapshot and getArbitrage can reuse one shared FundBlock shape.
  signal?: string;
  name_fa?: string;
  isin?: string;
  nav?: number;
  premium_pct?: number;
  liquidity?: string;
  management_fee?: string;
  reason?: string;
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
  // ── C1 (فیلدهای جدیدِ افزوده؛ اختیاری تا وقتی بک‌اند send کند) ──
  // مقیاس‌ها از روی کد موتور (`src/gold_desk/scorer.py:66-68,204-242`) خوانده شده:
  // جمع خامِ وزن‌های خام قبل از نرمال‌سازی (int).
  raw_total?: number | null;
  // مجموع وزان کامپوننت‌هایی که واقعاً داده داشته‌اند، در مقیاس **۰ تا ۱۰۰**
  // (int، نه کسر). آستانه: MIN_SCORE_COVERAGE_WEIGHT = 60 در constants.py:151.
  available_weight?: number | null;
  // موتور آن را `float(available_weight)` می‌گذارد، پس همین ۰ تا ۱۰۰ است و در UI
  // مستقیم با «٪» نمایش داده می‌شود.
  data_coverage_pct?: number | null;
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

export type FreshnessStatus = "ok" | "stale" | "empty" | "missing";

export interface FreshnessSource {
  key: string;
  label: string;
  table: string;
  column: string;
  max_age_minutes: number;
  last_at: string | null;
  age_minutes: number | null;
  rows: number | null;
  status: FreshnessStatus;
  detail: string | null;
}

export interface FreshnessReport {
  generated_at: string;
  overall: FreshnessStatus;
  counts: { ok: number; stale: number; empty: number; missing: number };
  sources: FreshnessSource[];
  scheduler_jobs?: number;
}

export interface KillSwitchResp {
  status: "NORMAL" | "WARNING" | "ACTIVE";
  reason: string | null;
  directive: string | null;
  triggered_at: string | null;
  active_rules: string[];
}

export interface BenchmarkComparison {
  label: string;
  points: number;
  return_pct: number | null;
  relative_pct: number | null;
  unavailable?: string;
}

export interface PortfolioPerformance {
  window_days: number;
  start: string | null;
  end: string | null;
  points: number;
  total_value_irt: number;
  total_cost_irt: number;
  unpriced_holdings: number;
  twr_pct: number | null;
  simple_return_pct: number | null;
  annualized_volatility_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number | null;
  var_95_pct: number | null;
  cvar_95_pct: number | null;
  concentration_pct: number | null;
  max_drift_pct: number | null;
  drift_by_class: Record<string, number>;
  benchmarks: Record<string, BenchmarkComparison>;
  unavailable: Record<string, string>;
}

export interface PortfolioValuePoint {
  as_of: string;
  total_value_irt: number;
  total_cost_irt: number;
  net_flow_irt: number;
  unpriced_holdings: number;
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

// ── Economic calendar (``/gold/analytics/macro/calendar``) ───────────────

export interface MacroCalendarEvent {
  event_id: string;
  event_date: string;
  event_time: string | null;
  title: string | null;
  country: string | null;
  category: string | null;
  importance: number | null;
  is_high_volatility: boolean;
  source: string | null;
}

// ── Macro posture (``GET /gold/analytics/macro/live``) ───────────────────
//
// Only the latest stored TIPS / DXY observation is exposed by the API; there
// is no historical series endpoint for either indicator yet, so the UI must
// not draw a time-series chart from these numbers.

export interface MacroPostureInputs {
  tips_yield?: number | null;
  dxy_index?: number | null;
  gold_trend?: "up" | "down" | "sideways" | string | null;
  tokenized_gold_premium?: Record<string, number>;
}

export interface MacroPosture {
  tips_yield: number;
  dxy_index: number;
  gold_trend: string;
  real_yield_score: number;
  real_yield_signal: "ACCOMMODATIVE" | "RESTRICTIVE" | "NEUTRAL" | string;
  dxy_score: number;
  dxy_signal: "WEAK" | "STRONG" | "NEUTRAL" | string;
  trend_score: number;
  composite_score: number;
  posture: "BULLISH" | "BEARISH" | "NEUTRAL" | string;
  inverse_correlation_expected: boolean;
  divergence: boolean;
  reasons: string[];
}

export interface MacroLiveResponse {
  available: boolean;
  missing: string[];
  posture: MacroPosture | null;
  inputs: MacroPostureInputs;
  tips_staleness_seconds: number | null;
  dxy_staleness_seconds: number | null;
  trend_staleness_seconds: number | null;
  high_vol_window: boolean;
  error: string | null;
}

// ── IME options-chain analytics (``GET /gold/analytics/options/chain``) ───
//
// ``iv_history_source`` is ``"unavailable"`` because no historical IV series
// is persisted, so IV rank/percentile stay null and must be shown as "—".

export interface OptionsChainContract {
  contract_key: string;
  symbol?: string | null;
  option_type: string;
  strike: number;
  market_price: number;
  expiry?: string | null;
  days_to_expiry?: number | null;
  forward_price?: number | null;
  volume?: number | null;
  open_interest?: number | null;
  oi_change?: number | null;
  oi_change_pct?: number | null;
  bid?: number | null;
  ask?: number | null;
  iv: number | null;
  iv_error: string | null;
  iv_rank: number | null;
  iv_percentile: number | null;
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  rho?: number | null;
  is_liquid: boolean;
  liquidity_reasons: string[];
}

export interface IvTermPoint {
  expiry: string | null;
  days_to_expiry: number | null;
  forward_price: number;
  atm_strike: number;
  atm_iv: number;
  contract_key: string | null;
}

export interface IvSkewRow {
  expiry: string | null;
  days_to_expiry: number | null;
  forward_price: number | null;
  put_strike: number | null;
  put_iv: number | null;
  call_strike: number | null;
  call_iv: number | null;
  skew: number | null;
  reason: string | null;
}

export interface OptionsChainReport {
  available: boolean;
  reason: string | null;
  source?: string;
  commodity?: string | null;
  forward_price?: number | null;
  contracts: OptionsChainContract[];
  contracts_count: number;
  skew_by_expiry: IvSkewRow[];
  iv_term_structure: IvTermPoint[];
  iv_available: boolean;
  iv_history_available: boolean;
  iv_history_source?: "unavailable" | "provider";
  iv_history_reason?: string;
}

// ── IME option strategy (``POST /gold/analytics/options/strategy``) ──────

export interface OptionsStrategyLeg {
  asset_type?: "option" | "underlying";
  option_type: "call" | "put";
  strike: number;
  quantity: number;
  premium: number;
  iv?: number;
  entry_price?: number;
}

export interface OptionsStrategyAnalysis {
  strategy?: string;
  net_debit: number;
  net_credit: number;
  breakevens: number[];
  max_profit: number | null;
  max_loss: number | null;
  max_profit_unbounded: boolean;
  max_loss_unbounded: boolean;
  pre_expiry_value?: number | null;
  pre_expiry_pnl?: number | null;
  pre_expiry_error?: string | null;
}
