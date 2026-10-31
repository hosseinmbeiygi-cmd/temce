// extended gold API client
//
// Every path here must exist in the mounted API surface:
//   * ``/gold/...``      — src/gold_desk/api.py (personal GoldDesk surface)
//   * ``/gold/...``      — apps/api/endpoints/gold.py (calculators/futures, mounted in router.py)
//   * ``/gold/analytics`` — apps/api/endpoints/gold_analytics.py

import { apiDelete, apiGet, apiPost, apiPut, getStoredAccessToken } from "@/lib/api";
import { ApiEnvelopeError } from "@/lib/api-envelope";
import { fetchWsTicket } from "@/lib/wsTicket";
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
  ScoreBlock,
  Snapshot,
  Vehicle,
} from "@/types/gold";
import type { GoldTerminal, GoldWhatIf } from "@/types/phase1";
import type {
  FundMapResponse,
  PlatformsResponse,
  ReturnsMatrixResponse,
  TehranBoardResponse,
} from "@/types/phase2";

export type { KillSwitchResp } from "@/types/gold";

/**
 * C3: surfaces مبتنی بر snapshot (/snapshot، /score، /signals/recent) در قطعی
 * داده با یک کد واحد جواب می‌دهند تا UI بتواند «سرویس در دسترس نیست» را از
 * «پاسخ بد» جدا کند. متن خطای داخلی هرگز به کاربر نشان داده نمی‌شود.
 */
export const SNAPSHOT_UNAVAILABLE = "snapshot_unavailable";

/**
 * خطای لایهٔ gold. پیامش برای کاربر است (فارسی و عمومی)، `detail` فقط برای لاگ.
 *
 * بک‌اند امروز در خطا HTTP 200 با `{success: false, data: null, error: {…}}`
 * برمی‌گرداند (`src/gold_desk/api.py:95-103`) و طبق C3 فردا 503 می‌دهد؛ این کلاس
 * هر دو را به یک نوع واحد تبدیل می‌کند تا merge سه‌طرفه اتمیک باشد.
 */
export class GoldAPIError extends Error {
  readonly status: number | null;
  readonly code: string | null;
  /** جزئیات داخلی — فقط برای کنسول/لاگ، نه برای رندر (C3). */
  readonly detail: string | null;

  constructor(
    message: string,
    options: { status?: number | null; code?: string | null; detail?: string | null } = {},
  ) {
    super(message);
    this.name = "GoldAPIError";
    this.status = options.status ?? null;
    this.code = options.code ?? null;
    this.detail = options.detail ?? null;
  }
}

/** آیا این خطا یعنی سرویس طلا موقتاً خوابیده؟ (۵۰۳ یا کد C3) */
export function isServiceUnavailable(error: unknown): boolean {
  if (error instanceof GoldAPIError) {
    return error.status === 503 || error.code === SNAPSHOT_UNAVAILABLE;
  }
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /\b503\b/.test(message);
}

/** `api.ts` خطا را به شکل `HTTP <status>: <body>` می‌سازد؛ اینها همان را برگ می‌گردانند. */
function httpStatusFromMessage(message: string): number | null {
  const m = /^HTTP (\d{3})/.exec(message);
  return m ? Number(m[1]) : null;
}

function bodyFromMessage(message: string): unknown {
  const idx = message.indexOf(": ");
  if (idx < 0) return null;
  try {
    return JSON.parse(message.slice(idx + 2));
  } catch {
    return null;
  }
}

function detailOf(error: unknown): string | null {
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    return typeof message === "string" ? message : String(message);
  }
  return error === undefined || error === null ? null : String(error);
}

/**
 * پاسخ gold را باز می‌کند. سه شکل را می‌پذیرد:
 *   ۱) پاکت سالم `{success: true, data}`            → همان data
 *   ۲) پاسخ برهنه (معیار امروز `/dca/plan`)         → خودِ بدنه
 *   ۳) `{success: false}` یا `data: null`            → throw (بدون undefined!)
 *
 * مورد ۳ دقیقاً همان جایی بود که `r.data` مقدار `undefined` می‌داد و React Query
 * آن را رد می‌کرد («Query data cannot be undefined») — صفحهٔ خطای مبهم.
 */
function unwrapGoldPayload<T>(payload: unknown, label: string, code: string | null): T {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const envelope = payload as { success?: boolean; data?: unknown; error?: unknown };
    if (envelope.success === false) {
      const detail = detailOf(envelope.error);
      console.warn(`[goldApi] ${label}: backend reported failure`, detail ?? envelope);
      throw new GoldAPIError(`${label}: داده در دسترس نیست`, { code, detail });
    }
    if ("data" in envelope) {
      if (envelope.data === null || envelope.data === undefined) {
        throw new GoldAPIError(`${label}: داده در دسترس نیست`, { code });
      }
      return envelope.data as T;
    }
    return payload as T;
  }
  if (Array.isArray(payload)) return payload as unknown as T;
  throw new GoldAPIError(`${label}: پاسخ غیرمنتظره است`, { code });
}

function normalizeGoldError(error: unknown, label: string, code: string | null): GoldAPIError {
  if (error instanceof GoldAPIError) return error;
  // `api.ts` اکنون خودِ پاکت `success:false` را رد می‌کند (بخش ۰۵)، پس خطای
  // snapshot پیش از رسیدن به `unwrapGoldPayload` پرتاب می‌شود. نگاشت C3 باید
  // همان کد «داده در دسترس نیست» را بدهد تا UI کد ۵۰۳ را از خطای عمومی جدا کند.
  if (error instanceof ApiEnvelopeError) {
    console.warn(`[goldApi] ${label}: backend reported failure`, error.detail ?? error.message);
    return new GoldAPIError(`${label}: داده در دسترس نیست`, {
      code: error.code ?? code,
      detail: error.detail === null || error.detail === undefined ? null : JSON.stringify(error.detail),
    });
  }
  const message = error instanceof Error ? error.message : String(error ?? "");
  const status = httpStatusFromMessage(message);
  if (status === 503) {
    // بدنهٔ ۵۰۳ ممکن است هیچ متن قابل‌نمایشی نداشته باشد (C3) — فقط لاگ می‌شود.
    console.warn(`[goldApi] ${label}: HTTP 503`, message);
    return new GoldAPIError(`${label}: سرویس دادهٔ طلا موقتاً در دسترس نیست`, {
      status,
      code: code ?? SNAPSHOT_UNAVAILABLE,
      detail: message,
    });
  }
  return new GoldAPIError(message, { status, detail: message });
}

/** اجرای یک فراخوان gold با نرمال‌سازی خطا و باز کردن پاکت. */
async function goldCall<T>(
  label: string,
  code: string | null,
  run: () => Promise<unknown>,
): Promise<T> {
  let payload: unknown;
  try {
    payload = await run();
  } catch (error) {
    throw normalizeGoldError(error, label, code);
  }
  return unwrapGoldPayload<T>(payload, label, code);
}

// ── Snapshot-backed reads ────────────────────────────────────────

export async function getSnapshot(): Promise<Snapshot> {
  return goldCall<Snapshot>("snapshot", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>("/gold/snapshot"),
  );
}

/**
 * امتیاز فعلی به‌تنهایی (`GET /gold/score`).
 *
 * هیچ صفحه‌ای در درخت gold امروز این مسیر را صدا نمی‌زند — امتیاز از دل
 * `snapshot.score` می‌آید — ولی C3 این endpoint را نام می‌برد، پس reader با
 * همان نگاشت خطا در دسترس است تا فراخوانِ بعدی مجبور به `fetch` خام نشود.
 */
export async function getScore(): Promise<ScoreBlock> {
  return goldCall<ScoreBlock>("score", SNAPSHOT_UNAVAILABLE, () => apiGet<unknown>("/gold/score"));
}

export async function getScoreHistory(days: number): Promise<
  Array<{ score_at: string; total: number; decision: string; hard_stop_active: boolean }>
> {
  const data = await goldCall<{
    items?: Array<{ score_at: string; total: number; decision: string; hard_stop_active: boolean }>;
  }>("score-history", null, () => apiGet<unknown>(`/gold/history/score?days=${days}`));
  return data?.items ?? [];
}

export async function getSnapshotHistory(symbol: string, days: number): Promise<
  Array<{ snapshot_at: string; bubble_pct: number | null }>
> {
  const data = await goldCall<{
    items?: Array<{ snapshot_at: string; bubble_pct: number | null }>;
  }>("snapshot-history", null, () =>
    apiGet<unknown>(
      `/gold/history/snapshot?symbol=${encodeURIComponent(symbol)}&days=${days}`,
    ),
  );
  return data?.items ?? [];
}

export async function getGoldLivePrices(): Promise<Record<string, number>> {
  return goldCall<Record<string, number>>("live-prices", null, () =>
    apiGet<unknown>("/gold/live-prices"),
  );
}

// ── Phase 1 data terminal ───────────────────────────────────────
//
// Every value is Rial except ``xau_usd``. ``null`` is a real answer (source did
// not provide it) and must be rendered «—», never as zero. The what-if route is
// a preview: it writes nothing and its rows carry quality ``SAMPLE``.

export async function getGoldTerminal(): Promise<GoldTerminal> {
  return goldCall<GoldTerminal>("terminal", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>("/gold/terminal"),
  );
}

export async function postGoldWhatIf(input: {
  xau_usd: number;
  usd_irt_rial: number;
}): Promise<GoldWhatIf> {
  return goldCall<GoldWhatIf>("what-if", SNAPSHOT_UNAVAILABLE, () =>
    apiPost<unknown>("/gold/what-if", input),
  );
}

// ── Phase 2 market coverage (read-only) ─────────────────────────
//
// Tehran shop prices, online-platform comparison, the returns matrix and the
// fund market map. None of these routes can place an order or take payment —
// the payloads carry `capabilities` with every trading flag false, and the UI
// must not add a buy/cart/checkout control on top of them.

export async function getGoldTehranBoard(): Promise<TehranBoardResponse> {
  return goldCall<TehranBoardResponse>("tehran-board", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>("/gold/tehran-board"),
  );
}

export async function getGoldPlatforms(): Promise<PlatformsResponse> {
  return goldCall<PlatformsResponse>("platforms", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>("/gold/platforms"),
  );
}

export async function getGoldReturnsMatrix(
  baseCurrency: "IRR" | "USD" = "IRR",
): Promise<ReturnsMatrixResponse> {
  return goldCall<ReturnsMatrixResponse>("returns-matrix", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>(`/gold/returns-matrix?base_currency=${baseCurrency}`),
  );
}

export async function getGoldFundMap(
  sizeMetric: "trade_value" | "market_value" = "trade_value",
): Promise<FundMapResponse> {
  return goldCall<FundMapResponse>("fund-map", SNAPSHOT_UNAVAILABLE, () =>
    apiGet<unknown>(`/gold/fund-map?size_metric=${sizeMetric}`),
  );
}

// ── Health / freshness ──────────────────────────────────────────

function asHealthReport(payload: unknown): HealthResponse {
  return unwrapGoldPayload<HealthResponse>(payload, "health", null);
}

export async function getHealth(): Promise<HealthResponse> {
  // C8: قطعی Redis یا DB با HTTP 503 گزارش می‌شود، ولی بدنه همچنان همان
  // گزارش تک‌تک وابستگی‌هاست. صفحهٔ سلامت باید بگوید «کدام» خوابیده، نه یک
  // خطای مبهم — پس 503 اینجا مسیر داده‌دار است، نه مسیر خطا.
  try {
    return asHealthReport(await apiGet<unknown>("/gold/health"));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error ?? "");
    const body = bodyFromMessage(message);
    if (body && typeof body === "object" && "redis_ok" in body) return asHealthReport(body);
    throw normalizeGoldError(error, "health", null);
  }
}

export async function getFreshness(): Promise<FreshnessReport> {
  return goldCall<FreshnessReport>("freshness", null, () => apiGet<unknown>("/gold/freshness"));
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
// The backend pushes on `/gold/ws` (src/gold_desk/ws_hub.py). Per C10 there are
// two cadences — `hot` (light, every 10s) and `snapshot` (full, every 300s) —
// plus `signal` frames that live_signals.py already broadcasts today. The
// manager understands all three and timestamps them, because the UI needs to
// tell «اتصال زنده» from «اتصال وصل ولی دادهٔ تازه نمی‌آید».
// A browser cannot attach an Authorization header to a handshake, so the access
// token travels as a query parameter.

export type WSState = "connecting" | "open" | "closed" | "error";

/** بدنهٔ پیام `hot` — دقیقاً همان کلیدهایی که `build_hotpath_response` می‌سازد. */
export interface GoldHotPayload {
  status: "ok" | "no_data";
  timestamp?: string | null;
  message?: string | null;
  refs?: { xau_usd: number | null; usd_irt: number | null; aed_gap_pct: number | null };
  score?: { total: number | null; decision: string | null };
  signal?: { action: string | null; confidence: number | null; reason: string | null };
  coin_emami?: {
    market: number | null;
    fair: number | null;
    bubble_pct: number | null;
    implied_usd: number | null;
  };
  top_funds?: Array<{
    symbol: string;
    name: string | null;
    nav: number | null;
    bubble_pct: number | null;
    bpr: number | null;
  }>;
}

/**
 * as_of سیم (ISO 8601) را به epoch ms تبدیل می‌کند؛ مقدار غیر ISO ⇒ null.
 *
 * عمداً فقط شکل ISO را می‌پذیریم: `Date.parse` رشته‌های مبهمی مثل "12" را هم
 * عدد می‌کند و آن‌وقت کهنگی با یک زمان جعلی محاسبه می‌شود.
 */
export function parseAsOf(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const raw = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(raw)) {
    return null;
  }
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

export interface GoldWSInfo {
  state: WSState;
  /** epoch ms آخرین پیامِ معتبر (هر نوعی) — زمان رسیدن، برای fallback. */
  lastMessageAt: number | null;
  lastSnapshotAt: number | null;
  lastHotAt: number | null;
  /** epoch ms تازه‌ترین `as_of` (یا زمان رسیدن اگر as_of نبود/نامعتبر بود). */
  lastAsOfAt: number | null;
  /** `as_of` آخرین فریم hot — آستانهٔ کهنگی ۲× بازهٔ hot. */
  lastHotAsOfAt: number | null;
  /** `as_of` آخرین فریم snapshot — آستانهٔ کهنگی ۶۰۰ ثانیه. */
  lastSnapshotAsOfAt: number | null;
  lastHot: GoldHotPayload | null;
}

type WSListener = (state: WSState, snap: Snapshot | null, info: GoldWSInfo) => void;

function goldWebSocketUrl(ticket: string | null): string | null {
  if (typeof window === "undefined") return null;
  const base = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
  const root = base.startsWith("http")
    ? base.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${base}`;
  // FE-06: only the single-use ticket belongs in the handshake URL; the
  // access token must never be exposed to logs/history via the query string.
  return `${root.replace(/\/$/, "")}/gold/ws${ticket ? `?ticket=${encodeURIComponent(ticket)}` : ""}`;
}

class GoldWSManager {
  private ws: WebSocket | null = null;
  private listeners = new Set<WSListener>();
  private state: WSState = "closed";
  private lastSnapshot: Snapshot | null = null;
  private lastHot: GoldHotPayload | null = null;
  private lastMessageAt: number | null = null;
  private lastSnapshotAt: number | null = null;
  private lastHotAt: number | null = null;
  private lastAsOfAt: number | null = null;
  private lastHotAsOfAt: number | null = null;
  private lastSnapshotAsOfAt: number | null = null;
  private retryDelay = 1000;
  private readonly maxRetryDelay = 30_000;
  private reconnectTimer: number | null = null;
  private pingInterval: number | null = null;
  /** Bumped on every connect(): a slow ticket request must not dial late. */
  private connectSeq = 0;

  private info(): GoldWSInfo {
    return {
      state: this.state,
      lastMessageAt: this.lastMessageAt,
      lastSnapshotAt: this.lastSnapshotAt,
      lastHotAt: this.lastHotAt,
      lastAsOfAt: this.lastAsOfAt,
      lastHotAsOfAt: this.lastHotAsOfAt,
      lastSnapshotAsOfAt: this.lastSnapshotAsOfAt,
      lastHot: this.lastHot,
    };
  }

  subscribe(listener: WSListener): () => void {
    this.listeners.add(listener);
    listener(this.state, this.lastSnapshot, this.info());
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

    // FE-06: exchange the session for a single-use ticket before dialing; the
    // access token itself never enters the WebSocket URL.
    const seq = ++this.connectSeq;
    void fetchWsTicket()
      .then((ticket) => {
        if (seq !== this.connectSeq || this.listeners.size === 0) return;
        if (!ticket) {
          this.setState("error");
          this.scheduleReconnect();
          return;
        }
        const url = goldWebSocketUrl(ticket);
        if (url) this.dial(url);
      })
      .catch(() => {
        if (seq !== this.connectSeq || this.listeners.size === 0) return;
        this.setState("error");
        this.scheduleReconnect();
      });
  }

  private dial(url: string) {
    this.setState("connecting");
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      // Backoff فقط تا یک اتصال موفق دوام می‌آورد؛ بعد از باز شدن سوکت به
      // مقدار اولیه برمی‌گردد تا قطعی‌های مقطعی جریمه نشوند.
      this.retryDelay = 1000;
      this.setState("open");
      this.pingInterval = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30_000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as {
          type?: string;
          as_of?: unknown;
          data?: Snapshot | GoldHotPayload | Record<string, unknown>;
        };
        const now = Date.now();
        // کهنگی از زمان داده (`as_of`) می‌آید، نه از زمان رسیدن؛ as_of نامعتبر
        // یا غایب ⇒ fallback به زمان رسیدن (بدون کرش).
        const dataAt = parseAsOf(msg.as_of) ?? now;
        const freshest = (previous: number | null) => Math.max(previous ?? 0, dataAt);
        if (msg.type === "snapshot" && msg.data) {
          this.lastSnapshot = msg.data as Snapshot;
          this.lastSnapshotAt = now;
          this.lastSnapshotAsOfAt = freshest(this.lastSnapshotAsOfAt);
          this.lastAsOfAt = freshest(this.lastAsOfAt);
          this.lastMessageAt = now;
          this.setState("open", this.lastSnapshot);
        } else if (msg.type === "hot" && msg.data) {
          // hot جای snapshot را نمی‌گیرد (کم‌حجم است و بیشتر فیلدها را ندارد)،
          // ولی ثابت می‌کند خط زنده است.
          this.lastHot = msg.data as GoldHotPayload;
          this.lastHotAt = now;
          this.lastHotAsOfAt = freshest(this.lastHotAsOfAt);
          this.lastAsOfAt = freshest(this.lastAsOfAt);
          this.lastMessageAt = now;
          this.setState(this.state, this.lastSnapshot);
        } else if (msg.type === "signal") {
          this.lastAsOfAt = freshest(this.lastAsOfAt);
          this.lastMessageAt = now;
          this.setState(this.state, this.lastSnapshot);
        }
      } catch {
        /* non-JSON heartbeat frames (the hub's "pong") are ignored */
      }
    };

    ws.onerror = () => this.setState("error");

    ws.onclose = () => {
      this.cleanup();
      this.setState("closed");
      this.scheduleReconnect();
    };
  }

  /**
   * backoff نمایی: 1s → 2s → 4s … تا ۳۰ ثانیه (maxRetryDelay). تایمر one-shot
   * است تا چند قطعیِ پیاپی چند سوکت هم‌زمان نسازند.
   */
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
    this.lastHot = null;
    this.lastMessageAt = null;
    this.lastSnapshotAt = null;
    this.lastHotAt = null;
    this.lastAsOfAt = null;
    this.lastHotAsOfAt = null;
    this.lastSnapshotAsOfAt = null;
    this.setState("closed", null);
  }

  private setState(state: WSState, snap: Snapshot | null = this.lastSnapshot) {
    this.state = state;
    const info = this.info();
    this.listeners.forEach((listener) => listener(state, snap, info));
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
 *
 * امضا دست‌نخورده مانده (قاعده ۴)؛ برای کهنگی و `hot` از `useGoldWS` استفاده
 * کنید که همین manager را با listener کامل‌تر subscribe می‌کند.
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

/**
 * C4: `current_score` دیگر از کلاینت خوانده نمی‌شود — بک‌اند آن را از snapshot
 * سمت سرور برمی‌دارد. اگر فراخوانی قدیمی هنوز آن را بفرستد، همین‌جا قبل از
 * ارسال حذف می‌شود تا قرارداد نقض نشود.
 */
export async function planDCA(input: {
  total_capital_irt: number;
  risk_profile: RiskProfile;
  preferred_vehicle?: Vehicle;
}): Promise<DCAPlan> {
  const { current_score: _droppedByContract, ...payload } = input as Record<string, unknown>;
  return goldCall<DCAPlan>("dca-plan", null, () =>
    apiPost<unknown>("/gold/dca/plan", payload),
  );
}

// ── Live signals (GET /signals/recent) ──────────────────────────

/**
 * سیگنال‌های زندهٔ مسیر `/gold/signals/recent`.
 *
 * قبلاً `LiveSignalBanner` مستقیم `apiGet` می‌زد و خطا را دور می‌ریخت، یعنی در
 * قطعی سرویس بنر بی‌سروصدا غیب می‌شد (F2). این reader همان نگاشت C3 را دارد.
 */
export interface GoldLiveSignal {
  symbol: string;
  signal_type: string;
  severity: string;
  title: string;
  description: string;
  current_value: number;
  threshold: number;
  change_pct: number | null;
  ts: number;
}

export async function getRecentSignals(limit = 10): Promise<GoldLiveSignal[]> {
  const data = await goldCall<{ signals?: GoldLiveSignal[] } | GoldLiveSignal[]>(
    "signals",
    SNAPSHOT_UNAVAILABLE,
    () => apiGet<unknown>(`/gold/signals/recent?limit=${limit}`),
  );
  if (Array.isArray(data)) return data;
  return data?.signals ?? [];
}

// ── API tokens (GET/POST/DELETE /tokens) ────────────────────────
//
// صفحهٔ /gold/tokens قبلاً `fetch` خام می‌زد: prefix /api/v1 را نمی‌گرفت،
// هدر Authorization نمی‌رفت و مسیر ۴۰۱/refresh دور زده می‌شد — یعنی در
// production عملاً کار نمی‌کرد (F8).

export interface GoldApiToken {
  token_id: string;
  name: string;
  scopes: string[];
  enabled: boolean;
  created_at: string | null;
  last_used_at: string | null;
}

export async function getApiTokens(): Promise<GoldApiToken[]> {
  return goldCall<GoldApiToken[]>("tokens", null, () => apiGet<unknown>("/gold/tokens"));
}

/**
 * route این endpoint پارامترها را در query می‌خواند
 * (`name: str = Query(...)`, `api.py:714-717`)، پس query string اینجا درست است.
 *
 * پاسخ `{success:true, data:{token, token_id}}` است؛ `token` خام فقط یک‌بار
 * برگردانده می‌شود و باید همان لحظه کپی شود.
 */
export async function createApiToken(
  name: string,
  scopes: string,
): Promise<{ token: string; token_id: string }> {
  const query = new URLSearchParams({ name, scopes });
  return goldCall<{ token: string; token_id: string }>("token-create", null, () =>
    apiPost<unknown>(`/gold/tokens?${query.toString()}`),
  );
}

export async function revokeApiToken(tokenId: string): Promise<boolean> {
  const r = await goldCall<{ success?: boolean } | boolean>("token-revoke", null, () =>
    apiDelete<unknown>(`/gold/tokens/${encodeURIComponent(tokenId)}`),
  );
  return typeof r === "boolean" ? r : Boolean(r?.success);
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
  critical_count: number | null;
  warning_count: number | null;
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
    // Missing counts stay null so the UI renders "—" instead of a fabricated 0.
    health_ratio: data?.aggregate_health_ratio ?? null,
    critical_count: data?.critical_count ?? null,
    warning_count: data?.warning_count ?? null,
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
  generated_at: string | null;
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
    generated_at: r.data?.generated_at ?? null,
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
  // ── out-of-sample (C/قرارداد F7) ──
  // موتور این‌ها را در `BacktestMetrics` دارد (`backtest_runner.py:77-81`) ولی
  // route `/backtest/strategy` فعلاً serialize شان نمی‌کند، پس **اختیاری‌اند**:
  // نبودشان با صفر فرق دارد و UI باید تفاوت را ببیند.
  oos_start?: string | null;
  oos_total_return_pct?: number | null;
  oos_buy_hold_return_pct?: number | null;
  oos_alpha_pct?: number | null;
  oos_max_drawdown_pct?: number | null;
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
      oos_start?: string | null;
      oos_total_return_pct?: number | null;
      oos_buy_hold_return_pct?: number | null;
      oos_alpha_pct?: number | null;
      oos_max_drawdown_pct?: number | null;
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
