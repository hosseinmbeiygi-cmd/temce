export type GoldSignalSymbol =
  | "ZARFSHANG"
  | "LOTUS"
  | "IME_GOLD_FUTURES"
  | "COIN_PHYSICAL"
  | "18K_GOLD";

export type GoldSignalMarket = "TSE" | "IME" | "PHYSICAL";
export type GoldSignalAction = "BUY" | "SELL" | "HOLD" | "CLOSE";
export type GoldSignalTimeframe = "SCALP" | "INTRADAY" | "SWING" | "LONG_TERM";
export type GoldSignalRiskLevel = "LOW" | "MEDIUM" | "HIGH" | "EXTREME";
export type KillSwitchStatus = "NORMAL" | "WARNING" | "ACTIVE";

export interface GoldSignalOutput {
  timestamp: string;
  asset: {
    symbol: GoldSignalSymbol;
    market: GoldSignalMarket;
    current_price: number;
  };
  signal: {
    action: GoldSignalAction;
    confidence_score: number;
    timeframe: GoldSignalTimeframe;
  };
  trade_parameters: {
    entry_range: [number, number];
    stop_loss: number;
    target_1: number;
    target_2: number;
    risk_reward_ratio: number;
  };
  metrics: {
    nav_premium_pct: number;
    coin_bubble_pct: number;
    gold_usd_correlation: number;
    dollar_adjusted_expected_roi: number;
  };
  leverage_and_margin: {
    leverage: number;
    liquidation_price: number | null;
    health_ratio: number | null;
    risk_level: GoldSignalRiskLevel;
  };
  rationale: string;
  kill_switch_status: KillSwitchStatus;
}

export interface ManualTradeEntry {
  asset: GoldSignalSymbol;
  market: GoldSignalMarket;
  side: "BUY" | "SELL";
  quantity: number;
  entryPrice: number;
  usdRate: number;
  fee: number;
  tradeDate: string;
}

