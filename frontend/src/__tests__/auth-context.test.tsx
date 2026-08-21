import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";

// ── Auth is stored in-memory + httpOnly cookie now (XSS-safe) ────
// The AuthProvider restores the session by calling hydrateSession(), which
// exchanges the httpOnly refresh cookie for a fresh access token + user.
// We mock @/lib/api so each test controls what hydration returns, and use
// vi.resetModules() so every test gets a fresh in-memory store (no leakage).

type MemAuth = {
  access_token: string | null;
  user?: Record<string, unknown> | null;
} | null;

// Hoisted so tests can reset the mocked api store between runs (the vi.mock
// factory closure is NOT re-executed by vi.resetModules()).
const { hydrateSessionMock, authStoreMock } = vi.hoisted(() => {
  let mem: MemAuth = null;
  return {
    hydrateSessionMock: vi.fn(),
    authStoreMock: {
      get: () => (mem?.access_token ? mem : null),
      set: (data: {
        user: Record<string, unknown>;
        access_token: string;
      }) => {
        mem = {
          access_token: data.access_token,
          user: data.user,
        };
      },
      clear: () => {
        mem = null;
      },
      reset: () => {
        mem = null;
      },
    },
  };
});

// In-memory stand-in for api.ts's shared auth store — lets us verify the
// context and the api layer observe the same session without real storage.
vi.mock("@/lib/api", () => ({
  hydrateSession: (...args: unknown[]) => hydrateSessionMock(...args),
  getStoredAuth: () => authStoreMock.get(),
  storeAuth: (data: Parameters<typeof authStoreMock.set>[0]) => authStoreMock.set(data),
  clearAuth: () => authStoreMock.clear(),
}));

const ORIGINAL_FETCH = globalThis.fetch;

// Fresh module per test (clears the module-level in-memory auth store).
async function loadAuth() {
  const mod = await import("@/lib/auth-context");
  return mod;
}

function wrapperFor(Provider: (p: { children: ReactNode }) => ReactNode) {
  return function wrapper({ children }: { children: ReactNode }) {
    return <Provider>{children}</Provider>;
  };
}

const AUTHED_SESSION = {
  access_token: "access-token-1",
  user: { id: "u1", username: "testuser", roles: ["user"] },
};

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.resetModules();
    hydrateSessionMock.mockReset();
    authStoreMock.reset();
    // Default: no active session → hydration returns nothing.
    hydrateSessionMock.mockResolvedValue({ access_token: null });
    localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
    vi.restoreAllMocks();
  });

  describe("hydration from the httpOnly refresh cookie", () => {
    it("restores the session (user + tokens) when hydration succeeds", async () => {
      hydrateSessionMock.mockResolvedValue(AUTHED_SESSION);

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.username).toBe("testuser");
      expect(result.current.accessToken).toBe("access-token-1");
    });

    it("starts unauthenticated when hydration finds no valid cookie", async () => {
      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
    });

    it("stays logged out when hydration throws", async () => {
      hydrateSessionMock.mockRejectedValue(new Error("network down"));

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe("login", () => {
    it("sets user/tokens, never writes them to localStorage, and uses credentials include", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          data: {
            user: { id: "u9", username: "ali", roles: ["analyst"] },
            access_token: "new-access",
          },
        }),
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.login("ali", "secret");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.username).toBe("ali");
      expect(result.current.accessToken).toBe("new-access");

      // The request must carry credentials so the httpOnly refresh cookie is set.
      const loginCall = fetchMock.mock.calls[0];
      expect(loginCall[0]).toContain("/auth/login");
      expect(loginCall[1].credentials).toBe("include");

      // Nothing sensitive in localStorage (XSS-safe).
      expect(localStorage.getItem("auth")).toBeNull();
      expect(localStorage.length).toBe(0);
    });

    it("throws when login fails and keeps user logged out", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: async () => "invalid credentials",
      }) as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      let loginError: unknown;
      await act(async () => {
        try {
          await result.current.login("ali", "wrong");
        } catch (e) {
          loginError = e;
        }
      });

      expect(loginError).toBeInstanceOf(Error);
      expect((loginError as Error).message).toContain("invalid credentials");
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe("logout", () => {
    it("clears state and invalidates the server session after a hydrated session", async () => {
      hydrateSessionMock.mockResolvedValue(AUTHED_SESSION);
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/auth/logout"),
        expect.objectContaining({
          method: "POST",
          credentials: "include",
          headers: { Authorization: "Bearer access-token-1" },
        }),
      );
    });

    it("keeps the local session cleared when the server logout fails", async () => {
      hydrateSessionMock.mockResolvedValue(AUTHED_SESSION);
      globalThis.fetch = vi.fn().mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.accessToken).toBeNull();
    });
  });

  describe("role helpers", () => {
    it("hasRole returns true when the user has the role", async () => {
      hydrateSessionMock.mockResolvedValue({
        ...AUTHED_SESSION,
        user: { id: "u2", username: "x", roles: ["analyst"] },
      });

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasRole("analyst")).toBe(true);
      expect(result.current.hasRole("admin")).toBe(false);
    });

    it("admin is allowed through every role check", async () => {
      hydrateSessionMock.mockResolvedValue({
        ...AUTHED_SESSION,
        user: { id: "u3", username: "root", roles: ["admin"] },
      });

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasRole("admin")).toBe(true);
      expect(result.current.hasRole("user")).toBe(true);
      expect(result.current.hasAnyRole("analyst", "user")).toBe(true);
    });

    it("hasAnyRole matches any of the requested roles", async () => {
      hydrateSessionMock.mockResolvedValue({
        ...AUTHED_SESSION,
        user: { id: "u4", username: "x", roles: ["viewer"] },
      });

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasAnyRole("analyst", "viewer")).toBe(true);
      expect(result.current.hasAnyRole("admin", "analyst")).toBe(false);
    });
  });

  describe("refreshAccessToken", () => {
    it("returns null and logs out when the refresh endpoint rejects", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
      }) as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      let token: string | null = null;
      await act(async () => {
        token = await result.current.refreshAccessToken();
      });
      expect(token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it("calls /auth/refresh with credentials include and updates the access token", async () => {
      hydrateSessionMock.mockResolvedValue(AUTHED_SESSION);

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          data: { access_token: "rotated-access", user: AUTHED_SESSION.user },
        }),
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { AuthProvider, useAuth } = await loadAuth();
      const { result } = renderHook(() => useAuth(), { wrapper: wrapperFor(AuthProvider) });
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      let token: string | null = null;
      await act(async () => {
        token = await result.current.refreshAccessToken();
      });
      expect(token).toBe("rotated-access");
      expect(result.current.accessToken).toBe("rotated-access");

      const refreshCall = fetchMock.mock.calls[0];
      expect(refreshCall[0]).toContain("/auth/refresh");
      expect(refreshCall[1].credentials).toBe("include");
      // Cookie-only contract: the body must not carry the refresh token.
      expect(JSON.stringify(refreshCall[1].body)).not.toContain("refresh_token");
    });
  });
});
