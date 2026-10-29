// FE-05 — out-of-order frames must not overwrite newer prices, and symbols
// removed from the subscription must disappear instead of looking live.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useMarketWebSocket } from "@/hooks/useWebSocket";

type Handler = ((event?: { data: string }) => void) | null;

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: Handler = null;
  onmessage: Handler = null;
  onclose: Handler = null;
  onerror: Handler = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
}

function openSocket(): FakeWebSocket {
  const ws = FakeWebSocket.instances[0];
  act(() => {
    ws.readyState = FakeWebSocket.OPEN;
    ws.onopen?.();
  });
  return ws;
}

function push(ws: FakeWebSocket, payload: unknown) {
  act(() => {
    ws.onmessage?.({ data: JSON.stringify(payload) });
  });
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

describe("useMarketWebSocket ordering (FE-05)", () => {
  it("keeps the newer price when an older frame arrives", () => {
    const { result } = renderHook(() => useMarketWebSocket(["AAA"]));
    const ws = openSocket();

    push(ws, [{ symbol: "AAA", price: 10, timestamp: 2000 }]);
    push(ws, [{ symbol: "AAA", price: 5, timestamp: 1000 }]);

    expect(result.current.prices.get("AAA")?.price).toBe(10);
    expect(result.current.prices.get("AAA")?.timestamp).toBe(2000);
  });

  it("drops a symbol it unsubscribes from", () => {
    const { result, rerender } = renderHook(
      ({ symbols }) => useMarketWebSocket(symbols),
      { initialProps: { symbols: ["AAA"] } },
    );
    const ws = openSocket();
    push(ws, [{ symbol: "AAA", price: 10, timestamp: 2000 }]);
    expect(result.current.prices.has("AAA")).toBe(true);

    rerender({ symbols: ["BBB"] });

    expect(result.current.prices.has("AAA")).toBe(false);
    expect(ws.sent.some((m) => m.includes("unsubscribe") && m.includes("AAA"))).toBe(true);
  });
});
