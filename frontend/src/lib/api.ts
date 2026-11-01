import { assertSuccessEnvelope } from './api-envelope';
import { withCsrf } from './csrf';
import { ApiError, ApiTimeoutError, ApiUnauthorizedError } from './api-errors';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const REQUEST_TIMEOUT_MS = 60_000;
const LONG_TIMEOUT_MS = 600_000; // 10 minutes for heavy sync operations

// Consumers such as React Query use this event to drop user-scoped cache data
// whenever the in-memory session is cleared.
export const AUTH_STATE_CLEARED_EVENT = "auth:state-cleared";

// ── Auth token helpers (in-memory, XSS-safe) ────────────────────────
// The refresh token lives in an httpOnly cookie (set by the backend); the
// access token + user are kept in module memory only — never localStorage,
// so an XSS payload cannot exfiltrate them.

interface InMemoryAuth {
  access_token: string | null;
  user?: Record<string, unknown> | null;
}

let _memoryAuth: InMemoryAuth = { access_token: null, user: null };

// Single-flight guard for the 401 path. Many parallel requests fail together
// when a token expires; without this every one of them fired its own logout
// request and its own redirect to /auth/login (a redirect storm).
let _sessionTerminationStarted = false;

/**
 * Access token from storage, or null when nobody is signed in.
 *
 * Exported for the WebSocket clients: a browser cannot attach an
 * ``Authorization`` header to a handshake, so they pass the token as a query
 * parameter instead.
 */
export function getStoredAccessToken(): string | null {
  return _memoryAuth.access_token;
}

function setAccessToken(token: string) {
  _memoryAuth.access_token = token;
}

function setAuthUser(user: Record<string, unknown> | null) {
  _memoryAuth.user = user;
}

function clearStoredAuth() {
  _memoryAuth = { access_token: null, user: null };
}

function writeStoredAuth(data: { access_token: string }) {
  _memoryAuth.access_token = data.access_token;
  // A fresh token means the session is healthy again; a later 401 must be
  // able to terminate it.
  _sessionTerminationStarted = false;
}

// Session restore after a page reload: the access token is gone from memory
// but the refresh cookie survives — exchange it for a fresh access token.
export async function hydrateSession(): Promise<InMemoryAuth> {
  await restoreSession();
  return _memoryAuth;
}

/**
 * Exchange the refresh cookie for an access token — at most once per document.
 *
 * Runs exactly once per page load, no matter who asks first: the auth provider
 * on mount, or an API call that fires before it. That ordering matters for two
 * reasons — the backend revokes the refresh token on every rotation, so two
 * parallel refreshes would log the user out on a plain reload; and a request
 * sent with no token 401s and can clear a perfectly good session.
 */
function restoreSession(): Promise<string | null> {
  if (!_sessionRestore) {
    _sessionRestore = _silentRefresh().then((token) => {
      if (!token) clearStoredAuth();
      return token;
    });
  }
  return _sessionRestore;
}

// ── Silent Token Refresh ────────────────────────────────────────

let _refreshPromise: Promise<string | null> | null = null;
// Per-document session restore (see restoreSession). Request paths await it
// instead of firing a request with no token — those 401s are what used to
// clear a healthy session.
let _sessionRestore: Promise<string | null> | null = null;

async function _silentRefresh(): Promise<string | null> {
  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      // The refresh token lives in an httpOnly cookie — the server reads it.
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: withCsrf({ "Content-Type": "application/json" }, "POST"),
        body: JSON.stringify({}),
        credentials: "include",
      });

      if (!res.ok) return null;

      const json = await res.json();
      const data = json.data ?? json;
      const newAccessToken = data.access_token;

      if (newAccessToken) {
        writeStoredAuth({ access_token: newAccessToken });
        if (data.user) _memoryAuth.user = data.user as Record<string, unknown>;
        return newAccessToken;
      }
      return null;
    } catch {
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// ── 401 Handler ─────────────────────────────────────────────────

function _handle401() {
  // Concurrent 401s: only the first caller terminates the session. The rest
  // see the flag and return without a second logout call or redirect.
  if (_sessionTerminationStarted) return;
  _sessionTerminationStarted = true;

  const accessToken = getStoredAccessToken();
  clearAuth();

  // A failed refresh must not leave the httpOnly cookie alive. JavaScript
  // cannot delete it directly, so expire it through the unauthenticated-safe
  // logout endpoint before redirecting to the login page.
  const headers: HeadersInit = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    void Promise.resolve(
      fetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        headers: withCsrf(headers, "POST"),
        credentials: "include",
      }),
    ).catch(() => undefined);
  } catch {
    // A synchronous fetch failure must not mask the original 401 response.
  }

  if (typeof window !== "undefined") {
    const currentPath = window.location.pathname;
    if (!currentPath.startsWith("/auth/")) {
      // `reason` lets the login page explain why the user landed there.
      window.location.href =
        `/auth/login?redirect=${encodeURIComponent(currentPath)}&reason=session_expired`;
    }
  }
}

// ── Helper: fetch with timeout ──────────────────────────────────


async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs: number = REQUEST_TIMEOUT_MS): Promise<Response> {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(), timeoutMs);
  // Combine the caller's signal (e.g. React Query cancellation on symbol
  // switch) with the internal timeout signal. Previously options.signal was
  // unconditionally overwritten by the internal controller, so external
  // cancellation was silently ignored.
  const externalSignal = options.signal ?? null;
  let combined: AbortSignal = timeoutController.signal;
  let externalListener: (() => void) | null = null;
  if (externalSignal) {
    const anyFn = (AbortSignal as unknown as { any?: (signals: AbortSignal[]) => AbortSignal }).any;
    if (typeof anyFn === "function") {
      combined = anyFn([timeoutController.signal, externalSignal]);
    } else if (externalSignal.aborted) {
      timeoutController.abort();
    } else {
      externalListener = () => timeoutController.abort();
      externalSignal.addEventListener("abort", externalListener, { once: true });
    }
  }
  try {
    const response = await fetch(url, {
      ...options,
      headers: withCsrf(options.headers, options.method),
      signal: combined,
      credentials: "include",
    });
    return response;
  } catch (e) {
    // An externally aborted request must keep its AbortError identity so
    // React Query can distinguish cancellation from a real failure — do not
    // mask it as a timeout.
    if (externalSignal?.aborted) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      // The internal timeout controller is the only remaining abort source.
      // A dedicated type keeps it out of the generic failure path (React Query
      // must not retry it, and the UI shows a timeout-specific message).
      throw new ApiTimeoutError(url, timeoutMs);
    }
    throw e;
  } finally {
    clearTimeout(timer);
    if (externalListener && externalSignal) {
      externalSignal.removeEventListener("abort", externalListener);
    }
  }
}

// ── Core API Functions ──────────────────────────────────────────

async function apiRequest<T>(
  endpoint: string,
  init: RequestInit & { timeoutMs?: number },
  token?: string | null,
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string> | undefined) };
  let authToken = token ?? getStoredAccessToken();
  // Auth endpoints never need a token; everything else may be reached on a
  // fresh document where the session is still being restored from the cookie.
  const sessionOptional = endpoint.includes("/auth/");
  let restoreAttempted = false;
  if (!authToken && !sessionOptional && typeof window !== "undefined") {
    // Restore before sending: a request sent with no token 401s, triggers its
    // own refresh, and races the one the auth provider is already starting.
    restoreAttempted = true;
    await restoreSession();
    authToken = token ?? getStoredAccessToken();
  }
  if (authToken) (headers as Record<string, string>).Authorization = `Bearer ${authToken}`;

  const timeoutMs = init.timeoutMs ?? REQUEST_TIMEOUT_MS;
   
  const { timeoutMs: _t, ...fetchInit } = init as RequestInit & { timeoutMs?: number };

  let response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, { ...fetchInit, headers }, timeoutMs);

  // If the restore just failed there is no session to refresh — retrying the
  // refresh would only burn a second rotation on a dead cookie.
  if (response.status === 401 && !endpoint.includes('/auth/') && !(restoreAttempted && !authToken)) {
    const newToken = await _silentRefresh();
    if (newToken) {
      (headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
      response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, { ...fetchInit, headers }, timeoutMs);
    }
  }

  if (response.status === 401) { _handle401(); }
  if (!response.ok) {
    const errorText = await response.text();
    const message = `HTTP ${response.status}: ${errorText || response.statusText}`;
    if (response.status === 401) throw new ApiUnauthorizedError(message);
    throw new ApiError(message, { status: response.status });
  }
  const payload = (await response.json()) as T;
  // HTTP 200 با `success:false` یعنی منبع داده خطا داده است؛ اگر پاکت را
  // همان‌طور برگردانیم، `extractArray` آن را به `[]` تبدیل می‌کند و صفحه
  // «خالی» را از «خطا» تشخیص نمی‌دهد. پرتاب خطا این حالت را به React Query
  // می‌رساند تا بنر خطا نمایش داده شود (بخش ۰۵).
  assertSuccessEnvelope(payload, endpoint);
  return payload;
}

export async function apiGet<T>(endpoint: string, token?: string | null, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(endpoint, { headers: {}, signal: signal ?? undefined }, token);
}

export async function apiPost<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null,
  timeoutMs?: number
): Promise<T> {
  const postTimeout = timeoutMs ?? (
    endpoint.includes('/backtests') || endpoint.includes('/ml/') || endpoint.includes('/brsapi') || endpoint.includes('/data-import') || endpoint.includes('/orchestrator') || endpoint.includes('/sync')
      ? LONG_TIMEOUT_MS : REQUEST_TIMEOUT_MS
  );
  return apiRequest<T>(endpoint, { method: 'POST', body: data ? JSON.stringify(data) : undefined, timeoutMs: postTimeout }, token);
}

export async function apiPut<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null
): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'PUT', body: data ? JSON.stringify(data) : undefined }, token);
}

export async function apiPatch<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null
): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'PATCH', body: data ? JSON.stringify(data) : undefined }, token);
}

export async function apiDelete<T>(endpoint: string, token?: string | null): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'DELETE' }, token);
}

// ── Auth Helpers (legacy, kept for backward compatibility) ───────
// New code should use useAuth() hook from auth-context.tsx instead.

// Backward-compatible wrappers over the in-memory store (no localStorage).
export function getStoredAuth() {
  if (!_memoryAuth.access_token) return null;
  return {
    access_token: _memoryAuth.access_token,
    user: _memoryAuth.user,
  };
}

export function clearAuth() {
  clearStoredAuth();
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event(AUTH_STATE_CLEARED_EVENT));
  }
}

export function storeAuth(data: { user: Record<string, unknown>; access_token: string }) {
  _memoryAuth.access_token = data.access_token;
  _memoryAuth.user = data.user ?? _memoryAuth.user;
  setAccessToken(data.access_token);
  setAuthUser(data.user ?? _memoryAuth.user);
  _sessionTerminationStarted = false;
}

// ------ Array Extraction (اصلاح‌شده) ------------------------------------------------------------------------------------------------------
export function extractArray<T = unknown>(response: unknown): T[] {
  if (Array.isArray(response)) return response as T[];

  if (response && typeof response === 'object') {
    const obj = response as Record<string, unknown>;
    for (const key of ['data', 'items', 'results', 'list', 'records', 'content', 'docs'] as const) {
      const val = obj[key];
      if (Array.isArray(val)) return val as T[];
      if (val && typeof val === 'object') {
        const nested = extractArray(val);
        if (nested.length > 0) return nested as T[];
      }
    }
    for (const val of Object.values(obj)) {
      if (Array.isArray(val)) return val as T[];
      if (val && typeof val === 'object') {
        const nested = extractArray(val);
        if (nested.length > 0) return nested as T[];
      }
    }
  }
  return [];
}

export function extractItems<T = unknown>(response: unknown): T[] {
  return extractArray<T>(response);
}

export function extractTotal(response: unknown): number {
  if (response && typeof response === 'object') {
    const obj = response as Record<string, unknown>;
    for (const key of ['total', 'totalCount', 'count', 'total_items', 'totalItems'] as const) {
      if (typeof obj[key] === 'number') return obj[key] as number;
      const data = obj['data'] as Record<string, unknown> | undefined;
      if (data && typeof data[key] === 'number') return data[key] as number;
    }
    const data = obj['data'] as Record<string, unknown> | undefined;
    if (data && typeof data === 'object') {
      for (const key of ['total', 'totalCount', 'count', 'total_items', 'totalItems'] as const) {
        if (typeof data[key] === 'number') return data[key] as number;
      }
    }
  }
  return 0;
}

export function safeExtractArray<T = unknown>(response: unknown, endpoint?: string): T[] {
  if (response && typeof response === "object") {
    const obj = response as Record<string, unknown>;
    if (obj.success === false || obj.error || obj.detail) {
      console.warn(`[safeExtractArray] backend error at ${endpoint ?? "?"}:`, obj.error ?? obj.detail ?? obj);
    }
  }
  return extractArray<T>(response);
}
