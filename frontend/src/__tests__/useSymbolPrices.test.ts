import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSymbolPrices } from "@/hooks/useWebSocket";

// ── Fake WebSocket (jsdom has no real WebSocket) ──────────────────────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  emitOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
  emitMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  emitClose() {
    this.readyState = 3;
    this.onclose?.();
  }
}

describe("useSymbolPrices", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts disconnected with empty prices", () => {
    const { result } = renderHook(() => useSymbolPrices(["فولاد"]));
    expect(result.current.connected).toBe(false);
    expect(result.current.prices).toEqual({});
  });

  it("returns live prices as a plain Record keyed by symbol after WS update", () => {
    const { result } = renderHook(() => useSymbolPrices(["فولاد", "خودرو"]));
    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();

    act(() => ws.emitOpen());
    act(() =>
      ws.emitMessage([
        { symbol: "فولاد", price: 1250, change_percent: 2.5, volume: 1_000_000 },
        { symbol: "خودرو", price: 565, change_percent: -0.8 },
      ])
    );

    expect(result.current.connected).toBe(true);
    expect(result.current.prices["فولاد"].price).toBe(1250);
    expect(result.current.prices["فولاد"].price_change_pct).toBe(2.5);
    expect(result.current.prices["فولاد"].change_pct).toBe(2.5);
    expect(result.current.prices["فولاد"].volume).toBe(1_000_000);
    expect(result.current.prices["خودرو"].price_change_pct).toBe(-0.8);
  });

  it("falls back price_change_pct to change when change_percent missing", () => {
    const { result } = renderHook(() => useSymbolPrices(["فولاد"]));
    const ws = MockWebSocket.instances[0];

    act(() => ws.emitOpen());
    act(() => ws.emitMessage([{ symbol: "فولاد", price: 10, change: 1.2 }]));

    expect(result.current.prices["فولاد"].price_change_pct).toBe(1.2);
  });

  it("ignores malformed messages without crashing", () => {
    const { result } = renderHook(() => useSymbolPrices(["فولاد"]));
    const ws = MockWebSocket.instances[0];

    act(() => ws.emitOpen());
    act(() => ws.emitMessage("not-json{{{"));
    expect(result.current.prices).toEqual({});
  });

  it("trades the access token for a one-time ticket and never puts it in the URL", async () => {
    const { clearAuth, storeAuth } = await import("@/lib/api");
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ success: true, data: { ticket: "ws-ticket-1", expires_in: 60 } }),
      text: async () => "",
    }));
    vi.stubGlobal("fetch", fetchMock);
    storeAuth({ user: {}, access_token: "test-token" });
    try {
      renderHook(() => useSymbolPrices(["فولاد"]));
      await vi.waitFor(() => expect(MockWebSocket.instances[0]).toBeDefined());

      const url = MockWebSocket.instances[0].url;
      expect(url).toContain("ticket=ws-ticket-1");
      expect(url).not.toContain("test-token");
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/auth/ws-ticket"),
        expect.objectContaining({ method: "POST" }),
      );
    } finally {
      clearAuth();
    }
  });

  it("never opens a socket when the ticket request fails", async () => {
    const { clearAuth, storeAuth } = await import("@/lib/api");
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({}),
      text: async () => "ticket store unavailable",
    }));
    vi.stubGlobal("fetch", fetchMock);
    storeAuth({ user: {}, access_token: "test-token" });
    try {
      renderHook(() => useSymbolPrices(["فولاد"]));
      for (let i = 0; i < 12; i++) await Promise.resolve();

      expect(fetchMock).toHaveBeenCalled();
      expect(MockWebSocket.instances).toHaveLength(0);
    } finally {
      clearAuth();
    }
  });

  it("subscribes/unsubscribes when the symbol list changes", () => {
    const { rerender } = renderHook(({ symbols }) => useSymbolPrices(symbols), {
      initialProps: { symbols: ["A"] },
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());
    ws.send.mockClear();

    rerender({ symbols: ["A", "B"] });
    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ action: "subscribe", symbols: ["B"] }),
    );

    ws.send.mockClear();
    rerender({ symbols: ["B"] });
    expect(ws.send).toHaveBeenCalledWith(
      JSON.stringify({ action: "unsubscribe", symbols: ["A"] }),
    );
  });

  it("marks an open but silent socket stale, and clears it on a message", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_700_000_000_000);
    try {
      const { result } = renderHook(() => useSymbolPrices(["A"]));
      const ws = MockWebSocket.instances[0];
      act(() => ws.emitOpen());
      // Connected before the first frame: no data to call live yet.
      expect(result.current.stale).toBe(true);

      act(() => ws.emitMessage([{ symbol: "A", price: 10, timestamp: 1_700_000_000 }]));
      expect(result.current.stale).toBe(false);
      expect(result.current.prices.A.timestamp).toBe(1_700_000_000);
    } finally {
      vi.useRealTimers();
    }
  });
});
