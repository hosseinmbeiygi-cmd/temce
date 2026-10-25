// F9 — Golddesk service worker: پاسخ مالی کهنه‌تر از TTL هرگز از cache سرو
// نمی‌شود. این تنها شبکهٔ ایمنی است که مانع می‌شود کاربر در قطعی شبکه، نرخِ
// دیروز را به‌جای نرخِ امروز ببیند و همان‌جا تصمیم بگیرد.
//
// اجرا/مرز بین دو SW در `GoldSwBoundary.test.ts` پوشش داده شده است.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MockCacheStorage,
  jsonResponse,
  loadSwSource,
  respondWith,
  type FakeClient,
} from "./fixtures/swHarness";

const SW_SOURCE = readFileSync(
  resolve(process.cwd(), "public/golddesk-sw.js"),
  "utf8",
);

const GOLD_URL = "http://localhost/api/v1/gold/snapshot";
const ORIGINAL_FETCH = globalThis.fetch;

describe("golddesk service worker (F9)", () => {
  let cacheStorage: MockCacheStorage;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-24T10:00:00Z"));
    cacheStorage = new MockCacheStorage();
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
    vi.useRealTimers();
  });

  function boot(clients: FakeClient[] = []) {
    const sw = loadSwSource(
      SW_SOURCE,
      { fetch: fetchMock, caches: cacheStorage, Response, Request, Headers, console },
      clients,
    );
    sw.dispatch("install", { waitUntil: () => undefined });
    sw.dispatch("activate", { waitUntil: () => undefined });
    return sw;
  }

  it("caches a successful gold API response and can serve it while offline", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ success: true, data: { xau_usd: 2345 } }));
    const sw = boot();
    await respondWith(sw, GOLD_URL);

    // حالا آفلاین: پاسخ باید از کش بیاید، نه خطا
    fetchMock.mockRejectedValue(new Error("network down"));
    const res = await respondWith(sw, GOLD_URL);
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ success: true });
  });

  it("refuses to serve a financial response older than the TTL", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ success: true, data: { xau_usd: 2345 } }));
    const sw = boot();
    await respondWith(sw, GOLD_URL);

    // هشت دقیقه بعد — سقف عمر مالی پنج دقیقه است (کادنس snapshot در C10)
    vi.setSystemTime(new Date("2026-10-24T10:08:00Z"));
    fetchMock.mockRejectedValue(new Error("network down"));

    const res = await respondWith(sw, GOLD_URL);
    expect(res.ok, "پاسخ کهنه نباید ok باشد").toBe(false);
    // و بدنهٔ کهنه هم نباید به دست کاربر برسد
    expect(await res.text()).not.toContain("2345");
  });

  it("serves a cached response that is still inside the TTL window", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ success: true, data: { xau_usd: 999 } }));
    const sw = boot();
    await respondWith(sw, GOLD_URL);

    vi.setSystemTime(new Date("2026-10-24T10:02:00Z")); // ۲ دقیقه — داخل TTL
    fetchMock.mockRejectedValue(new Error("network down"));

    const res = await respondWith(sw, GOLD_URL);
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ success: true });
  });

  it("is network-first: a reachable network always wins over the cache", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, data: { v: 1 } }));
    const sw = boot();
    await respondWith(sw, GOLD_URL);

    fetchMock.mockResolvedValueOnce(jsonResponse({ success: true, data: { v: 2 } }));
    const res = await respondWith(sw, GOLD_URL);
    expect(await res.json()).toMatchObject({ data: { v: 2 } });
  });

  it("only cache-stamps gold API calls, never the rest of /api/", async () => {
    // بقیهٔ /api/ عمداً کش نمی‌شود تا دادهٔ مالی بخش‌های دیگر کهنه سرو نشود.
    fetchMock.mockResolvedValue(jsonResponse({ success: true, data: { v: 1 } }));
    const sw = boot();
    await respondWith(sw, "http://localhost/api/v1/funds/AHR1/list");
    fetchMock.mockRejectedValue(new Error("network down"));
    const res = await respondWith(sw, "http://localhost/api/v1/funds/AHR1/list");
    expect(res.ok).toBe(false);
  });

  it("notifies connected clients when a gold request fails, and again on recovery", async () => {
    const received: Array<Record<string, unknown>> = [];
    const client: FakeClient = {
      url: "http://localhost/gold",
      postMessage: (data) => received.push(data as Record<string, unknown>),
    };

    fetchMock.mockRejectedValue(new Error("network down"));
    const sw = boot([client]);
    await respondWith(sw, GOLD_URL);

    // بنر آفلاین باید از خودِ SW خبر بگیرد، نه فقط از window offline event
    expect(received.some((m) => String(m?.type ?? "").includes("offline"))).toBe(true);

    fetchMock.mockResolvedValue(jsonResponse({ success: true }));
    await respondWith(sw, GOLD_URL);
    expect(received.some((m) => String(m?.type ?? "").includes("online"))).toBe(true);
  });

  it("names its caches with a version so an upgrade cannot reuse stale entries", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ success: true }));
    boot();
    const names = await cacheStorage.keys();
    expect(names.some((n) => /v\d+/.test(n)), `کش‌ها نسخه ندارند: ${names.join(", ")}`).toBe(true);
  });
});
