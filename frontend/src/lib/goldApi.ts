// extended gold API client
//
// Every path here must exist in the mounted API surface:
//   * ``/gold/...``      — src/gold_desk/api.py (personal GoldDesk surface)
//   * ``/gold/...``      — apps/api/endpoints/gold.py (calculators/futures, mounted in router.py)
//   * ``/gold/analytics`` — apps/api/endpoints/gold_analytics.py

import { apiDelete, apiGet, apiPost, apiPut, getStoredAccessToken } from "@/lib/api";
import type {
  AlertEvent,
  AlertRule,
  DCAPlan,
  FreshnessReport,
  HealthResponse,
  KillSwitchResp,
  MacroCalendarEvent,
  MacroLiveResponse,
  OptionsChainReport,
  OptionsStrategyAnalysis,
  OptionsStrategyLeg,
  RiskProfile,
  Snapshot,
  Vehicle,
} from "@/types/gold";

export type { KillSwitchResp } from "@/types/gold";

/**
 * STEP 8: shared 503 detection so every gold surface can render an explicit
 * "service unavailable" state instead of a generic failure.
 */
export function isServiceUnavailable(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /\b503\b/.test(message);
}

// ── Snapshot-backed reads ────────────────────────────────────────

export async function getSnapshot(): Promise<Snapshot> {
  const r = await apiGet<{ success: boolean; data: Snapshot }>("/gold/snapshot");
  return r.data;
}

export async function getScoreHistory(days: number): Promise<
  Array<{ score_at: string; total: number; decision: string; hard_stop_active: boolean }>
> {
  const r = await apiGet<{
    success: boolean;
    data: {
      items: Array<{
        score_at: string;
        total: number;
        decision: string;
        hard_stop_active: boolean;
      }>;
      total: number;
    };
  }>(`/gold/history/score?days=${days}`);
  return r.data?.items ?? [];
}

export async function getSnapshotHistory(symbol: string, days: number): Promise<
  Array<{ snapshot_at: string; bubble_pct: number }>
> {
  const r = await apiGet<{
    success: boolean;
    data: {
      items: Array<{ snapshot_at: string; bubble_pct: number }>;
      total: number;
    };
  }>(`/gold/history/snapshot?symbol=${encodeURIComponent(symbol)}&days=${days}`);
  return r.data?.items ?? [];
}

export async function getGoldLivePrices(): Promise<Record<string, number>> {
  const r = await apiGet<{ success: boolean; data: Record<string, number> }>("/gold/live-prices");
  return r.data;
}

// ── Health / freshness ──────────────────────────────────────────

export async function getHealth(): Promise<HealthResponse> {
  // The GoldDesk route returns the report object directly (no {success,data}
  // envelope); tolerate an enveloped payload too so neither shape yields
  // `undefined` (react-query rejects undefined query data).
  const r = await apiGet<HealthResponse | { success: boolean; data: HealthResponse }>("/gold/health");
  if (r && typeof r === "object" && "data" in r && r.data) return r.data;
  return r as HealthResponse;
}

export async function getFreshness(): Promise<FreshnessReport> {
  const r = await apiGet<{ success: boolean; data: FreshnessReport }>("/gold/freshness");
  return r.data;
}

export async function getTelegramStatus(): Promise<{
  success: boolean;
  data: {
    is_operational: boolean;
    bot_configured: boolean;
    default_chat_id_set: boolean;
    enabled: boolean;
  };
}> {
  const r = await apiGet<{
    success: boolean;
    data: {
      is_operational: boolean;
      bot_configured: boolean;
      default_chat_id_set: boolean;
      enabled: boolean;
    };
  }>("/gold/telegram/status");
  return r;
}

export async function testTelegram(chatId?: string): Promise<{
  success: boolean;
  error: { message: string } | null;
}> {
  const r = await apiPost<{
    success: boolean;
    error: { message: string } | null;
  }>("/gold/telegram/test", chatId ? { chat_id: chatId } : {});
  return r;
}

// ── Economic calendar (CPI / NFP / FOMC + Iran manual events) ────
//
// Public calculator surface: mounted at ``/gold/analytics``.

export async function getMacroCalendar(limit = 20): Promise<MacroCalendarEvent[]> {
  const r = await apiGet<{ success: boolean; data: MacroCalendarEvent[] }>(
    `/gold/analytics/macro/calendar?limit=${limit}`,
  );
  return r.data ?? [];
}

// ── Live snapshot WebSocket ─────────────────────────────────────
//
// The backend streams ``{"type": "snapshot", "data": Snapshot}`` every few
// seconds from ``/gold/ws``. A browser cannot attach an Authorization header
// to a handshake, so the access token travels as a query parameter.

export type WSState = "connecting" | "open" | "closed" | "error";

type WSListener = (state: WSState, snap: Snapshot | null) => void;

function goldWebSocketUrl(): string | null {
  if (typeof window === "undefined") return null;
  const base = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
  const root = base.startsWith("http")
    ? base.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${base}`;
  const token = getStoredAccessToken();
  return `${root.replace(/\/$/, "")}/gold/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

class GoldWSManager {
  private ws: WebSocket | null = null;
  private listeners = new Set<WSListener>();
  private state: WSState = "closed";
  private lastSnapshot: Snapshot | null = null;
  private retryDelay = 1000;
  private readonly maxRetryDelay = 30_000;
  private reconnectTimer: number | null = null;
  private pingInterval: number | null = null;

  subscribe(listener: WSListener): () => void {
    this.listeners.add(listener);
    listener(this.state, this.lastSnapshot);
    if (!this.ws && this.listeners.size > 0) this.connect();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) this.disconnect();
    };
  }

  private connect() {
    // The backend rejects an unauthenticated handshake with 403, and the token
    // only exists after the session is hydrated/logged in. Dialing early just
    // burns a doomed socket (and a console error), so wait for a token and
    // retry once the session appears.
    if (!getStoredAccessToken()) {
      this.scheduleReconnect();
      return;
    }

    const url = goldWebSocketUrl();
    if (!url) return;

    this.setState("connecting");
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.retryDelay = 1000;
      this.setState("open");
      this.pingInterval = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30_000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type?: string; data?: Snapshot };
        if (msg.type === "snapshot" && msg.data) {
          this.lastSnapshot = msg.data;
          this.setState("open", this.lastSnapshot);
        }
      } catch {
        /* non-JSON heartbeat frames are ignored */
      }
    };

    ws.onerror = () => this.setState("error");

    ws.onclose = () => {
      this.cleanup();
      this.setState("closed");
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null || this.listeners.size === 0) return;
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
    this.lastSnapshot = null;
    this.setState("closed", null);
  }

  private setState(state: WSState, snap: Snapshot | null = this.lastSnapshot) {
    this.state = state;
    this.listeners.forEach((listener) => listener(state, snap));
  }
}

let _goldWsManager: GoldWSManager | null = null;

export function getGoldWSManager(): GoldWSManager {
  if (!_goldWsManager) _goldWsManager = new GoldWSManager();
  return _goldWsManager;
}

/**
 * Subscribe to the live gold snapshot stream.
 *
 * ``onOpen``/``onClose`` fire on connection transitions;
 * ``onSnapshot`` receives every streamed snapshot.
 */
export function subscribeGoldWS(
  onOpen?: () => void,
  onClose?: () => void,
  onSnapshot?: (snap: Snapshot) => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  return getGoldWSManager().subscribe((state, snap) => {
    if (state === "open") onOpen?.();
    if (state === "closed" || state === "error") onClose?.();
    if (state === "open" && snap) onSnapshot?.(snap);
  });
}

// ── Alerts ──────────────────────────────────────────────────────

export async function getAlertRules(): Promise<AlertRule[]> {
  const r = await apiGet<{ success: boolean; data: AlertRule[] }>("/gold/alerts/rules");
  return r.data;
}

export async function getAlertEvents(days: number): Promise<AlertEvent[]> {
  const r = await apiGet<{ success: boolean; data: AlertEvent[] }>(
    `/gold/alerts/events?days=${days}`,
  );
  return r.data;
}

export async function seedDefaultRules(): Promise<void> {
  await apiPost<{ success: boolean }>("/gold/alerts/seed", undefined);
}

export async function deleteAlertRule(id: number): Promise<void> {
  await apiDelete<{ success: boolean }>(`/gold/alerts/rules/${id}`);
}

export async function updateAlertRule(id: number, patch: { enabled?: boolean }): Promise<void> {
  await apiPut<{ success: boolean }>(`/gold/alerts/rules/${id}`, patch);
}

export async function ackAlert(id: number): Promise<void> {
  await apiPost<{ success: boolean }>(`/gold/alerts/${id}/ack`, {});
}

export async function createAlertRule(input: {
  name: string;
  rule_type: string;
  symbol?: string;
  threshold: number;
  channel: "inapp" | "telegram" | "both";
  telegram_chat_id?: string;
  cooldown_minutes: number;
}): Promise<{ id: number }> {
  // The create route answers with the new row's id only.
  const r = await apiPost<{ success: boolean; data: { id: number } }>("/gold/alerts/rules", input);
  return r.data;
}

// ── DCA ─────────────────────────────────────────────────────────

export async function planDCA(input: {
  total_capital_irt: number;
  risk_profile: RiskProfile;
  current_score: number;
  preferred_vehicle?: Vehicle;
}): Promise<DCAPlan> {
  const r = await apiPost<{ success: boolean; data: DCAPlan }>("/gold/dca/plan", input);
  return r.data;
}

// ── Futures (apps/api/endpoints/gold.py) ────────────────────────

export type FuturesPositionRow = {
  id: string;
  contract_symbol: string;
  position_type: string;
  entry_price: number;
  quantity: number;
  leverage: number;
  current_price: number | null;
  liquidation_price: number | null;
  health_ratio: number | null;
  distance_to_liquidation_pct: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  status: string;
  exit_price: number | null;
  exit_reason: string | null;
  opened_at: string | null;
  closed_at: string | null;
};

export async function getFuturesPositions(status: string): Promise<FuturesPositionRow[]> {
  const r = await apiGet<{ success: boolean; data: Array<Record<string, unknown>> }>(
    `/gold/futures/positions?status=${encodeURIComponent(status)}`,
  );
  return (r.data ?? []) as unknown as FuturesPositionRow[];
}

export async function getFuturesHealth(): Promise<{
  health_ratio: number | null;
  critical_count: number;
  warning_count: number;
}> {
  const r = await apiGet<{
    success: boolean;
    data: {
      aggregate_health_ratio: number | null;
      critical_count: number;
      warning_count: number;
    };
  }>("/gold/futures/health");
  const data = r.data;
  return {
    // The API names the portfolio-level figure ``aggregate_health_ratio``.
    health_ratio: data?.aggregate_health_ratio ?? null,
    critical_count: data?.critical_count ?? 0,
    warning_count: data?.warning_count ?? 0,
  };
}

export async function getKillSwitch(): Promise<KillSwitchResp> {
  const r = await apiGet<{ success: boolean; data: KillSwitchResp }>("/gold/kill-switch");
  return r.data;
}

export async function postFuturesMargin(input: {
  entry_price: number;
  position_type: "LONG" | "SHORT";
  leverage: number;
  quantity: number;
  current_price?: number;
  account_equity?: number;
}): Promise<{
  recommended_stop_loss: number | null;
  health_ratio: number | null;
  liquidation_price: number | null;
  alert_message: string | null;
  alert_level: string | null;
  contract_value: number | null;
  initial_margin: number | null;
  maintenance_margin: number | null;
  distance_to_liquidation_pct: number | null;
  leverage: number | null;
  position_type: string | null;
}> {
  const r = await apiPost<{
    success: boolean;
    data: {
      recommended_stop_loss: number | null;
      health_ratio: number | null;
      liquidation_price: number | null;
      alert_message: string | null;
      alert_level: string | null;
      contract_value: number | null;
      initial_margin: number | null;
      maintenance_margin: number | null;
      distance_to_liquidation_pct: number | null;
      leverage: number | null;
      position_type: string | null;
    };
  }>("/gold/futures/margin-calculator", input);
  return r.data;
}

export async function openFuturesPosition(input: {
  contract_symbol: string;
  position_type: "LONG" | "SHORT";
  entry_price: number;
  quantity: number;
  leverage: number;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
}): Promise<{ id: string }> {
  const r = await apiPost<{ success: boolean; data: { id: string } }>(
    "/gold/futures/positions",
    input,
  );
  return r.data;
}

export async function closeFuturesPosition(
  id: string,
  exit: number,
  reason: string,
): Promise<void> {
  await apiPost<{ success: boolean }>(`/gold/futures/positions/${id}/close`, {
    exit_price: exit,
    reason,
  });
}

// ── Physical / arbitrage ────────────────────────────────────────

export type ArbitrageResp = {
  // STEP 8: the endpoint answers ``{available: false, reason, ...}`` when its
  // inputs are missing — that payload carries NO spread fields, so treating
  // them as guaranteed numbers crashed the command center and physical page.
  available: boolean;
  reason?: string | null;
  missing_symbols?: string[];
  pair?: string | null;
  gross_spread_pct?: number | null;
  net_spread_pct?: number | null;
  action?: string | null;
  strategy?: string | null;
  estimated_profit_pct?: number | null;
};

export async function getArbitrage(): Promise<ArbitrageResp | null> {
  const r = await apiGet<{ success: boolean; data: ArbitrageResp | null }>("/gold/arbitrage");
  return r.data;
}

export async function postCoinBubble(input: Record<string, unknown>): Promise<{
  coin: string;
  bubble_pct: number;
  coin_intrinsic_irr: number;
  coin_market_irr: number;
  signal: string;
  reason: string;
}> {
  const r = await apiPost<{
    success: boolean;
    data: {
      coin: string;
      bubble_pct: number;
      coin_intrinsic_irr: number;
      coin_market_irr: number;
      signal: string;
      reason: string;
    };
  }>("/gold/coin-bubble", input);
  return r.data;
}

// ── ETF NAV premium ─────────────────────────────────────────────

export type ETFNavRow = {
  symbol: string;
  fund_name: string;
  isin?: string;
  market_price: number | null;
  nav_per_unit: number | null;
  bubble_pct: number | null;
  signal?: string;
  liquidity?: string;
  management_fee?: string;
  reason?: string;
};

export async function getETFSnapshot(symbol?: string): Promise<{
  best_opportunity: string | null;
  items: ETFNavRow[];
}> {
  const r = await apiGet<{
    success: boolean;
    data: {
      items: Array<{
        symbol: string;
        name_fa: string;
        isin: string;
        market_price: number | null;
        nav: number | null;
        premium_pct: number | null;
        signal: string;
        reason: string;
        liquidity: string;
        management_fee: string;
      }>;
      best_opportunity: string | null;
      generated_at: string;
    };
  }>("/gold/etf-nav-premium");

  const items: ETFNavRow[] = (r.data?.items ?? []).map((row) => ({
    symbol: row.symbol,
    fund_name: row.name_fa,
    isin: row.isin,
    market_price: row.market_price,
    nav_per_unit: row.nav,
    bubble_pct: row.premium_pct,
    signal: row.signal,
    liquidity: row.liquidity,
    management_fee: row.management_fee,
    reason: row.reason,
  }));

  return {
    best_opportunity: r.data?.best_opportunity ?? null,
    items: symbol ? items.filter((row) => row.symbol === symbol) : items,
  };
}

// ── Portfolio ───────────────────────────────────────────────────

export async function getPortfolioPerformance(windowDays: number): Promise<{
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
  benchmarks: Record<string, {
    label: string;
    points: number;
    return_pct: number | null;
    relative_pct: number | null;
    unavailable?: string;
  }>;
  unavailable: Record<string, string>;
}> {
  const r = await apiGet<{
    success: boolean;
    data: {
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
      benchmarks: Record<string, {
        label: string;
        points: number;
        return_pct: number | null;
        relative_pct: number | null;
        unavailable?: string;
      }>;
      unavailable: Record<string, string>;
    };
  }>(`/gold/portfolio/performance?days=${windowDays}`);
  return r.data;
}

export async function capturePortfolioSnapshot(): Promise<void> {
  await apiPost<{ success: boolean }>("/gold/portfolio/snapshot", undefined);
}

// ── Backtests ───────────────────────────────────────────────────

export async function getStrategyBacktest(input: {
  days: number;
  bubble_trigger: number;
  initial_capital: number;
}): Promise<{
  total_return_pct: number;
  buy_hold_return_pct: number;
  alpha_pct: number;
  hit_rate_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  n_successful: number;
  n_trades: number;
  final_value: number;
  warning: string | null;
  trades: Array<{
    tranche: number;
    date: string;
    price: number;
    amount_irt: number;
    units: number;
  }>;
}> {
  const query = new URLSearchParams({
    days: String(input.days),
    bubble_trigger: String(input.bubble_trigger),
    initial_capital: String(input.initial_capital),
  });
  const r = await apiGet<{
    success: boolean;
    data: {
      total_return_pct: number;
      buy_hold_return_pct: number;
      alpha_pct: number;
      hit_rate_pct: number;
      max_drawdown_pct: number;
      sharpe_ratio: number;
      n_successful: number;
      n_trades: number;
      final_value: number;
      warning: string | null;
      trades: Array<{
        tranche: number;
        date: string;
        price: number;
        amount_irt: number;
        units: number;
      }>;
    };
  }>(`/gold/backtest/strategy?${query.toString()}`);
  return r.data;
}

export async function getBacktest(days: number, threshold: number): Promise<{
  signal_days: number;
  forward_30d_avg_pct: number;
  hit_rate_pct: number;
}> {
  const r = await apiGet<{
    success: boolean;
    data: { signal_days: number; forward_30d_avg_pct: number; hit_rate_pct: number };
  }>(`/gold/backtest?days=${days}&bubble_threshold=${threshold}`);
  return r.data;
}

// ── Watchlist ───────────────────────────────────────────────────

export async function getWatchlist(): Promise<{ symbols: string[] }> {
  // Same story as getHealth: the route returns `{symbols, updated_at}` bare.
  const r = await apiGet<{
    symbols?: string[];
    data?: { symbols?: string[] };
  }>("/gold/watchlist");
  return { symbols: r?.symbols ?? r?.data?.symbols ?? [] };
}

export async function putWatchlist(input: { symbols: string[] }): Promise<void> {
  await apiPut<{ success: boolean }>("/gold/watchlist", input);
}

// ── Assistant rules (source of truth: acceptance.yaml) ──────────

export async function getAssistantRules(): Promise<unknown> {
  // Shape is validated (not assumed) by ``parseAssistantRules`` in
  // ``lib/gold-silver-spec.ts``; the endpoint serves the acceptance.yaml block.
  const r = await apiGet<{ success: boolean; data: unknown }>("/gold/assistant-rules");
  return r.data;
}

// ── Portfolio stress testing ─────────────────────────────────────
//
// Public scenario catalogue + authenticated pure calculator. Shocks are
// decimal returns (``0.10`` = +10%); volatility points use ``0.01`` per point.

export type GoldRiskShocks = {
  xau_usd_pct: number;
  usd_irr_pct: number;
  local_premium_pct: number;
  fund_discount_pct: number;
  volatility_points: number;
  liquidity_haircut_pct: number;
};

export type GoldRiskScenario = {
  scenario_id: string;
  name_fa: string;
  name_en: string;
  description_fa: string;
  shocks: GoldRiskShocks;
};

export type GoldRiskAssetType =
  | "gold"
  | "coin"
  | "fund"
  | "etf"
  | "certificate"
  | "futures"
  | "option"
  | "fx"
  | "cash"
  | "other";

export type GoldRiskDirection = "long" | "short";

export type GoldRiskPositionInput = {
  symbol: string;
  asset_type: GoldRiskAssetType;
  direction: GoldRiskDirection;
  exposure_irr: number;
  delta?: number;
  vega_irr_per_vol_point?: number;
  margin_irr?: number;
  maintenance_margin_irr?: number | null;
};

export type GoldRiskScenarioInput = {
  scenario_id: string;
  name_fa?: string;
  name_en?: string;
  description_fa?: string;
  shocks: Partial<GoldRiskShocks>;
};

export type GoldRiskStressInput = {
  equity_irr: number;
  positions: GoldRiskPositionInput[];
  scenarios?: GoldRiskScenarioInput[];
};

export type GoldRiskPositionResult = {
  symbol: string;
  asset_type: GoldRiskAssetType;
  direction: GoldRiskDirection;
  exposure_irr: number;
  market_return_pct: number;
  market_pnl_irr: number;
  vega_pnl_irr: number;
  liquidity_cost_irr: number;
  pnl_irr: number;
};

export type GoldRiskScenarioResult = {
  scenario_id: string;
  name_fa: string;
  name_en: string;
  description_fa: string;
  shocks: GoldRiskShocks;
  pnl_irr: number;
  pnl_pct_of_equity: number | null;
  post_equity_irr: number;
  margin_call: boolean;
  forced_liquidation: boolean;
  maintenance_coverage_ratio: number | null;
  worst_position: GoldRiskPositionResult | null;
  positions: GoldRiskPositionResult[];
};

export type GoldRiskStressResult = {
  available: boolean;
  reason: string | null;
  equity_irr: number;
  gross_exposure_irr: number;
  net_exposure_irr: number;
  net_exposure_pct_of_equity: number;
  gross_leverage_ratio: number;
  margin_irr: number;
  maintenance_margin_irr: number;
  margin_utilization_pct: number;
  concentration_hhi: number | null;
  largest_position_pct: number | null;
  exposure_by_asset_type_irr: Record<string, number>;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";
  worst_case: GoldRiskScenarioResult;
  scenarios: GoldRiskScenarioResult[];
};

export async function getGoldRiskScenarios(): Promise<GoldRiskScenario[]> {
  const r = await apiGet<{ success: boolean; data: GoldRiskScenario[] }>(
    "/gold/analytics/risk/scenarios",
  );
  return r.data ?? [];
}

export async function runGoldRiskStress(
  input: GoldRiskStressInput,
): Promise<GoldRiskStressResult> {
  const r = await apiPost<{ success: boolean; data: GoldRiskStressResult }>(
    "/gold/analytics/risk/stress",
    input as unknown as Record<string, unknown>,
  );
  return r.data;
}

// ── Macro posture (GET /gold/analytics/macro/live) ──────────────────────
//
// Returns ``available=false`` with a ``missing`` list instead of failing when
// the stored TIPS/DXY rows are absent or stale; a 503 is therefore only
// possible from a broken gateway and surfaces as an API error.

export async function getMacroPosture(): Promise<MacroLiveResponse> {
  const r = await apiGet<{ success: boolean; data: MacroLiveResponse }>(
    "/gold/analytics/macro/live",
  );
  return r.data;
}

// ── IME options chain analytics (GET /gold/analytics/options/chain) ─────
//
// Server-side IV / delta / OI enrichment over the stored ``brsapi_ime_options``
// rows. Historical IV is not persisted, so ``iv_rank``/``iv_percentile`` are
// null and ``iv_history_source`` is ``"unavailable"``.

export async function getOptionsChainAnalytics(params?: {
  commodity?: string;
  limit?: number;
  forwardPrice?: number;
  riskFreeRate?: number;
  minVolume?: number;
  minOpenInterest?: number;
  maxBidAskSpreadPct?: number;
}): Promise<OptionsChainReport> {
  const qs = new URLSearchParams();
  if (params?.commodity) qs.set("commodity", params.commodity);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.forwardPrice) qs.set("forward_price", String(params.forwardPrice));
  if (params?.riskFreeRate !== undefined) qs.set("risk_free_rate", String(params.riskFreeRate));
  if (params?.minVolume !== undefined) qs.set("min_volume", String(params.minVolume));
  if (params?.minOpenInterest !== undefined)
    qs.set("min_open_interest", String(params.minOpenInterest));
  if (params?.maxBidAskSpreadPct !== undefined)
    qs.set("max_bid_ask_spread_pct", String(params.maxBidAskSpreadPct));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const r = await apiGet<{ success: boolean; data: OptionsChainReport }>(
    `/gold/analytics/options/chain${suffix}`,
  );
  return r.data;
}

// ── IME option strategy analysis (POST /gold/analytics/options/strategy) ─
//
// The endpoint returns extrema, breakevens and the pre-expiry value; the
// payoff curve itself is intrinsic-value arithmetic and is drawn client-side
// from the same legs so the chart cannot drift from the API's leg list.

export async function runOptionsStrategy(input: {
  strategy: string;
  legs: OptionsStrategyLeg[];
  expiry_price?: number;
  forward_price?: number;
  risk_free_rate?: number;
  days_to_expiry?: number;
  pre_expiry_days?: number;
  pre_expiry_forward?: number;
}): Promise<OptionsStrategyAnalysis> {
  const r = await apiPost<{ success: boolean; data: OptionsStrategyAnalysis }>(
    "/gold/analytics/options/strategy",
    input as unknown as Record<string, unknown>,
  );
  return r.data;
}
