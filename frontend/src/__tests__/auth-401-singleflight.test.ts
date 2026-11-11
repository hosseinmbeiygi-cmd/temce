// FE-13 — چند 401 هم‌زمان نباید چند logout و چند redirect بسازند.
//
// قبلاً هر درخواست شکست‌خورده `_handle401()` خودش را اجرا می‌کرد: یک POST
// /auth/logout جداگانه و یک تغییر جداگانه window.location برای هر پاسخ 401.

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

function response(overrides: Partial<Response> = {}): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    redirected: false,
    type: "basic" as const,
    url: "",
    clone: () => response(overrides),
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

const ORIGINAL_WINDOW = globalThis.window;
let redirects: string[] = [];

beforeEach(() => {
  vi.resetModules();
  redirects = [];
  const location: { pathname: string; href: string } = { pathname: "/dashboard", href: "" };
  Object.defineProperty(location, "href", {
    configurable: true,
    get: () => redirects[redirects.length - 1] ?? "",
    set: (value: string) => {
      redirects.push(value);
    },
  });
  Object.defineProperty(globalThis, "window", {
    value: { location, dispatchEvent: vi.fn() },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(globalThis, "window", {
    value: ORIGINAL_WINDOW,
    writable: true,
    configurable: true,
  });
});

function installExpiredSessionFetch() {
  const calls = { refresh: 0, logout: 0 };
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const href = String(url);
    if (href.includes("/auth/refresh")) {
      calls.refresh += 1;
      return response({ ok: false, status: 401 });
    }
    if (href.includes("/auth/logout")) {
      calls.logout += 1;
      return response({ ok: true, status: 200 });
    }
    return response({ ok: false, status: 401 });
  });
  return calls;
}

async function importApi() {
  const api = await import("@/lib/api");
  api.storeAuth({ user: { username: "t" }, access_token: "expired-token" });
  return api;
}

describe("401 handling — single flight", () => {
  it("fires one logout and one redirect for three concurrent 401s", async () => {
    const api = await importApi();
    const calls = installExpiredSessionFetch();

    const results = await Promise.allSettled([
      api.apiGet("/signals"),
      api.apiGet("/portfolios"),
      api.apiGet("/alerts"),
    ]);

    expect(results.map((r) => r.status)).toEqual(["rejected", "rejected", "rejected"]);
    for (const result of results) {
      if (result.status === "rejected") {
        expect((result.reason as { name?: string }).name).toBe("UnauthorizedError");
      }
    }

    expect(calls.refresh).toBe(1);
    expect(calls.logout).toBe(1);
    expect(redirects).toHaveLength(1);
    expect(redirects[0]).toContain("/auth/login?redirect=");
    expect(redirects[0]).toContain("reason=session_expired");
  });

  it("re-arms the guard after a fresh login", async () => {
    const api = await importApi();
    installExpiredSessionFetch();

    await expect(api.apiGet("/signals")).rejects.toMatchObject({ name: "UnauthorizedError" });
    expect(redirects).toHaveLength(1);

    // A successful login (new access token) must allow a later expiry to
    // terminate the session again instead of silently doing nothing.
    api.storeAuth({ user: { username: "t" }, access_token: "fresh-token" });
    installExpiredSessionFetch();
    await expect(api.apiGet("/portfolios")).rejects.toMatchObject({ name: "UnauthorizedError" });

    expect(redirects).toHaveLength(2);
  });
});
