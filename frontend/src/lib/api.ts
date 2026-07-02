const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const REQUEST_TIMEOUT_MS = 15_000;

// ------ Helper: fetch with timeout ------------------------------------------------------
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

// ------ Core API Functions ------------
export async function apiGet<T>(
  endpoint: string,
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, { headers });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

export async function apiPost<T>(
  endpoint: string,
  data?: Record<string, unknown>,
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers,
    body: data ? JSON.stringify(data) : undefined,
  });
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
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'PUT',
    headers,
    body: data ? JSON.stringify(data) : undefined,
  });
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
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
    method: 'DELETE',
    headers,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
  }
  return response.json();
}

// ------ Auth Helpers ------------------------------------------------------------------------------------------------------------------
export function getStoredAuth() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('auth');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearAuth() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('auth');
}

export function storeAuth(data: { user: Record<string, unknown>; access_token: string; refresh_token?: string }) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('auth', JSON.stringify(data));
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