// FE-13 — لغو درخواست باید هویت AbortError خود را حفظ کند و اتمام زمان انتظار
// باید یک خطای نوع‌دار (نه خطای عمومی) باشد.
//
// قبلاً هر AbortError داخلی به `Error("Request timeout after …")` تبدیل می‌شد؛
// UI همین متن انگلیسی خام را نشان می‌داد و React Query آن را مثل یک خطای عادی
// دوباره تلاش می‌کرد.

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

type ApiModule = typeof import("@/lib/api");
type ErrorsModule = typeof import("@/lib/api-errors");

async function importApi(): Promise<{ api: ApiModule; errors: ErrorsModule }> {
  const api = await import("@/lib/api");
  const errors = await import("@/lib/api-errors");
  api.storeAuth({ user: { username: "t" }, access_token: "token" });
  return { api, errors };
}

const ORIGINAL_WINDOW = globalThis.window;

beforeEach(() => {
  vi.resetModules();
  Object.defineProperty(globalThis, "window", {
    value: { location: { pathname: "/dashboard", href: "" }, dispatchEvent: vi.fn() },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  Object.defineProperty(globalThis, "window", {
    value: ORIGINAL_WINDOW,
    writable: true,
    configurable: true,
  });
});

describe("api transport — cancellation", () => {
  it("rethrows the caller's AbortError instead of masking it as a failure", async () => {
    const { api } = await importApi();

    const controller = new AbortController();
    controller.abort();

    globalThis.fetch = vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError"));

    await expect(api.apiGet("/signals", undefined, controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});

describe("api transport — timeout", () => {
  it("throws a typed ApiTimeoutError after the request budget elapses", async () => {
    vi.useFakeTimers();
    const { api, errors } = await importApi();

    globalThis.fetch = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

    const pending = api.apiGet("/slow-endpoint");
    const assertion = expect(pending).rejects.toBeInstanceOf(errors.ApiTimeoutError);

    await vi.advanceTimersByTimeAsync(60_000);
    await assertion;
  });
});
