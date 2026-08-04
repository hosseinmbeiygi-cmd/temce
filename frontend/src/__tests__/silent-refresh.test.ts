import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Mock Response Builder ──────────────────────────────────────
function mockFetchResponse(overrides: Partial<Response> = {}): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    redirected: false,
    type: "basic" as const,
    url: "",
    clone: () => mockFetchResponse(overrides),
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    bytes: () => Promise.resolve(new Uint8Array(0)),
    formData: () => Promise.resolve(new FormData()),
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(""),
    ...overrides,
  } as Response;
}

// ── localStorage Mock ──────────────────────────────────────────
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
    _reset() { store = {}; },
  };
})();

// ── Tests ──────────────────────────────────────────────────────
describe("Silent Token Refresh", () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    vi.resetModules();
    localStorageMock._reset();
    Object.defineProperty(globalThis, "localStorage", { value: localStorageMock, writable: true });
    Object.defineProperty(globalThis, "window", {
      value: {
        location: { pathname: "/", href: "" },
      },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    // Restore window for SSR test
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      writable: true,
      configurable: true,
    });
  });

  // ── Helper: import api functions with fresh module ────────────
  async function importApi() {
    const mod = await import("@/lib/api");
    return {
      apiGet: mod.apiGet,
      apiPost: mod.apiPost,
      apiPut: mod.apiPut,
      apiDelete: mod.apiDelete,
      clearAuth: mod.clearAuth,
      storeAuth: mod.storeAuth,
    };
  }

  // ══════════════════════════════════════════════════════════════
  // 1. Successful Token Refresh
  // ══════════════════════════════════════════════════════════════
  describe("Successful Refresh", () => {
    it("retries the original request with new token after successful refresh", async () => {
      const { apiGet } = await importApi();

      // Store auth with expired access token and a refresh token
      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-access-token",
        refresh_token: "valid-refresh-token",
      }));

      const fetchMock = vi.fn()
        // First call: original request → 401
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        // Second call: refresh → 200 with new tokens
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: {
              access_token: "new-access-token",
              refresh_token: "new-refresh-token",
            },
          }),
        }))
        // Third call: retry original request → 200
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: { symbol: "test" } }),
        }));

      globalThis.fetch = fetchMock;

      const result = await apiGet("/signals");

      expect(result).toEqual({ data: { symbol: "test" } });
      expect(fetchMock).toHaveBeenCalledTimes(3);

      // Verify the retry used the new token
      const retryCall = fetchMock.mock.calls[2];
      expect(retryCall[1].headers).toMatchObject({
        Authorization: "Bearer new-access-token",
      });

      // Verify localStorage was updated with new tokens
      const stored = JSON.parse(localStorageMock.getItem("auth") as string);
      expect(stored.access_token).toBe("new-access-token");
      expect(stored.refresh_token).toBe("new-refresh-token");
    });

    it("keeps old refresh_token when server doesn't return a new one", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-token",
        refresh_token: "old-refresh-token",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: { access_token: "new-token" }, // no refresh_token
          }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: {} }),
        }));

      globalThis.fetch = fetchMock;

      await apiGet("/test");

      const stored = JSON.parse(localStorageMock.getItem("auth") as string);
      expect(stored.access_token).toBe("new-token");
      expect(stored.refresh_token).toBe("old-refresh-token"); // preserved
    });
  });

  // ══════════════════════════════════════════════════════════════
  // 2. Failed Token Refresh
  // ══════════════════════════════════════════════════════════════
  describe("Failed Refresh", () => {
    it("redirects to login when refresh endpoint returns non-200", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-token",
        refresh_token: "invalid-refresh-token",
      }));

      const fetchMock = vi.fn()
        // First call: 401
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        // Refresh: 401
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      // apiGet throws HTTP 401 after _handle401 runs
      await expect(apiGet("/signals")).rejects.toThrow("HTTP 401");

      // localStorage should be cleared
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("auth");
      // Should redirect to login with redirect param
      expect(window.location.href).toContain("/auth/login?redirect=");
    });

    it("redirects to login when refresh throws a network error", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-token",
        refresh_token: "some-refresh-token",
      }));

      const fetchMock = vi.fn()
        // First call: 401
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        // Refresh: network error
        .mockRejectedValueOnce(new TypeError("Failed to fetch"));

      globalThis.fetch = fetchMock;

      await expect(apiGet("/signals")).rejects.toThrow("HTTP 401");

      expect(localStorageMock.removeItem).toHaveBeenCalledWith("auth");
      expect(window.location.href).toContain("/auth/login");
    });

    it("redirects to login when no refresh_token exists in storage", async () => {
      const { apiGet } = await importApi();

      // No auth stored at all
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      await expect(apiGet("/signals")).rejects.toThrow("HTTP 401");

      expect(localStorageMock.removeItem).toHaveBeenCalledWith("auth");
      expect(window.location.href).toContain("/auth/login");
    });
  });

  // ══════════════════════════════════════════════════════════════
  // 3. Deduplication of Concurrent Requests
  // ══════════════════════════════════════════════════════════════
  describe("Deduplication", () => {
    it("only sends one refresh request for multiple concurrent 401s", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-token",
        refresh_token: "valid-refresh-token",
      }));

      // Build fetch mock: multiple 401s then one refresh, then success for retries
      const fetchMock = vi.fn()
        // 3 concurrent requests all get 401
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        // Only ONE refresh call
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: { access_token: "refreshed-token", refresh_token: "new-refresh" },
          }),
        }))
        // Retries succeed
        .mockResolvedValue(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: { ok: true } }),
        }));

      globalThis.fetch = fetchMock;

      // Fire 3 concurrent requests
      const [r1, r2, r3] = await Promise.all([
        apiGet("/signals"),
        apiGet("/portfolios"),
        apiGet("/alerts"),
      ]);

      expect(r1).toEqual({ data: { ok: true } });
      expect(r2).toEqual({ data: { ok: true } });
      expect(r3).toEqual({ data: { ok: true } });

      // 3 original requests + 1 refresh + 3 retries = 7 total
      // But dedup means only 1 refresh regardless of timing
      const refreshCalls = fetchMock.mock.calls.filter(
        (call: string[]) => call[0].includes("/auth/refresh")
      );
      expect(refreshCalls).toHaveLength(1);
    });

    it("resets the refresh promise after completion", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired-token",
        refresh_token: "valid-refresh-token",
      }));

      const fetchMock = vi.fn()
        // First request: 401 → refresh → retry
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: { access_token: "token-1", refresh_token: "refresh-1" },
          }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: { ok: true } }),
        }))
        // Second request: 401 → NEW refresh → retry
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            data: { access_token: "token-2", refresh_token: "refresh-2" },
          }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ data: { ok: true } }),
        }));

      globalThis.fetch = fetchMock;

      // First request
      await apiGet("/signals");
      // Second request (after first completes)
      await apiGet("/portfolios");

      // Should have 2 separate refresh calls (not deduplicated across time)
      const refreshCalls = fetchMock.mock.calls.filter(
        (call: string[]) => call[0].includes("/auth/refresh")
      );
      expect(refreshCalls).toHaveLength(2);
    });
  });

  // ══════════════════════════════════════════════════════════════
  // 4. Skip Refresh for /auth/ Endpoints
  // ══════════════════════════════════════════════════════════════
  describe("Skip Refresh for /auth/ Endpoints", () => {
    it("does NOT attempt refresh for /auth/login", async () => {
      const { apiPost } = await importApi();

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      await expect(apiPost("/auth/login", { username: "test", password: "test" })).rejects.toThrow("HTTP 401");

      // No refresh call should be made
      const refreshCalls = fetchMock.mock.calls.filter(
        (call: string[]) => call[0].includes("/auth/refresh")
      );
      expect(refreshCalls).toHaveLength(0);

      // Should still redirect to login
      expect(window.location.href).toContain("/auth/login");
    });

    it("does NOT attempt refresh for /auth/register", async () => {
      const { apiPost } = await importApi();

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      await expect(apiPost("/auth/register", { username: "test", password: "test" })).rejects.toThrow("HTTP 401");

      const refreshCalls = fetchMock.mock.calls.filter(
        (call: string[]) => call[0].includes("/auth/refresh")
      );
      expect(refreshCalls).toHaveLength(0);
    });
  });

  // ══════════════════════════════════════════════════════════════
  // 5. API Methods Coverage
  // ══════════════════════════════════════════════════════════════
  describe("All API Methods Handle 401", () => {
    it("apiPost retries after refresh", async () => {
      const { apiPost } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired",
        refresh_token: "valid",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ data: { access_token: "new", refresh_token: "new" } }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ result: "created" }),
        }))
        .mockResolvedValue(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ result: "created" }),
        }));

      globalThis.fetch = fetchMock;

      const result = await apiPost("/backtests/run", { strategy: "test" });
      expect(result).toEqual({ result: "created" });
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it("apiPut retries after refresh", async () => {
      const { apiPut } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired",
        refresh_token: "valid",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ data: { access_token: "new", refresh_token: "new" } }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ updated: true }),
        }))
        .mockResolvedValue(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ updated: true }),
        }));

      globalThis.fetch = fetchMock;

      // Use /portfolios (not /auth/*) so refresh is attempted
      const result = await apiPut("/portfolios", { name: "Test" });
      expect(result).toEqual({ updated: true });
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it("apiDelete retries after refresh", async () => {
      const { apiDelete } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired",
        refresh_token: "valid",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ data: { access_token: "new", refresh_token: "new" } }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ deleted: true }),
        }));

      globalThis.fetch = fetchMock;

      const result = await apiDelete("/alerts/test-alert-id");
      expect(result).toEqual({ deleted: true });
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });
  });

  // ══════════════════════════════════════════════════════════════
  // 6. Edge Cases
  // ══════════════════════════════════════════════════════════════
  describe("Edge Cases", () => {
    it("does not redirect when already on /auth/ page and refresh fails", async () => {
      const { apiGet } = await importApi();

      // Already on login page
      const mockLocation = { pathname: "/auth/login", href: "/auth/login" };
      Object.defineProperty(globalThis, "window", {
        value: { location: mockLocation },
        writable: true,
        configurable: true,
      });

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired",
        refresh_token: "invalid",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValue(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      // apiGet will throw HTTP 401 after _handle401 runs — that's expected
      await expect(apiGet("/signals")).rejects.toThrow("HTTP 401");

      // Should NOT redirect (already on auth page) — href stays as-is
      expect(mockLocation.href).toBe("/auth/login");
    });

    it("handles malformed localStorage gracefully", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", "not-valid-json");

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValue(mockFetchResponse({ ok: false, status: 401 }));

      globalThis.fetch = fetchMock;

      // Should throw HTTP error (no refresh attempted)
      await expect(apiGet("/signals")).rejects.toThrow("HTTP 401");

      // No refresh attempted (no valid refresh_token)
      const refreshCalls = fetchMock.mock.calls.filter(
        (call: string[]) => call[0].includes("/auth/refresh")
      );
      expect(refreshCalls).toHaveLength(0);
    });

    it("sends correct Content-Type header in refresh request", async () => {
      const { apiGet } = await importApi();

      localStorageMock.setItem("auth", JSON.stringify({
        access_token: "expired",
        refresh_token: "valid-refresh",
      }));

      const fetchMock = vi.fn()
        .mockResolvedValueOnce(mockFetchResponse({ ok: false, status: 401 }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ data: { access_token: "new", refresh_token: "new" } }),
        }))
        .mockResolvedValueOnce(mockFetchResponse({
          ok: true, status: 200,
          json: () => Promise.resolve({ data: {} }),
        }));

      globalThis.fetch = fetchMock;

      await apiGet("/test");

      const refreshCall = fetchMock.mock.calls[1];
      expect(refreshCall[0]).toContain("/auth/refresh");
      expect(refreshCall[1].method).toBe("POST");
      expect(refreshCall[1].headers).toMatchObject({
        "Content-Type": "application/json",
      });
      expect(refreshCall[1].body).toContain("valid-refresh");
    });

    it("works when window is undefined (SSR)", async () => {
      // In SSR, localStorage and window are undefined
      Object.defineProperty(globalThis, "window", { value: undefined, writable: true, configurable: true });

      // Mock fetch to return a successful response (no 401)
      globalThis.fetch = vi.fn().mockResolvedValue(mockFetchResponse({
        ok: true, status: 200,
        json: () => Promise.resolve({ ssr: true }),
      }));

      const mod = await import("@/lib/api");
      const result = await mod.apiGet("/test");

      // Should return the JSON response (fetch still works in SSR mock)
      expect(result).toEqual({ ssr: true });
    });
  });
});
