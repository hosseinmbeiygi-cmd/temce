import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSymbolPrices } from "@/hooks/useWebSocket";

// ── Fake WebSocket (jsdom has no real WebSocket) ──────────────────────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(_url: string) {
    MockWebSocket.instances.push(this);
  }

  emitOpen() {
    this.onopen?.();
  }
  emitMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  emitClose() {
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
});
