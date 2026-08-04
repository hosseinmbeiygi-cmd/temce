const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const REQUEST_TIMEOUT_MS = 60_000;
const LONG_TIMEOUT_MS = 600_000; // 10 minutes for heavy sync operations

// ── Auth token helpers ──────────────────────────────────────────

const AUTH_STORAGE_KEY = "auth";

function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.access_token ?? null;
  } catch {
    return null;
  }
}

function clearStoredAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

function writeStoredAuth(data: { access_token: string; refresh_token?: string }) {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
      ...parsed,
      access_token: data.access_token,
      refresh_token: data.refresh_token ?? parsed.refresh_token,
    }));
  } catch { /* ignore */ }
}

// ── Silent Token Refresh ────────────────────────────────────────

let _refreshPromise: Promise<string | null> | null = null;

async function _silentRefresh(): Promise<string | null> {
  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (!raw) return null;
      const stored = JSON.parse(raw);
      if (!stored?.refresh_token) return null;

      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: stored.refresh_token }),
      });

      if (!res.ok) return null;

      const json = await res.json();
      const data = json.data ?? json;
      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token ?? stored.refresh_token;

      writeStoredAuth({ access_token: newAccessToken, refresh_token: newRefreshToken });

      return newAccessToken;
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
  clearStoredAuth();
  if (typeof window !== "undefined") {
    const currentPath = window.location.pathname;
    if (!currentPath.startsWith("/auth/")) {
      window.location.href = `/auth/login?redirect=${encodeURIComponent(currentPath)}`;
    }
  }
}

// ── Helper: fetch with timeout ──────────────────────────────────


async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs: number = REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    clearTimeout(timer);
  }
}

// ── Core API Functions ──────────────────────────────────────────

export async function apiGet<T>(
  endpoint: string,
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const authToken = token ?? getStoredAccessToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, { headers });

  // Silent refresh on 401
  if (response.status === 401 && !endpoint.includes('/auth/')) {
    const newToken = await _silentRefresh();
    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`;
      response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, { headers });
    }
  }

  if (response.status === 401) { _handle401(); }
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

export async function apiPost<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null,
  timeoutMs?: number
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const authToken = token ?? getStoredAccessToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers,
    body: data ? JSON.stringify(data) : undefined,
  }, timeoutMs ?? LONG_TIMEOUT_MS);

  // Silent refresh on 401
  if (response.status === 401 && !endpoint.includes('/auth/')) {
    const newToken = await _silentRefresh();
    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`;
      response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers,
        body: data ? JSON.stringify(data) : undefined,
      }, timeoutMs ?? LONG_TIMEOUT_MS);
    }
  }

  if (response.status === 401) { _handle401(); }
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

export async function apiPut<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const authToken = token ?? getStoredAccessToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'PUT',
    headers,
    body: data ? JSON.stringify(data) : undefined,
  });

  // Silent refresh on 401
  if (response.status === 401 && !endpoint.includes('/auth/')) {
    const newToken = await _silentRefresh();
    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`;
      response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
        method: 'PUT',
        headers,
        body: data ? JSON.stringify(data) : undefined,
      });
    }
  }

  if (response.status === 401) { _handle401(); }
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

export async function apiDelete<T>(
  endpoint: string,
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const authToken = token ?? getStoredAccessToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'DELETE',
    headers,
  });

  // Silent refresh on 401
  if (response.status === 401 && !endpoint.includes('/auth/')) {
    const newToken = await _silentRefresh();
    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`;
      response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
        method: 'DELETE',
        headers,
      });
    }
  }

  if (response.status === 401) { _handle401(); }
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

// ── Auth Helpers (legacy, kept for backward compatibility) ───────
// New code should use useAuth() hook from auth-context.tsx instead.

export function getStoredAuth() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearAuth() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function storeAuth(data: { user: Record<string, unknown>; access_token: string; refresh_token?: string }) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(data));
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

export function safeExtractArray<T = unknown>(response: unknown, _endpoint?: string): T[] {
  void _endpoint;
  return extractArray<T>(response);
}