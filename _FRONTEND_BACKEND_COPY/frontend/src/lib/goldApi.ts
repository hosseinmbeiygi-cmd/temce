// API client برای GoldDesk
// استفاده از api client موجود
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import type {
  AlertEvent,
  AlertRule,
  BacktestResult,
  DCAPlan,
  HealthResponse,
  RiskProfile,
  Snapshot,
  Vehicle,
  Watchlist,
} from "@/types/gold";

export interface StrategyBacktest {
  period: { start: string; end: string };
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  buy_hold_return_pct: number;
  alpha_pct: number;
  hit_rate_pct: number;
  n_trades: number;
  n_successful: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  trades: Array<{
    date: string;
    tranche: number;
    price: number;
    amount_irt: number;
    units: number;
  }>;
  warning: string | null;
}

export interface OptionGreeks {
  delta: number;
  gamma: number;
  vega: number;
  theta: number;
  rho: number;
}

export interface OptionPrice {
  call: number;
  put: number;
  forward: number;
  strike: number;
  time_years: number;
  iv: number;
  rate: number;
  d1: number;
  d2: number;
  greeks: OptionGreeks;
}

export interface CollarResult {
  cost: number;
  floor: number;
  cap: number;
  put_premium: number;
  call_premium: number;
  spot: number;
  time_years: number;
}

export async function getSnapshot(): Promise<Snapshot> {
  const r = await apiGet<{ success: boolean; data: Snapshot }>("/api/gold/snapshot");
  return r.data;
}

export async function getScoreHistory(days = 7) {
  return apiGet<{ success: boolean; data: { items: Array<{ score_at: string; total: number; decision: string; hard_stop_active: boolean }>; total: number } }>(
    `/api/gold/history/score?days=${days}`,
  );
}

export async function getSnapshotHistory(symbol = "IR_COIN_EMAMI", days = 7) {
  return apiGet<{ success: boolean; data: { items: Array<{ snapshot_at: string; market_price: number; fair_value: number; bubble_pct: number }>; total: number } }>(
    `/api/gold/history/snapshot?symbol=${symbol}&days=${days}`,
  );
}

export async function planDCA(opts: {
  total_capital_irt: number;
  risk_profile?: RiskProfile;
  current_score: number;
  preferred_vehicle?: Vehicle;
}): Promise<DCAPlan> {
  return apiPost<DCAPlan>("/api/gold/dca/plan", opts);
}

export async function getAlertRules(): Promise<AlertRule[]> {
  const r = await apiGet<{ success: boolean; data: AlertRule[] }>("/api/gold/alerts/rules");
  return r.data;
}

export async function createAlertRule(rule: {
  name: string;
  rule_type: string;
  symbol?: string;
  threshold: number;
  channel?: "inapp" | "telegram" | "both";
  telegram_chat_id?: string;
  cooldown_minutes?: number;
}) {
  return apiPost<{ success: boolean; data: { id: number } }>("/api/gold/alerts/rules", rule);
}

export async function updateAlertRule(id: number, update: Partial<{
  name: string;
  threshold: number;
  channel: string;
  enabled: boolean;
  cooldown_minutes: number;
  telegram_chat_id: string;
}>) {
  return apiPut(`/api/gold/alerts/rules/${id}`, update);
}

export async function deleteAlertRule(id: number) {
  return apiDelete(`/api/gold/alerts/rules/${id}`);
}

export async function getAlertEvents(days = 7, unreadOnly = false): Promise<AlertEvent[]> {
  const r = await apiGet<{ success: boolean; data: AlertEvent[] }>(
    `/api/gold/alerts/events?days=${days}&unread_only=${unreadOnly}`,
  );
  return r.data;
}

export async function ackAlert(eventId: number) {
  return apiPost(`/api/gold/alerts/${eventId}/ack`, {});
}

export async function seedDefaultRules() {
  return apiPost<{ success: boolean; data: { inserted: number } }>("/api/gold/alerts/seed", {});
}

export async function getHealth(): Promise<HealthResponse> {
  const r = await apiGet<{ success: boolean; data: HealthResponse }>("/api/gold/health");
  return r.data;
}

export async function getBacktest(days = 90, bubbleThreshold = 8, symbol = "IR_COIN_EMAMI"): Promise<BacktestResult> {
  const r = await apiGet<{ success: boolean; data: BacktestResult }>(
    `/api/gold/backtest?days=${days}&bubble_threshold=${bubbleThreshold}&symbol=${symbol}`,
  );
  return r.data;
}

export async function getWatchlist(): Promise<Watchlist> {
  const r = await apiGet<{ success: boolean; data: Watchlist }>("/api/gold/watchlist");
  return r.data;
}

export async function putWatchlist(symbols: string[]): Promise<Watchlist> {
  return apiPut<Watchlist>("/api/gold/watchlist", { symbols, updated_at: null });
}

export async function testTelegram(chatId?: string) {
  return apiPost<{ success: boolean; error?: { message: string } }>("/api/gold/telegram/test", {
    chat_id: chatId,
  });
}

export async function getTelegramStatus() {
  return apiGet<{ success: boolean; data: { bot_configured: boolean; default_chat_id_set: boolean; enabled: boolean; is_operational: boolean } }>(
    "/api/gold/telegram/status",
  );
}

// ── Strategy Backtest ──────────────────────────────────────────


export async function getStrategyBacktest(opts: {
  days?: number;
  symbol?: string;
  bubble_trigger?: number;
  initial_capital?: number;
} = {}): Promise<StrategyBacktest> {
  const params = new URLSearchParams({
    days: String(opts.days ?? 90),
    symbol: opts.symbol ?? "IR_COIN_EMAMI",
    bubble_trigger: String(opts.bubble_trigger ?? 5),
    initial_capital: String(opts.initial_capital ?? 100_000_000),
  });
  const r = await apiGet<{ success: boolean; data: StrategyBacktest }>(
    `/api/gold/backtest/strategy?${params}`,
  );
  return r.data;
}

// ── Black-76 Options ──────────────────────────────────────────


export async function priceOption(opts: {
  forward: number;
  strike: number;
  expiry: string;
  iv?: number;
  rate?: number;
}): Promise<OptionPrice> {
  // query params (backend uses Query(...))
  const params = new URLSearchParams({
    forward: String(opts.forward),
    strike: String(opts.strike),
    expiry: opts.expiry,
    iv: String(opts.iv ?? 0.25),
    rate: String(opts.rate ?? 0.30),
  });
  // query params for non-Query-required: forward/strike/expiry also as query
  // We pass them as query params even though backend reads them as direct function args
  // FastAPI reads simple types (float, str) from query if not in body
  const r = await apiGet<{ success: boolean; data: OptionPrice }>(
    `/api/gold/options/price?${params}`,
  );
  return r.data;
}

export async function protectiveCollar(opts: {
  spot: number;
  put_strike: number;
  call_strike: number;
  expiry: string;
  iv?: number;
  rate?: number;
}): Promise<CollarResult> {
  const params = new URLSearchParams({
    spot: String(opts.spot),
    put_strike: String(opts.put_strike),
    call_strike: String(opts.call_strike),
    expiry: opts.expiry,
    iv: String(opts.iv ?? 0.25),
    rate: String(opts.rate ?? 0.30),
  });
  const r = await apiGet<{ success: boolean; data: CollarResult }>(
    `/api/gold/options/collar?${params}`,
  );
  return r.data;
}

// ── WebSocket ─────────────────────────────────────────────────

type WSState = "connecting" | "open" | "closed" | "error";
type WSListener = (state: WSState, snap: Snapshot | null) => void;

class GoldWSManager {
  private ws: WebSocket | null = null;
  private listeners: Set<WSListener> = new Set();
  private reconnectTimer: number | null = null;
  private pingInterval: number | null = null;
  private lastSnapshot: Snapshot | null = null;
  private state: WSState = "closed";
  private retryDelay = 1000;
  private maxRetryDelay = 30_000;

  subscribe(listener: WSListener): () => void {
    this.listeners.add(listener);
    listener(this.state, this.lastSnapshot);
    if (this.state === "closed") this.connect();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) this.disconnect();
    };
  }

  private connect() {
    if (typeof window === "undefined") return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/gold/ws`;
    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.setState("connecting");

    this.ws.onopen = () => {
      this.retryDelay = 1000;
      this.setState("open");
      // heartbeat
      this.pingInterval = window.setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) this.ws.send("ping");
      }, 30_000);
    };

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "snapshot" && msg.data) {
          this.lastSnapshot = msg.data as Snapshot;
          this.setState("open", this.lastSnapshot);
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    this.ws.onerror = () => this.setState("error");

    this.ws.onclose = () => {
      this.cleanup();
      this.setState("closed");
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null) return;
    if (this.listeners.size === 0) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.retryDelay = Math.min(this.retryDelay * 2, this.maxRetryDelay);
      this.connect();
    }, this.retryDelay);
  }

  private cleanup() {
    if (this.pingInterval !== null) {
      window.clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private disconnect() {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.cleanup();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.setState("closed");
  }

  private setState(state: WSState, snap: Snapshot | null = this.lastSnapshot) {
    this.state = state;
    this.listeners.forEach((l) => l(state, snap));
  }
}

let _manager: GoldWSManager | null = null;

export function getGoldWSManager(): GoldWSManager {
  if (typeof window === "undefined") {
    // SSR fallback
    return new GoldWSManager();
  }
  if (!_manager) _manager = new GoldWSManager();
  return _manager;
}

// back-compat
export function subscribeGoldWS(
  onSnapshot: (snap: Snapshot) => void,
  onError?: (err: Event) => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  const mgr = getGoldWSManager();
  return mgr.subscribe((state, snap) => {
    if (state === "open" && snap) onSnapshot(snap);
    if (state === "error" && onError) onError(new Event("ws-error"));
  });
}

export type { WSState };

// ── API Tokens ──────────────────────────────────────────────

export interface APIToken {
  token_id: string;
  name: string;
  scopes: string[];
  enabled: boolean;
  created_at: string | null;
  last_used_at: string | null;
}

export async function listAPITokens(): Promise<APIToken[]> {
  const r = await apiGet<{ success: boolean; data: APIToken[] }>("/api/gold/tokens");
  return r.data;
}

export async function createAPIToken(name: string, scopes: string): Promise<{ token: string; token_id: string; name: string; scopes: string[] }> {
  const r = await apiPost<{ success: boolean; data: { token: string; token_id: string; name: string; scopes: string[] } }>(
    `/api/gold/tokens?name=${encodeURIComponent(name)}&scopes=${encodeURIComponent(scopes)}`,
    {},
  );
  return r.data;
}

export async function revokeAPIToken(tokenId: string): Promise<boolean> {
  const r = await apiDelete<{ success: boolean }>(`/api/gold/tokens/${tokenId}`);
  return r.success;
}

// ── Portfolio ───────────────────────────────────────────────

export interface Holding {
  symbol: string;
  display_name: string;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  cost_basis: number;
  current_value: number;
  pnl_irt: number;
  pnl_pct: number;
  n_purchases: number;
}

export interface Portfolio {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings: Holding[];
  snapshot_at: string | null;
}

export interface PlanStatus {
  plan_id: number;
  name: string;
  status: {
    total_capital: number;
    executed: number;
    remaining: number;
    next_tranche_pct: number;
    next_tranche_amount: number;
    next_trigger: string;
    current_score: number;
    stop_loss_pct: number;
    take_profit_pct: number;
  };
}

export interface Trade {
  id: number;
  symbol: string;
  action: "buy" | "sell";
  quantity: number;
  price: number;
  amount_irt: number;
  fee_irt: number;
  pnl_irt: number;
  note: string | null;
  traded_at: string | null;
}

export async function getPortfolio(): Promise<Portfolio> {
  const r = await apiGet<{ success: boolean; data: Portfolio }>("/api/gold/portfolio");
  return r.data;
}

export async function addHolding(h: {
  symbol: string;
  display_name: string;
  vehicle?: string;
  quantity: number;
  buy_price: number;
  buy_amount_irt: number;
  buy_fee_pct?: number;
  note?: string;
}) {
  return apiPost<{ success: boolean; data: { id: number } }>("/api/gold/portfolio/holdings", h);
}

export async function deleteHolding(id: number) {
  return apiDelete(`/api/gold/portfolio/holdings/${id}`);
}

export async function getDCAPlans(currentScore: number): Promise<PlanStatus[]> {
  const r = await apiGet<{ success: boolean; data: PlanStatus[] }>(`/api/gold/portfolio/dca?current_score=${currentScore}`);
  return r.data;
}

export async function createDCAPlan(p: { name: string; total_capital_irt: number; risk_profile?: "conservative" | "balanced" | "aggressive"; current_score?: number; vehicle?: "etf" | "cert" | "melted" | "coin" }) {
  return apiPost<{ success: boolean; data: { id: number; ladder: any[] } }>("/api/gold/portfolio/dca", p);
}

export async function executeDCA(planId: number, tranche: number) {
  return apiPost(`/api/gold/portfolio/dca/${planId}/execute?tranche=${tranche}`, {});
}

export async function deleteDCAPlan(planId: number) {
  return apiDelete(`/api/gold/portfolio/dca/${planId}`);
}

export async function getTrades(limit = 20): Promise<Trade[]> {
  const r = await apiGet<{ success: boolean; data: Trade[] }>(`/api/gold/portfolio/trades?limit=${limit}`);
  return r.data;
}

export async function recordTrade(t: { symbol: string; action: "buy" | "sell"; quantity: number; price: number; amount_irt: number; fee_pct?: number; holding_id?: number; plan_id?: number; note?: string }) {
  return apiPost("/api/gold/portfolio/trades", t);
}

// ── Antigravity v5 (backend /api/v1/gold) ─────────────────────

// Live prices (BrsApi)
export interface GoldLivePrices {
  gold_oz_usd: number;
  gold_18k_irr: number;
  coin_bahar_irr: number;
  usd_irr: number;
  last_updated: string;
  source: string;
  is_stale: boolean;
}
export async function getGoldLivePrices(refresh = false): Promise<GoldLivePrices> {
  const r = await apiGet<{ success: boolean; data: GoldLivePrices }>(
    `/api/v1/gold/live-prices${refresh ? "?refresh=true" : ""}`,
  );
  return r.data;
}

// Coin bubble
export interface CoinBubbleResp {
  coin_intrinsic_irr: number;
  coin_market_irr: number;
  bubble_pct: number;
  signal: "BUY" | "SELL" | "NEUTRAL";
  reason: string;
}
export async function postCoinBubble(p: {
  coin_price_irr: number;
  gold_oz_usd: number;
  usd_irr: number;
  weight_g?: number;
  purity?: number;
}): Promise<CoinBubbleResp> {
  const r = await apiPost<{ success: boolean; data: CoinBubbleResp }>(
    "/api/v1/gold/coin-bubble",
    p,
  );
  return r.data;
}

// ETF NAV Premium
export interface ETFNavRow {
  symbol: string;
  name_fa: string;
  isin: string;
  market_price: number;
  nav: number;
  premium_pct: number;
  signal: "BUY" | "SELL" | "NEUTRAL";
  reason: string;
  liquidity: string;
  management_fee: string;
}
export interface ETFNavPremiumResp {
  items: ETFNavRow[];
  best_opportunity: string | null;
  generated_at: string;
}
export async function getETFSnapshot(): Promise<ETFNavPremiumResp> {
  const r = await apiGet<{ success: boolean; data: ETFNavPremiumResp }>(
    "/api/v1/gold/etf-nav-premium",
  );
  return r.data;
}

// Arbitrage
export interface ArbitrageResp {
  pair: string;
  gross_spread_pct: number;
  net_spread_pct: number;
  action: "BUY_ETF_SELL_PHYSICAL" | "BUY_PHYSICAL_SELL_ETF" | "NO_ARBITRAGE";
  strategy: string;
  estimated_profit_pct: number;
}
export async function getArbitrage(): Promise<ArbitrageResp | null> {
  const r = await apiGet<{ success: boolean; data: ArbitrageResp | null }>(
    "/api/v1/gold/arbitrage",
  );
  return r.data;
}

// Futures — Margin Calculator (اولویت)
export interface FuturesMarginResp {
  contract_value: number;
  initial_margin: number;
  maintenance_margin: number;
  liquidation_price: number;
  leverage: number;
  position_type: "LONG" | "SHORT";
  health_ratio: number | null;
  distance_to_liquidation_pct: number | null;
  alert_level: "SAFE" | "WARNING" | "CRITICAL" | null;
  alert_message: string | null;
  recommended_stop_loss: number | null;
}
export async function postFuturesMargin(p: {
  entry_price: number;
  position_type: "LONG" | "SHORT";
  leverage?: number;
  quantity: number;
  current_price?: number;
  account_equity?: number;
}): Promise<FuturesMarginResp> {
  const r = await apiPost<{ success: boolean; data: FuturesMarginResp }>(
    "/api/v1/gold/futures/margin-calculator",
    p,
  );
  return r.data;
}

// Futures — Positions
export interface FuturesPosition {
  id: string;
  contract_symbol: string;
  position_type: "LONG" | "SHORT";
  leverage: number;
  entry_price: number;
  quantity: number;
  current_price: number | null;
  initial_margin: number;
  maintenance_margin: number;
  liquidation_price: number;
  distance_to_liquidation_pct: number | null;
  health_ratio: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  status: string;
  exit_price: number | null;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
  opened_at: string | null;
  closed_at: string | null;
}
export async function getFuturesPositions(status?: string): Promise<FuturesPosition[]> {
  const r = await apiGet<{ success: boolean; data: FuturesPosition[] }>(
    `/api/v1/gold/futures/positions${status ? `?status=${status}` : ""}`,
  );
  return r.data;
}
export async function openFuturesPosition(p: {
  contract_symbol: string;
  position_type: "LONG" | "SHORT";
  entry_price: number;
  quantity: number;
  leverage?: number;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  notes?: string | null;
}) {
  return apiPost("/api/v1/gold/futures/positions", p);
}
export async function closeFuturesPosition(
  position_id: string,
  exit_price: number,
  reason = "MANUAL",
) {
  return apiPost(`/api/v1/gold/futures/positions/${position_id}/close`, {
    exit_price,
    reason,
  });
}
export interface FuturesHealthResp {
  positions: FuturesPosition[];
  total_used_margin: number;
  total_equity: number;
  aggregate_health_ratio: number | null;
  critical_count: number;
  warning_count: number;
}
export async function getFuturesHealth(): Promise<FuturesHealthResp> {
  const r = await apiGet<{ success: boolean; data: FuturesHealthResp }>(
    "/api/v1/gold/futures/health",
  );
  return r.data;
}

// Kill-Switch
export interface KillSwitchResp {
  status: "NORMAL" | "WARNING" | "ACTIVE";
  reason: string | null;
  triggered_at: string | null;
  active_rules: string[];
  directive: string | null;
}
export async function getKillSwitch(): Promise<KillSwitchResp> {
  const r = await apiGet<{ success: boolean; data: KillSwitchResp }>(
    "/api/v1/gold/kill-switch",
  );
  return r.data;
}

// IME futures catalog
export async function getIMEFutures(): Promise<any[]> {
  const r = await apiGet<{ success: boolean; data: any[] }>("/api/v1/gold/ime/futures");
  return r.data;
}
