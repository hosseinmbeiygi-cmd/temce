const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
const REQUEST_TIMEOUT_MS = 60_000;
const LONG_TIMEOUT_MS = 600_000; // 10 minutes for heavy sync operations

// ── Auth token helpers (in-memory, XSS-safe) ────────────────────────
// The refresh token lives in an httpOnly cookie (set by the backend); the
// access token + user are kept in module memory only — never localStorage,
// so an XSS payload cannot exfiltrate them.

interface InMemoryAuth {
  access_token: string | null;
  refresh_token?: string;
  user?: Record<string, unknown> | null;
}

let _memoryAuth: InMemoryAuth = { access_token: null, refresh_token: undefined, user: null };

function getStoredAccessToken(): string | null {
  return _memoryAuth.access_token;
}

function setAccessToken(token: string) {
  _memoryAuth.access_token = token;
}

function setAuthUser(user: Record<string, unknown> | null) {
  _memoryAuth.user = user;
}

function clearStoredAuth() {
  _memoryAuth = { access_token: null, refresh_token: undefined, user: null };
}

function writeStoredAuth(data: { access_token: string; refresh_token?: string }) {
  _memoryAuth.access_token = data.access_token;
  if (data.refresh_token) _memoryAuth.refresh_token = data.refresh_token;
}

// Session restore after a page reload: the access token is gone from memory
// but the refresh cookie survives — exchange it for a fresh access token.
export async function hydrateSession(): Promise<InMemoryAuth> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: "" }), // token read from httpOnly cookie
      credentials: "include",
    });
    if (!res.ok) {
      clearStoredAuth();
      return _memoryAuth;
    }
    const json = await res.json();
    const data = json.data ?? json;
    if (data?.access_token) {
      _memoryAuth.access_token = data.access_token;
      if (data.refresh_token) _memoryAuth.refresh_token = data.refresh_token;
      if (data.user) _memoryAuth.user = data.user as Record<string, unknown>;
    } else {
      clearStoredAuth();
    }
  } catch {
    clearStoredAuth();
  }
  return _memoryAuth;
}

// ── Silent Token Refresh ────────────────────────────────────────

let _refreshPromise: Promise<string | null> | null = null;

async function _silentRefresh(): Promise<string | null> {
  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      // The refresh token lives in an httpOnly cookie — the server reads it.
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: "" }),
        credentials: "include",
      });

      if (!res.ok) return null;

      const json = await res.json();
      const data = json.data ?? json;
      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token;

      if (newAccessToken) {
        writeStoredAuth({ access_token: newAccessToken, refresh_token: newRefreshToken });
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
    const response = await fetch(url, {
    ...options,
    signal: controller.signal,
    credentials: "include",
  });
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

// Backward-compatible wrappers over the in-memory store (no localStorage).
export function getStoredAuth() {
  if (!_memoryAuth.access_token) return null;
  return {
    access_token: _memoryAuth.access_token,
    refresh_token: _memoryAuth.refresh_token,
    user: _memoryAuth.user,
  };
}

export function clearAuth() {
  clearStoredAuth();
}

export function storeAuth(data: { user: Record<string, unknown>; access_token: string; refresh_token?: string }) {
  _memoryAuth.access_token = data.access_token;
  if (data.refresh_token) _memoryAuth.refresh_token = data.refresh_token;
  _memoryAuth.user = data.user ?? _memoryAuth.user;
  setAccessToken(data.access_token);
  setAuthUser(data.user ?? _memoryAuth.user);
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