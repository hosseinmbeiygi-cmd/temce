const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function apiPost<T>(path: string, body: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  const json = await res.json();
  if (!json.success) throw new Error(json.error?.message || json.error || "Request failed");
  return json.data as T;
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  const json = await res.json();
  if (!json.success) throw new Error(json.error?.message || json.error || "Request failed");
  return json.data as T;
}

export async function apiPut<T>(path: string, body: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: "PUT", headers, body: JSON.stringify(body) });
  const json = await res.json();
  if (!json.success) throw new Error(json.error?.message || json.error || "Request failed");
  return json.data as T;
}

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

export async function apiDelete<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers });
  const json = await res.json();
  if (!json.success) throw new Error(json.error?.message || json.error || "Request failed");
  return json.data as T;
}

export function clearAuth() {
  localStorage.removeItem("auth");
}
