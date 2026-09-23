import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

// Controlled useQuery stub — each test pins the query state the hooks receive.
let queryState: { data?: unknown; isError?: boolean; isLoading?: boolean } = {};
// The most recent query options are captured so tests can also invoke the
// REAL queryFn (mapping path) against a mocked apiGet.
let lastQueryOpts: { queryFn?: () => Promise<unknown> } = {};
vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: { queryFn?: () => Promise<unknown> }) => {
    lastQueryOpts = opts;
    return {
      data: queryState.data,
      isError: queryState.isError ?? false,
      isLoading: queryState.isLoading ?? false,
    };
  },
}));

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  extractArray: (res: unknown) => {
    const d = (res as { data?: unknown })?.data;
    if (Array.isArray(d)) return d;
    if (Array.isArray((d as { items?: unknown[] })?.items)) return (d as { items: unknown[] }).items;
    return [];
  },
}));

import {
  useIndices,
  useNewsItems,
  useQuoteCards,
  useTopStocks,
  useActiveSymbols,
  useTopPerformers,
  useTickerItems,
} from "@/hooks/useMarketData";

beforeEach(() => {
  queryState = {};
  lastQueryOpts = {};
  apiGetMock.mockReset();
});

describe("useMarketData — no silent mock fallback contract", () => {
  it("useIndices: empty feed → empty data + isLive=false (no INDICES mock leak)", () => {
    queryState = { data: [], isError: false, isLoading: false };
    const { result } = renderHook(() => useIndices());
    expect(result.current.data).toEqual([]);
    expect(result.current.isLive).toBe(false);
    expect(result.current.isError).toBe(false);
  });

  it("useIndices: fetch error → isLive=false + isError=true, data still empty", () => {
    queryState = { data: undefined, isError: true, isLoading: false };
    const { result } = renderHook(() => useIndices());
    expect(result.current.data).toEqual([]);
    expect(result.current.isError).toBe(true);
    expect(result.current.isLive).toBe(false);
  });

  it("useIndices: real rows → isLive=true and the queryFn maps raw fields", async () => {
    queryState = {
      data: [
        { id: 1, name: "شاخص کل", index_value: 2500000, index_change: 12000, index_change_pct: 0.48 },
      ],
      isError: false,
      isLoading: false,
    };
    const { result } = renderHook(() => useIndices());
    expect(result.current.isLive).toBe(true);
    // Mapping path: run the real queryFn against a mocked apiGet.
    apiGetMock.mockResolvedValueOnce({
      success: true,
      data: [{ id: 1, name: "شاخص کل", index_value: 2500000, index_change: 12000, index_change_pct: 0.48 }],
    });
    const mapped = (await lastQueryOpts.queryFn?.()) as Array<{ name: string; value: number }>;
    expect(mapped[0]).toMatchObject({ name: "شاخص کل", value: 2500000, changePct: 0.48 });
  });

  it("useNewsItems: error → empty array, never the NEWS mock", () => {
    queryState = { data: undefined, isError: true, isLoading: false };
    const { result } = renderHook(() => useNewsItems());
    expect(result.current.data).toEqual([]);
    expect(result.current.isError).toBe(true);
  });

  it("useQuoteCards: error → empty array, never the QUOTES mock", () => {
    queryState = { data: undefined, isError: true, isLoading: false };
    const { result } = renderHook(() => useQuoteCards());
    expect(result.current.data).toEqual([]);
    expect(result.current.isLive).toBe(false);
  });

  it("useTopStocks: heatmap derived, empty when the feed is empty", () => {
    queryState = { data: [], isError: false, isLoading: false };
    const { result } = renderHook(() => useTopStocks());
    expect(result.current.data).toEqual([]);
    expect(result.current.isLive).toBe(false);
  });

  it("useTopStocks: sorted by changePct descending on a live feed", () => {
    queryState = {
      data: [
        { symbol: "A", name: "a", change: 1.0, value: 10e9 },
        { symbol: "B", name: "b", change: 3.5, value: 20e9 },
        { symbol: "C", name: "c", change: -2.0, value: 5e9 },
      ],
      isError: false,
      isLoading: false,
    };
    const { result } = renderHook(() => useTopStocks());
    expect(result.current.data.map((s) => s.symbol)).toEqual(["B", "A", "C"]);
    expect(result.current.isLive).toBe(true);
  });

  it("useActiveSymbols: splits tse/otc by market label", () => {
    queryState = {
      data: [
        { symbol: "T1", name: "t1", change: 1, value: 30e9, market: "بورس تهران" },
        { symbol: "O1", name: "o1", change: 2, value: 12e9, market: "فرابورس" },
      ],
      isError: false,
      isLoading: false,
    };
    const { result } = renderHook(() => useActiveSymbols());
    expect(result.current.data.tse.map((s) => s.symbol)).toEqual(["T1"]);
    expect(result.current.data.otc.map((s) => s.symbol)).toEqual(["O1"]);
    expect(result.current.isLive).toBe(true);
  });

  it("useTopPerformers / useTickerItems: empty on empty feed", () => {
    queryState = { data: [], isError: false, isLoading: false };
    const tp = renderHook(() => useTopPerformers());
    const tk = renderHook(() => useTickerItems());
    expect(tp.result.current.data).toEqual([]);
    expect(tk.result.current.data).toEqual([]);
  });

  it("first-load state surfaces isLoading so widgets can suppress the banner", () => {
    queryState = { data: undefined, isError: false, isLoading: true };
    const { result } = renderHook(() => useQuoteCards());
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isLive).toBe(false);
  });
});
