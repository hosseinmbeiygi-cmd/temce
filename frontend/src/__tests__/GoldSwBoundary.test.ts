// S1 — مرز بین دو Service Worker رقیب.
//
// دو SW ثبت می‌شوند:
//   * `/sw.js`          بدون scope ⇒ scope = `/` (src/app/providers.tsx:15)
//   * `/golddesk-sw.js` با scope `/gold` (src/components/gold/PWAProvider.tsx:21)
// طبق spec برای یک client، registration با scope طولانی‌تر برنده است ⇒ صفحات
// /gold را golddesk-sw کنترل می‌کند و بقیهٔ اپ را sw.js.
//
// نکته‌ای که اولاً در تست لازم شد: **CacheStorage بین هر دو SW مشترک است** (per
// origin). پس اگر `sw.js` روزی /api/ را cache-first کند، می‌تواند ورودیِ
// کش‌شده توسط golddesk-sw (یا نسخهٔ قدیمی خودش) را سرو کند. خواستهٔ S1 دقیقاً
// همین را قفل می‌کند: هیچ SW ای پاسخ /api/v1/gold/* را از cache-first ندهد، و
// سقف عمر دادهٔ مالی در همهٔ SWها یک عدد باشد.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MockCacheStorage,
  bootSw,
  jsonResponse,
  loadSwSource,
  respondWith,
} from "./fixtures/swHarness";

const ROOT = resolve(process.cwd(), "public");
const GOLD_SW = readFileSync(resolve(ROOT, "golddesk-sw.js"), "utf8");
const APP_SW = readFileSync(resolve(ROOT, "sw.js"), "utf8");

const GOLD_URL = "http://localhost/api/v1/gold/snapshot";
const ORIGINAL_FETCH = globalThis.fetch;

/** مقدار ثابت سقف عمر مالی در یک فایل SW؛ undefined یعنی اصلاً مفهومش نیست. */
function declaredMaxAge(source: string): number | undefined {
  const m = /FINANCIAL_MAX_AGE_MS\s*=\s*([\d_]+)/.exec(source);
  return m ? Number(m[1].replace(/_/g, "")) : undefined;
}

function boot(source: string, fetchImpl: unknown, caches: MockCacheStorage) {
  return bootSw(
    loadSwSource(source, { fetch: fetchImpl, caches, Response, Request, Headers, console }),
  );
}

describe("S1 — which SW controls what", () => {
  it("registers two workers with scopes such that /gold is owned by the gold worker", () => {
    const providers = readFileSync(resolve(process.cwd(), "src/app/providers.tsx"), "utf8");
    const pwa = readFileSync(resolve(process.cwd(), "src/components/gold/PWAProvider.tsx"), "utf8");

    expect(providers).toMatch(/register\("\/sw\.js"\)/);
    expect(pwa).toMatch(/register\("\/golddesk-sw\.js",\s*\{\s*scope:\s*"\/gold"\s*\}/);
    // /gold تحت scope / است، پس اگر روزی registration طلا حذف شود آن را sw.js
    // می‌گیرد؛ این ادعا در تست‌های پایین همان رفتار را هم می‌سنجد.
  });
});

describe("S1 — no SW cache-firsts gold financial data", () => {
  let caches: MockCacheStorage;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-24T10:00:00Z"));
    caches = new MockCacheStorage();
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
    vi.useRealTimers();
  });

  /** یک پاسخ مالی را از پیش در کش می‌گذارد (انگار نسخهٔ دیگر SW نوشته). */
  async function seedCachedGold(body: unknown, ageMs: number) {
    const cache = await caches.open("cross-worker-shared");
    await cache.put(
      new Request(GOLD_URL),
      jsonResponse(body, { "x-golddesk-cached-at": String(Date.now() - ageMs) }),
    );
  }

  for (const [name, source] of [
    ["golddesk-sw.js", GOLD_SW],
    ["sw.js (scope /)", APP_SW],
  ]) {
    it(`${name}: network answer always wins over a cached gold response`, async () => {
      await seedCachedGold({ success: true, data: { xau_usd: 111 } }, 1_000);
      fetchMock.mockResolvedValue(jsonResponse({ success: true, data: { xau_usd: 222 } }));

      const sw = boot(source, fetchMock, caches);
      const res = await respondWith(sw, GOLD_URL);
      expect(await res.json()).toMatchObject({ data: { xau_usd: 222 } });
    });

    it(`${name}: never serves a gold response older than the shared financial max age`, async () => {
      await seedCachedGold({ success: true, data: { xau_usd: 333 } }, 20 * 60_000);
      fetchMock.mockRejectedValue(new Error("network down"));

      const sw = boot(source, fetchMock, caches);
      const res = await respondWith(sw, GOLD_URL);
      const text = await res.text();
      expect(text, "دادهٔ مالی کهنه از cache سرو شد").not.toContain("333");
      expect(res.ok).toBe(false);
    });
  }

  it("both workers declare ONE financial max age, so no surface is fresher-tolerant than another", () => {
    const gold = declaredMaxAge(GOLD_SW);
    const app = declaredMaxAge(APP_SW);
    expect(gold, "golddesk-sw.js سقف عمر مالی اعلام‌شده ندارد").toBeTypeOf("number");
    expect(app, "sw.js اصلاً مفهوم سقف عمر دادهٔ مالی را ندارد ⇒ هر دو SW یکی نیستند").toBeTypeOf(
      "number",
    );
    expect(app).toBe(gold);
    expect(gold).toBe(300_000);
  });
});
