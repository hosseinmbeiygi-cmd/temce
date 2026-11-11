// Stage 05 — قرارداد پاکت API: success / data_as_of / cache_hit.
//
// این تست‌ها همان سه حالتی را قفل می‌کنند که قبلاً در فرانت قابل تفکیک نبودند:
// داده، «موفق و خالی»، و «منبع خطا داده».

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiEnvelopeError,
  assertSuccessEnvelope,
  getDataAsOf,
  isCacheHit,
  isDataAsOfFresh,
  parseIsoInstant,
  readEnvelopeMeta,
} from "@/lib/api-envelope";

const NOW = Date.parse("2026-10-28T12:00:00Z");

describe("readEnvelopeMeta", () => {
  it("reads success, data_as_of and cache_hit from the envelope", () => {
    const meta = readEnvelopeMeta({
      success: true,
      data: [{ symbol: "A" }],
      data_as_of: "2026-10-28T11:59:00Z",
      cache_hit: true,
    });
    expect(meta).toMatchObject({
      success: true,
      dataAsOf: "2026-10-28T11:59:00Z",
      cacheHit: true,
      errorMessage: null,
    });
  });

  it("reports a bare payload as 'no envelope' (success null), not as success", () => {
    const meta = readEnvelopeMeta([{ symbol: "A" }]);
    expect(meta.success).toBeNull();
    expect(meta.dataAsOf).toBeNull();
    expect(meta.cacheHit).toBe(false);
  });

  it("reads data_as_of nested under data and the machine-readable error code", () => {
    const meta = readEnvelopeMeta({
      success: false,
      data: { data_as_of: "2026-10-28T11:58:00Z" },
      error: { code: "source_unavailable", message: "Traceback: division by zero" },
    });
    expect(meta.dataAsOf).toBe("2026-10-28T11:58:00Z");
    expect(meta.errorCode).toBe("source_unavailable");
    expect(meta.errorMessage).toMatch(/Traceback/);
  });

  it("exposes helpers over the same envelope", () => {
    const envelope = { success: true, data: [], data_as_of: "2026-10-28T11:00:00Z", cache_hit: true };
    expect(getDataAsOf(envelope)).toBe("2026-10-28T11:00:00Z");
    expect(isCacheHit(envelope)).toBe(true);
  });
});

describe("assertSuccessEnvelope", () => {
  it("throws on success:false and keeps the internal text out of the message", () => {
    const err = (() => {
      try {
        assertSuccessEnvelope(
          { success: false, data: null, error: { message: "Traceback: bubbler.py line 91" } },
          "/market/enriched-heatmap",
        );
        return null;
      } catch (error) {
        return error;
      }
    })();
    expect(err).toBeInstanceOf(ApiEnvelopeError);
    expect((err as ApiEnvelopeError).message).not.toMatch(/Traceback|bubbler/);
    expect((err as ApiEnvelopeError).message).toMatch(/داده در دسترس نیست/);
    // متن داخلی برای لاگ باقی می‌ماند.
    expect((err as ApiEnvelopeError).detail).toMatchObject({ message: expect.stringMatching(/Traceback/) });
  });

  it("does not throw for success:true, for bare payloads, or for arrays", () => {
    expect(() => assertSuccessEnvelope({ success: true, data: [] })).not.toThrow();
    expect(() => assertSuccessEnvelope({ items: [] })).not.toThrow();
    expect(() => assertSuccessEnvelope([])).not.toThrow();
  });
});

describe("parseIsoInstant", () => {
  it("parses Z, explicit offsets and naive server timestamps", () => {
    expect(parseIsoInstant("2026-10-28T12:00:00Z")).toBe(NOW);
    expect(parseIsoInstant("2026-10-28T15:30:00+03:30")).toBe(NOW);
    expect(parseIsoInstant("2026-10-28 12:00:00")).toBe(NOW); // naive ⇒ UTC
    expect(parseIsoInstant("2026-10-28T12:00:00.500Z")).toBe(NOW + 500);
  });

  it("rejects non-ISO strings instead of guessing (Date.parse would accept '12')", () => {
    expect(parseIsoInstant("12")).toBeNull();
    expect(parseIsoInstant("2026-13-40T10:00:00Z")).toBeNull();
    expect(parseIsoInstant("")).toBeNull();
    expect(parseIsoInstant(null)).toBeNull();
    expect(parseIsoInstant(1_760_000_000)).toBeNull();
  });
});

describe("isDataAsOfFresh", () => {
  it("accepts data inside the 5-minute window", () => {
    expect(isDataAsOfFresh("2026-10-28T11:58:00Z", { now: NOW })).toBe(true);
  });

  it("rejects data older than the window", () => {
    expect(isDataAsOfFresh("2026-10-28T11:40:00Z", { now: NOW })).toBe(false);
  });

  it("rejects future timestamps (negative age must not read as fresh)", () => {
    expect(isDataAsOfFresh("2026-10-28T12:30:00Z", { now: NOW })).toBe(false);
  });

  it("rejects missing or malformed data_as_of", () => {
    expect(isDataAsOfFresh(null, { now: NOW })).toBe(false);
    expect(isDataAsOfFresh(undefined, { now: NOW })).toBe(false);
    expect(isDataAsOfFresh("yesterday", { now: NOW })).toBe(false);
  });
});

// ── Transport: apiGet must surface a failed envelope as a rejection ──

function installFetch(handler: (url: string) => { status: number; body: unknown }) {
  const fetchMock = vi.fn(async (input: string): Promise<Response> => {
    if (input.endsWith("/auth/refresh")) {
      return {
        ok: false,
        status: 401,
        json: async (): Promise<unknown> => ({ success: false }),
        text: async (): Promise<string> => "",
      } as unknown as Response;
    }
    const { status, body } = handler(input);
    const text = JSON.stringify(body);
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async (): Promise<unknown> => JSON.parse(text),
      text: async (): Promise<string> => text,
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("apiGet envelope handling", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("rejects when the backend answers HTTP 200 with success:false", async () => {
    installFetch(() => ({
      status: 200,
      body: { success: false, data: null, error: { message: "Traceback: division by zero" } },
    }));
    const { apiGet } = await import("@/lib/api");
    // `resetModules` در beforeEach رجیستری را پاک می‌کند، پس نمونهٔ کلاس باید
    // از همان رجیستریِ تازه گرفته شود وگرنه `instanceof` بی‌دلیل false می‌شود.
    const { ApiEnvelopeError: FreshEnvelopeError } = await import("@/lib/api-envelope");
    const err = (await apiGet("/market/enriched-heatmap").catch((e) => e)) as Error;
    expect(err).toBeInstanceOf(FreshEnvelopeError);
    expect(err.message).not.toMatch(/Traceback/);
  });

  it("resolves the envelope for a successful response and keeps its metadata readable", async () => {
    installFetch(() => ({
      status: 200,
      body: {
        success: true,
        data: [{ symbol: "A" }],
        data_as_of: "2026-10-28T11:59:00Z",
        cache_hit: true,
      },
    }));
    const { apiGet } = await import("@/lib/api");
    const res = await apiGet<{ success: boolean; data: Array<{ symbol: string }> }>(
      "/market/enriched-heatmap",
    );
    expect(res.data).toEqual([{ symbol: "A" }]);
    expect(getDataAsOf(res)).toBe("2026-10-28T11:59:00Z");
    expect(isCacheHit(res)).toBe(true);
  });

  it("keeps bare array payloads working (no envelope, no throw)", async () => {
    installFetch(() => ({ status: 200, body: [{ symbol: "A" }] }));
    const { apiGet } = await import("@/lib/api");
    await expect(apiGet("/market/indices")).resolves.toEqual([{ symbol: "A" }]);
  });

  it("still rejects on a non-2xx status (transport failure path is unchanged)", async () => {
    installFetch(() => ({ status: 500, body: { detail: "boom" } }));
    const { apiGet } = await import("@/lib/api");
    await expect(apiGet("/market/indices")).rejects.toThrow(/HTTP 500/);
  });
});
