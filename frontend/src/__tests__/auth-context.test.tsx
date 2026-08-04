import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const ORIGINAL_FETCH = globalThis.fetch;
import { type ReactNode } from "react";
import { AuthProvider, useAuth } from "@/lib/auth-context";

// ── Wrapper ─────────────────────────────────────────────────────
function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

// ── localStorage helpers ────────────────────────────────────────
const AUTH_KEY = "auth";

function seedAuth(overrides: Record<string, unknown> = {}) {
  const stored = {
    user: { username: "testuser", roles: ["user"], id: "u1" },
    access_token: "access-token-1",
    refresh_token: "refresh-token-1",
    ...overrides,
  };
  localStorage.setItem(AUTH_KEY, JSON.stringify(stored));
}

// ── Tests ───────────────────────────────────────────────────────
describe("AuthProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    // Direct assignments aren't covered by vi.restoreAllMocks() — restore manually.
    globalThis.fetch = ORIGINAL_FETCH;
  });

  describe("hydration from localStorage", () => {
    it("hydrates isAuthenticated=true and user when auth is stored", async () => {
      seedAuth();

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.username).toBe("testuser");
      expect(result.current.accessToken).toBe("access-token-1");
      expect(result.current.refreshToken).toBe("refresh-token-1");
    });

    it("starts unauthenticated (isLoading=false) when nothing is stored", async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
    });

    it("handles malformed JSON in localStorage without crashing", async () => {
      localStorage.setItem(AUTH_KEY, "not-valid-json{{{");

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe("login", () => {
    it("stores tokens and sets user on successful login", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          data: {
            user: { username: "ali", roles: ["analyst"] },
            access_token: "new-access",
            refresh_token: "new-refresh",
          },
        }),
      }) as unknown as typeof fetch;

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.login("ali", "secret");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.username).toBe("ali");
      expect(result.current.accessToken).toBe("new-access");

      const stored = JSON.parse(localStorage.getItem(AUTH_KEY) as string);
      expect(stored.access_token).toBe("new-access");
      expect(stored.refresh_token).toBe("new-refresh");
    });

    it("throws when login fails and keeps user logged out", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: async () => "invalid credentials",
      }) as unknown as typeof fetch;

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      // Capture the rejection inside act() — more robust than expecting act's
      // promise to reject (which can be flaky across React versions).
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
    it("clears state and localStorage", async () => {
      seedAuth();

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

      act(() => {
        result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(localStorage.getItem(AUTH_KEY)).toBeNull();
    });
  });

  describe("role helpers", () => {
    it("hasRole returns true when the user has the role", async () => {
      seedAuth({ user: { username: "x", roles: ["analyst"], id: "u2" } });

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasRole("analyst")).toBe(true);
      expect(result.current.hasRole("admin")).toBe(false);
    });

    it("admin is allowed through every role check", async () => {
      seedAuth({ user: { username: "root", roles: ["admin"], id: "u3" } });

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasRole("admin")).toBe(true);
      expect(result.current.hasRole("user")).toBe(true);
      expect(result.current.hasAnyRole("analyst", "user")).toBe(true);
    });

    it("hasAnyRole matches any of the requested roles", async () => {
      seedAuth({ user: { username: "x", roles: ["viewer"], id: "u4" } });

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.hasAnyRole("analyst", "viewer")).toBe(true);
      expect(result.current.hasAnyRole("admin", "analyst")).toBe(false);
    });
  });

  describe("refreshAccessToken", () => {
    it("returns null when no refresh token is stored", async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      const token = await result.current.refreshAccessToken();
      expect(token).toBeNull();
    });
  });
});
