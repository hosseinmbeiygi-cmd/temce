// تایپ‌های سرویس ارز (apps/currency_service، پورت 8002)
// ساختار payload دقیقاً با endpoints/overview.py و endpoints/positions.py هم‌خوان است.

export type AssetType = "CASH_USD" | "USDT";
export type SignalType = "BUY" | "SELL" | "HOLD";
export type Confidence = "LOW" | "MEDIUM" | "HIGH";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type ArbitrageStatus = "NORMAL" | "OPPORTUNITY" | "EXPENSIVE";

export interface RateBlock {
  buy: number;
  sell: number;
  daily_change: number;
  spread: number;
  source: string;
}

export interface CurrencyRates {
  free: RateBlock;
  usdt: RateBlock;
  nima: RateBlock;
  official_cbi: number;
  timestamp: string;
}

export interface MarketSummary {
  free_market_usd: number;
  official_cbi_usd: number;
  nima_usd: number;
  usdt_irt: number;
  bubble_index: number;
  daily_volatility: number;
  bid_ask_spread: number;
  tether_arbitrage: number;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
}

export interface ArbitrageRow {
  name: string;
  price: number;
  difference_with_free_market: number;
  spread_pct: number;
  status: ArbitrageStatus;
}

export interface CurrencySignal {
  asset_type: AssetType;
  signal_type: SignalType;
  confidence: Confidence;
  reason: string;
  risk_level: RiskLevel;
  entry_range?: { min: number; max: number };
  target_price?: number;
  stop_loss?: number;
  holding_period?: string;
}

export interface KillSwitch {
  active: boolean;
  reasons: string[];
  action: string | null;
}

export interface CurrencyOverview {
  timestamp: string;
  rates: CurrencyRates;
  market_summary: MarketSummary;
  arbitrage_matrix: ArbitrageRow[];
  signals: CurrencySignal[];
  kill_switch: KillSwitch;
}

export interface ManualPosition {
  id: number;
  asset_type: AssetType;
  entry_price: number;
  volume: number;
  entry_date: string;
  created_at: string;
  note: string | null;
  current_price: number;
  pnl_toman: number;
  return_pct: number;
}

export interface PositionListResponse {
  count: number;
  positions: ManualPosition[];
}

export interface CreatePositionInput {
  asset_type: AssetType;
  entry_price: number;
  volume: number;
  entry_date?: string;
  note?: string;
}