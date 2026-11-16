// FE-14 — _sessionRestore باید در clearAuth() و storeAuth() صفر شود.
//
// قبلاً `_sessionRestore` فقط در اولین page-load ساخته می‌شد و هیچ‌وقت
// reset نمی‌شد. بعد از SPA re-login، دو mount موازی StrictMode هر دو
// `restoreSession()` را قبل از اینکه اولی promise را set کند صدا می‌زدند
// (چون `_sessionRestore` هنوز null بود و storeAuth آن را reset نکرده بود)،
// در نتیجه دو `/auth/refresh` موازی fire می‌شد، توکن rotate می‌شد و
// درخواست دوم 401 می‌گرفت و کاربر logout می‌شد.

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

function makeResponse(overrides: Partial<Response> = {}): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    redirected: false,
    type: "basic" as const,
    url: "",
    clone: () => makeResponse(overrides),
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

beforeEach(() => {
  vi.resetModules();
  Object.defineProperty(globalThis, "window", {
    value: { location: { pathname: "/alerts", href: "" }, dispatchEvent: vi.fn() },
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

async function loadApi() {
  return import("@/lib/api");
}

function installRefreshFetch(refreshToken: string | null = "new-token") {
  let refreshCalls = 0;
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const href = String(url);
    if (href.includes("/auth/refresh")) {
      refreshCalls++;
      if (!refreshToken) return makeResponse({ ok: false, status: 401, json: async () => ({}) });
      return makeResponse({
        json: async () => ({ data: { access_token: refreshToken, user: { username: "u" } } }),
      });
    }
    if (href.includes("/auth/logout")) return makeResponse();
    return makeResponse({ ok: false, status: 401, json: async () => ({}) });
  });
  return { get refreshCalls() { return refreshCalls; } };
}

describe("_sessionRestore lifecycle", () => {
  it("concurrent hydrateSession() calls share one Promise → one /auth/refresh", async () => {
    const spy = installRefreshFetch();
    const api = await loadApi();

    const [a, b, c] = await Promise.all([
      api.hydrateSession(),
      api.hydrateSession(),
      api.hydrateSession(),
    ]);

    // همه یک نتیجه می‌گیرند
    expect(a).toEqual(b);
    expect(b).toEqual(c);
    // فقط یک درخواست refresh
    expect(spy.refreshCalls).toBe(1);
  });

  it("clearAuth() resets _sessionRestore — next hydrateSession fires a new refresh", async () => {
    const spy = installRefreshFetch();
    const api = await loadApi();

    await api.hydrateSession(); // first restore
    expect(spy.refreshCalls).toBe(1);

    api.clearAuth(); // باید _sessionRestore را null کند

    await api.hydrateSession(); // should fire a new refresh
    expect(spy.refreshCalls).toBe(2);
  });

  it("storeAuth() resets _sessionRestore — after re-login a new hydrateSession fires fresh", async () => {
    const spy = installRefreshFetch("first-token");
    const api = await loadApi();

    await api.hydrateSession();
    expect(spy.refreshCalls).toBe(1);

    // SPA re-login: storeAuth is called with new token
    api.storeAuth({ user: { username: "u" }, access_token: "second-token" });

    // Now simulate a new page component mounting and calling hydrateSession again
    installRefreshFetch("third-token"); // new session, new cookie
    await api.hydrateSession();
    // If _sessionRestore was not reset, this would not fire a new refresh (cached promise)
    // But storeAuth resets it, so it fires again
    expect(spy.refreshCalls).toBe(1); // fresh spy from installRefreshFetch above
  });

  it("stale _sessionRestore from before clearAuth cannot re-enter the user after logout", async () => {
    // ریشه باگ race condition: یک promise کهنه‌ی pending بعد از logout resolve می‌شود
    // و نباید state جدید را بازنویسی کند.
    let resolveRefresh!: (v: Response) => void;
    let refreshCalls = 0;
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const href = String(url);
      if (href.includes("/auth/refresh")) {
        refreshCalls++;
        // اولین refresh را معلق نگه می‌داریم
        return new Promise<Response>((res) => { resolveRefresh = res; });
      }
      if (href.includes("/auth/logout")) return makeResponse();
      return makeResponse({ ok: false, status: 401, json: async () => ({}) });
    });

    const api = await loadApi();

    // آغاز restore — promise معلق است
    const restorePromise = api.hydrateSession();
    expect(refreshCalls).toBe(1);

    // در حین pending، logout اتفاق می‌افتد و clearAuth صدا می‌شود
    api.clearAuth();

    // کاربر دوباره login می‌کند
    api.storeAuth({ user: { username: "new-user" }, access_token: "fresh-login-token" });

    // حالا refresh قدیمی resolve می‌شود — باید session جدید را خراب نکند
    resolveRefresh(
      makeResponse({ json: async () => ({ data: { access_token: "stale-token", user: { username: "old-user" } } }) })
    );
    await restorePromise;

    // session باید همان fresh-login-token باشد، نه stale-token
    const auth = api.getStoredAuth();
    expect(auth?.access_token).toBe("fresh-login-token");
  });
});
