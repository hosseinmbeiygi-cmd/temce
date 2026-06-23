// ── API Client ──────────────────────────────────────
// All requests go through the Next.js rewrites proxy at /api/v1/*
// The Next.js server (server-side) then forwards to the backend.
// This works both in Docker (server can resolve api:8000) and locally.
// Never use an absolute URL here — it would bypass the proxy & fail
// in Docker because the browser can't resolve Docker hostnames.

const API_BASE = "/api/v1";

// ── Token Management ────────────────────────────────
export function getStoredAuth(): { token: string; refreshToken: string; user: any } | null {
  try {
    const raw = localStorage.getItem("auth");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function storeAuth(data: { access_token: string; refresh_token: string; user: any }) {
  localStorage.setItem("auth", JSON.stringify({ token: data.access_token, refreshToken: data.refresh_token, user: data.user }));
}

export function clearAuth() {
  localStorage.removeItem("auth");
}

// ── Extract Data Helper ─────────────────────────────
// Backend returns: { success: true, data: T, error: ... }
// Some endpoints return paginated: { success: true, data: { items: [], total, page, ... } }
// This helper extracts the actual data array from various response shapes.
export function extractArray<T = any>(response: any): T[] {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  // PaginatedResult: { items: [...], total, page, ... }
  if (response.items && Array.isArray(response.items)) return response.items;
  // Other common array wrappers
  if (response.data && Array.isArray(response.data)) return response.data;
  if (response.results && Array.isArray(response.results)) return response.results;
  if (response.records && Array.isArray(response.records)) return response.records;
  return [];
}

// ── Request Headers ─────────────────────────────────
function getHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // If no token provided, try to use stored auth
  if (!token) {
    const auth = getStoredAuth();
    if (auth?.token) headers["Authorization"] = `Bearer ${auth.token}`;
  }
  return headers;
}

// ── Response Parsing ─────────────────────────────────
// Shared between fetch & XHR code paths so the ApiResponse envelope unwrap
// lives in exactly one place.
function parseApiResponse<T>(status: number, contentType: string, raw: string): T {
  const ok = status >= 200 && status < 300;
  if (!contentType.includes("application/json")) {
    if (!ok) {
      throw new Error(`HTTP ${status}: ${raw.substring(0, 200)}`);
    }
    return raw as unknown as T;
  }

  let json: any;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new Error(`Invalid JSON response (HTTP ${status})`);
  }

  if (json && typeof json === "object" && "success" in json) {
    if (!json.success) {
      const errMsg = json.error?.message || json.error || `Request failed (${status})`;
      throw new Error(typeof errMsg === "string" ? errMsg : `Request failed (${status})`);
    }
    return json.data as T;
  }
  return json as T;
}

// ── Request Functions ───────────────────────────────
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  token?: string,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: getHeaders(token),
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  return parseApiResponse<T>(res.status, res.headers.get("content-type") || "", raw);
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  return request<T>("GET", path, undefined, token);
}

export async function apiPost<T>(path: string, body: unknown, token?: string): Promise<T> {
  return request<T>("POST", path, body, token);
}

export async function apiPut<T>(path: string, body: unknown, token?: string): Promise<T> {
  return request<T>("PUT", path, body, token);
}

export async function apiDelete<T>(path: string, token?: string): Promise<T> {
  return request<T>("DELETE", path, undefined, token);
}

// ── Multipart Upload ──────────────────────────────────
// POSTs a FormData payload. We intentionally do NOT set a Content-Type header
// here so the browser can attach the correct multipart/form-data; boundary=….
// Any Content-Type set by us would override the boundary and corrupt the body.
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  token?: string,
  onProgress?: (loaded: number, total: number) => void,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    const auth = getStoredAuth();
    if (auth?.token) headers["Authorization"] = `Bearer ${auth.token}`;
  }

  // Use XHR (not fetch) when onProgress is provided so we can observe upload progress.
  if (onProgress) {
    return await new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}${path}`);
      Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded, event.total);
      };
      xhr.onload = () => {
        try {
          resolve(
            parseApiResponse<T>(
              xhr.status,
              xhr.getResponseHeader("content-type") || "",
              xhr.responseText,
            ),
          );
        } catch (err) {
          reject(err instanceof Error ? err : new Error("Failed to parse response"));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(formData);
    });
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  const raw = await res.text();
  return parseApiResponse<T>(res.status, res.headers.get("content-type") || "", raw);
}
