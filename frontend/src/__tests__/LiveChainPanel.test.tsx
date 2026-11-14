import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LiveChainPanel from "@/app/options/components/LiveChainPanel";

// ── Race-observable apiGet mock ─────────────────────────────────────────────
// Each symbol resolves via a deferred we control from the test, so we can
// let an OLD symbol's response land AFTER a NEW symbol was selected and
// assert the UI still shows the NEW symbol (aborted request must be ignored).
type Deferred = {
  resolve: (v: unknown) => void;
  reject: (e: unknown) => void;
  signal: AbortSignal | null;
};

const deferreds: Record<string, Deferred[]> = {};
const apiGetMock = vi.fn((_url: string, _token?: unknown, _signal?: AbortSignal) =>
  Promise.resolve() as Promise<unknown>
);

vi.mock("@/lib/api", () => ({
  apiGet: (url: string, token?: unknown, signal?: AbortSignal) => apiGetMock(url, token, signal),
}));

function chainPayload(underlying: string, price: number) {
  return {
    success: true,
    data: {
      underlying,
      underlying_price: price,
      calls: [
        { symbol: `${underlying}-C1`, strike: price + 1000, price: 500, volume: 10, oi: 20, bid: 490, ask: 510, days_to_expiry: 12 },
      ],
      puts: [],
      total_contracts: 1,
    },
  };
}

function setupDeferredCall(url: string) {
  const symbolKey = decodeURIComponent(url.split("/live/chain/")[1]?.split("?")[0] ?? "?");
  const def: Deferred = { resolve: () => {}, reject: () => {}, signal: null };
  const promise = new Promise((resolve, reject) => {
    def.resolve = resolve;
    def.reject = reject;
  });
  deferreds[symbolKey] = deferreds[symbolKey] ?? [];
  deferreds[symbolKey].push(def);
  // capture the abort signal passed by the hook
  apiGetMock.mockImplementationOnce((_url: string, _token?: unknown, signal?: AbortSignal) => {
    def.signal = signal ?? null;
    return promise;
  });
  return promise;
}

function flushCall(symbolKey: string, payload: unknown, i = 0) {
  deferreds[symbolKey][i].resolve(payload);
}

beforeEach(() => {
  for (const k of Object.keys(deferreds)) delete deferreds[k];
  apiGetMock.mockReset();
  apiGetMock.mockImplementation((_url: string, _token?: unknown, _signal?: AbortSignal) =>
    Promise.resolve() as Promise<unknown>
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPanel() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <LiveChainPanel />
    </QueryClientProvider>
  );
}

describe("LiveChainPanel — request race protection", () => {
  it("passes an abort signal and never lets a stale symbol response overwrite the new one", async () => {
    const user = userEvent.setup();
    const p1 = setupDeferredCall("/options/live/chain/%D8%B0%D9%88%D8%A8?limit=50"); // ذوب
    const p2 = setupDeferredCall("/options/live/chain/%D9%81%D8%AE%D8%B2?limit=50"); // فخز
    renderPanel();

    // Select first symbol
    await user.click(screen.getByRole("button", { name: "ذوب" }));
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(1));
    // Select second symbol before the first resolves
    await user.click(screen.getByRole("button", { name: "فخز" }));
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledTimes(2));

    // The first request must have received an abort signal and be aborted now.
    expect(deferreds["ذوب"][0].signal).not.toBeNull();
    expect(deferreds["ذوب"][0].signal!.aborted).toBe(true);

    // Resolve the OLD symbol's request — UI must still show the NEW symbol.
    flushCall("ذوب", chainPayload("ذوب", 11111));
    await p1.catch(() => {});
    await waitFor(() => {
      expect(screen.getByText("فخز")).toBeInTheDocument();
    });
    expect(screen.queryByText("ذوب-C1")).not.toBeInTheDocument();

    // Now resolve the NEW symbol — its data renders.
    flushCall("فخز", chainPayload("فخز", 22222));
    await p2.catch(() => {});
    await waitFor(() => {
      expect(screen.getByText("فخز-C1")).toBeInTheDocument();
    });
  });

  it("shows an explicit error banner with retry on failure (no silent mock)", async () => {
    const user = userEvent.setup();
    apiGetMock.mockRejectedValueOnce(new Error("HTTP 503: upstream unavailable"));
    renderPanel();

    await user.click(screen.getByRole("button", { name: "ذوب" }));

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("خطا در دریافت داده‌ها از سرور");
    expect(banner).toHaveTextContent("HTTP 503");

    // Retry button re-issues the request.
    apiGetMock.mockResolvedValueOnce(chainPayload("ذوب", 33333));
    await user.click(screen.getByRole("button", { name: "تلاش مجدد" }));
    await waitFor(() => {
      expect(screen.getByText("ذوب-C1")).toBeInTheDocument();
    });
  });

  it("warns explicitly when the server answers with an empty chain", async () => {
    const user = userEvent.setup();
    apiGetMock.mockResolvedValueOnce({
      success: true,
      data: { underlying: "ذوب", underlying_price: 9000, calls: [], puts: [], total_contracts: 0 },
    });
    renderPanel();
    await user.click(screen.getByRole("button", { name: "ذوب" }));

    const warning = await screen.findByRole("status");
    expect(warning).toHaveTextContent("هشدار: داده‌ای برای این نماد یافت نشد");
  });
});
