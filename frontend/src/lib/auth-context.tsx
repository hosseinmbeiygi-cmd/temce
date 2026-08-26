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
import { clearAuth, getStoredAuth, hydrateSession, storeAuth } from "@/lib/api";

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
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
  hasRole: (role: string) => boolean;
  hasAnyRole: (...roles: string[]) => boolean;
}

// ── Auth storage: in-memory only (XSS-safe) ─────────────────────
// Single source of truth lives in @/lib/api (module memory) so every
// component reading getStoredAuth() sees the same session as the context.
// The refresh token is an httpOnly cookie set by the backend; the access
// token + user are restored after a reload via hydrateSession(), which
// exchanges the cookie for a fresh session. Nothing sensitive is ever
// written to localStorage.

// ── Context ─────────────────────────────────────────────────────

const ROLE_HIERARCHY: string[] = ["admin", "analyst", "user", "viewer"];

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Hydrate the session on mount: the access token is in-memory only, so
  // after a page reload we must exchange the httpOnly refresh cookie for a
  // fresh access token (and user profile) before considering the user logged in.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = getStoredAuth();
      if (stored?.access_token) {
        setState({
          user: (stored.user as AuthUser | undefined) ?? null,
          accessToken: stored.access_token,
          isAuthenticated: true,
          isLoading: false,
        });
        return;
      }
      try {
        const restored = await hydrateSession();
        if (cancelled) return;
        if (restored?.access_token) {
          storeAuth({
            user: (restored.user as AuthUser) ?? {},
            access_token: restored.access_token,
          });
          setState({
            user: (restored.user as AuthUser) ?? {},
            accessToken: restored.access_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } else {
          setState((prev) => ({ ...prev, isLoading: false }));
        }
      } catch {
        if (!cancelled) {
          setState((prev) => ({ ...prev, isLoading: false }));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── login ───────────────────────────────────────────────────

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      credentials: "include",
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Login failed (${res.status})`);
    }

    const json = await res.json();
    const data = json.data ?? json;

    if (data?.mfa_required) {
      throw new Error(
        JSON.stringify({
          mfa_required: true,
          mfa_token: data.mfa_token,
          method: data.method ?? 'totp',
          user: data.user,
        })
      );
    }

    if (!data?.access_token) {
      throw new Error('Login failed: missing access token');
    }

    const newState: AuthState = {
      user: data.user ?? data,
      accessToken: data.access_token,
      isAuthenticated: true,
      isLoading: false,
    };

    storeAuth({
      user: newState.user!,
      access_token: newState.accessToken!,
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
        credentials: "include",
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
        isAuthenticated: true,
        isLoading: false,
      };

      storeAuth({
        user: newState.user!,
        access_token: newState.accessToken!,
      });

      setState(newState);
    },
    [],
  );

  // ── logout ──────────────────────────────────────────────────

  const logout = useCallback(async () => {
    // Capture the access token before clearing the local session. The server
    // also invalidates the httpOnly refresh cookie, which local JavaScript
    // cannot remove itself.
    const accessToken = getStoredAuth()?.access_token ?? null;
    clearAuth();
    setState({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
    });

    // Local logout must not depend on network availability. The backend
    // operation is best-effort, while its endpoint always expires the cookie.
    try {
      const headers: HeadersInit = {};
      if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        headers,
        credentials: "include",
      });
    } catch {
      // The local state is already cleared; a failed request must not keep the
      // user stuck in the authenticated UI.
    }
  }, []);

  // ── refresh token ───────────────────────────────────────────

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    // The refresh token is an httpOnly cookie — the server reads it, so there
    // is nothing to send in the body and nothing to check in memory.
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });

      if (!res.ok) {
        // Refresh failed — force logout
        logout();
        return null;
      }

      const json = await res.json();
      const data = json.data ?? json;
      const newAccessToken = data.access_token;
      if (!newAccessToken) {
        logout();
        return null;
      }

      const freshUser = (data.user as AuthUser | undefined) ?? (getStoredAuth()?.user as AuthUser | undefined) ?? {};
      storeAuth({
        user: freshUser,
        access_token: newAccessToken,
      });

      setState((prev) => ({ ...prev, accessToken: newAccessToken, user: freshUser }));
      return newAccessToken;
    } catch {
      logout();
      return null;
    }
  }, [logout]);

  // ── role helpers ───────────────────────────────────────────

  const hasRole = useCallback((role: string): boolean => {
    const roles = state.user?.roles ?? [];
    if (roles.length === 0) return false;
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
