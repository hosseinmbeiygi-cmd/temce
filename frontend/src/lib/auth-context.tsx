"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// ── Types ───────────────────────────────────────────────────────

export interface AuthUser {
  id?: string;
  username?: string;
  email?: string;
  full_name?: string;
  roles?: string[];
  [key: string]: unknown;
}

export interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (data: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<string | null>;
  hasRole: (role: string) => boolean;
  hasAnyRole: (...roles: string[]) => boolean;
}

// ── Storage helpers ─────────────────────────────────────────────

const AUTH_STORAGE_KEY = "auth";

interface StoredAuth {
  user: AuthUser;
  access_token: string;
  refresh_token?: string;
}

function readStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

function writeStoredAuth(data: StoredAuth): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(data));
}

function clearStoredAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

// ── Context ─────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true, // starts true until we check localStorage
  });

  // Hydrate from localStorage on mount.
  // Client-only, one-time sync from an external store (localStorage) — this is the
  // documented pattern for localStorage hydration; it cannot be derived during render.
  useEffect(() => {
    const stored = readStoredAuth();
    if (stored) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({
        user: stored.user,
        accessToken: stored.access_token,
        refreshToken: stored.refresh_token ?? null,
        isAuthenticated: true,
        isLoading: false,
      });
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  // ── login ───────────────────────────────────────────────────

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Login failed (${res.status})`);
    }

    const json = await res.json();
    const data = json.data ?? json;

    const newState: AuthState = {
      user: data.user ?? data,
      accessToken: data.access_token,
      refreshToken: data.refresh_token ?? null,
      isAuthenticated: true,
      isLoading: false,
    };

    writeStoredAuth({
      user: newState.user!,
      access_token: newState.accessToken!,
      refresh_token: newState.refreshToken ?? undefined,
    });

    setState(newState);
  }, []);

  // ── register ────────────────────────────────────────────────

  const register = useCallback(
    async (data: {
      username: string;
      email: string;
      password: string;
      full_name?: string;
    }) => {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Registration failed (${res.status})`);
      }

      const json = await res.json();
      const payload = json.data ?? json;

      const newState: AuthState = {
        user: payload.user ?? payload,
        accessToken: payload.access_token,
        refreshToken: payload.refresh_token ?? null,
        isAuthenticated: true,
        isLoading: false,
      };

      writeStoredAuth({
        user: newState.user!,
        access_token: newState.accessToken!,
        refresh_token: newState.refreshToken ?? undefined,
      });

      setState(newState);
    },
    [],
  );

  // ── logout ──────────────────────────────────────────────────

  const logout = useCallback(() => {
    clearStoredAuth();
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  // ── refresh token ───────────────────────────────────────────

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    const stored = readStoredAuth();
    if (!stored?.refresh_token) return null;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: stored.refresh_token }),
      });

      if (!res.ok) {
        // Refresh failed — force logout
        logout();
        return null;
      }

      const json = await res.json();
      const data = json.data ?? json;

      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token ?? stored.refresh_token;

      writeStoredAuth({
        user: stored.user,
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
      });

      setState((prev) => ({
        ...prev,
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
      }));

      return newAccessToken;
    } catch {
      logout();
      return null;
    }
  }, [logout]);

  // ── role helpers ───────────────────────────────────────────

  const ROLE_HIERARCHY = ["admin", "analyst", "user", "viewer"];

  const hasRole = useCallback((role: string): boolean => {
    const roles = state.user?.roles ?? [];
    if (roles.includes("admin")) return true;
    const userTopIdx = Math.min(
      ...roles.map((r) => { const i = ROLE_HIERARCHY.indexOf(r); return i >= 0 ? i : ROLE_HIERARCHY.length; })
    );
    const reqIdx = ROLE_HIERARCHY.indexOf(role);
    return reqIdx >= 0 && userTopIdx <= reqIdx;
  }, [state.user]);

  const hasAnyRole = useCallback((...roles: string[]): boolean => {
    const userRoles = state.user?.roles ?? [];
    if (userRoles.includes("admin")) return true;
    return roles.some((r) => userRoles.includes(r));
  }, [state.user]);

  // ── value ───────────────────────────────────────────────────

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      register,
      logout,
      refreshAccessToken,
      hasRole,
      hasAnyRole,
    }),
    [state, login, register, logout, refreshAccessToken, hasRole, hasAnyRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
