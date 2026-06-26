const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const REQUEST_TIMEOUT_MS = 15_000;

// ── Helper: fetch with timeout ──────────────────
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

// ── Core API Functions ────
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
  data?: any,
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
  data?: any,
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

// ── Auth Helpers ──────────────────────────────────────
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

export function storeAuth(data: { user: any; access_token: string; refresh_token?: string }) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('auth', JSON.stringify(data));
}

// ── Array Extraction (اصلاح‌شده) ──────────────────────────────────
export function extractArray(response: any): any[] {
  if (Array.isArray(response)) return response;

  if (response && typeof response === 'object') {
    for (const key of ['data', 'items', 'results', 'list', 'records', 'content', 'docs']) {
      const val = response[key];
      if (Array.isArray(val)) return val;
      if (val && typeof val === 'object') {
        const nested = extractArray(val);
        if (nested.length > 0) return nested;
      }
    }
    for (const val of Object.values(response)) {
      if (Array.isArray(val)) return val;
      if (val && typeof val === 'object') {
        const nested = extractArray(val);
        if (nested.length > 0) return nested;
      }
    }
  }
  return [];
}

export function extractItems(response: any): any[] {
  return extractArray(response);
}

export function extractTotal(response: any): number {
  if (response && typeof response === 'object') {
    for (const key of ['total', 'totalCount', 'count', 'total_items', 'totalItems']) {
      if (typeof response[key] === 'number') return response[key];
      if (response.data && typeof response.data[key] === 'number') return response.data[key];
    }
    if (response.data && typeof response.data === 'object') {
      for (const key of ['total', 'totalCount', 'count', 'total_items', 'totalItems']) {
        if (typeof response.data[key] === 'number') return response.data[key];
      }
    }
  }
  return 0;
}

export function safeExtractArray(response: any, endpoint?: string): any[] {
  return extractArray(response);
}