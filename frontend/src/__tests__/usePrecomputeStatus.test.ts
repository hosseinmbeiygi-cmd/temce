import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor, cleanup } from "@testing-library/react";
import { usePrecomputeStatus, buildPrecomputeWsUrl } from "@/hooks/usePrecomputeStatus";
import { getPrecomputeStore } from "@/stores/precomputeStore";
import { getSoundManager } from "@/lib/sound/SoundEffectManager";

// ── Fake WebSocket (jsdom has no real WebSocket) ───────────────
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  readyState = 1;
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  emitOpen() {
    this.onopen?.();
  }
  emitMessage(data: unknown) {
    this.onmessage?.({ data: typeof data === "string" ? data : JSON.stringify(data) });
  }
  emitClose() {
    this.onclose?.();
  }
  emitError() {
    this.onerror?.();
  }
}

// ── fetch helpers ──────────────────────────────────────────────
function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "ERROR",
    headers: new Headers(),
    redirected: false,
    type: "basic" as const,
    url: "",
    clone: () => jsonResponse(body, status),
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    bytes: () => Promise.resolve(new Uint8Array(0)),
    formData: () => Promise.resolve(new FormData()),
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response;
}

const runningStatus = {
  overall_status: "RUNNING",
  current_group: "A",
  total_symbols: 60,
  completed_symbols: 10,
  failed_symbols: 0,
  progress_percent: 16.6,
  current_symbol: "فولاد",
  estimated_remaining_seconds: 30,
  last_update: "2026-09-13T09:00:00.000Z",
  groups: {
    A: { total: 10, completed: 10, failed: 0, status: "SUCCESS" },
    B: { total: 20, completed: 0, failed: 0, status: "RUNNING" },
    C: { total: 30, completed: 0, failed: 0, status: "PENDING" },
  },
};

const readyRows = [
  {
    symbol: "فولاد",
    group: "A",
    last_price: 1200,
    closing_price: 1190,
    technical_score: 70,
    liquidity_score: 80,
    money_flow_score: 65,
    armor_score: 78.2,
    data_dri: 93,
    is_unreliable: false,
    red_flags: [],
    calculated_at: "2026-09-13T09:00:00.000Z",
    expires_at: "2099-01-01T00:00:00.000Z",
    version: "v4.0",
  },
];

function installFetchMock() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/precompute/status")) return jsonResponse({ success: true, data: runningStatus });
    if (url.includes("/dashboard/ready")) return jsonResponse({ success: true, data: readyRows });
    if (url.includes("/precompute/start")) return jsonResponse({ success: true, data: { dispatched: true } });
    return jsonResponse({});
  });
}

const store = getPrecomputeStore();

describe("buildPrecomputeWsUrl", () => {
  const base = { hostname: "app.example.com", host: "app.example.com", protocol: "https:" };

  it("prefers an explicit NEXT_PUBLIC_WS_URL", () => {
    expect(
      buildPrecomputeWsUrl({ ...base, explicitWsUrl: "wss://edge.example.com/ws/precompute", apiBaseUrl: "https://api.example.com/api/v1" })
    ).toBe("wss://edge.example.com/ws/precompute");
  });

  it("derives the socket URL from an absolute API base", () => {
    expect(buildPrecomputeWsUrl({ ...base, apiBaseUrl: "http://127.0.0.1:8000/api/v1" })).toBe(
      "ws://127.0.0.1:8000/api/v1/ws/precompute"
    );
    expect(buildPrecomputeWsUrl({ ...base, apiBaseUrl: "https://api.example.com/api/v1/" })).toBe(
      "wss://api.example.com/api/v1/ws/precompute"
    );
  });

  it("dials the backend port directly for localhost development", () => {
    expect(buildPrecomputeWsUrl({ hostname: "localhost", host: "localhost:3000", protocol: "http:", apiBaseUrl: "/api/v1" })).toBe(
      "ws://localhost:8000/api/v1/ws/precompute"
    );
    expect(buildPrecomputeWsUrl({ hostname: "127.0.0.1", host: "127.0.0.1:3000", protocol: "http:" })).toBe(
      "ws://127.0.0.1:8000/api/v1/ws/precompute"
    );
  });

  it("uses a same-origin socket behind a reverse proxy (CSP connect-src 'self')", () => {
    expect(buildPrecomputeWsUrl({ ...base, apiBaseUrl: "/api/v1" })).toBe("wss://app.example.com/api/v1/ws/precompute");
    expect(buildPrecomputeWsUrl({ hostname: "10.0.0.5", host: "10.0.0.5:8080", protocol: "http:" })).toBe(
      "ws://10.0.0.5:8080/api/v1/ws/precompute"
    );
  });
});

describe("usePrecomputeStatus", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    globalThis.fetch = installFetchMock() as unknown as typeof fetch;
    store.reset();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("opens a websocket and starts fallback polling on mount", async () => {
    renderHook(() => usePrecomputeStatus());

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain("/ws/precompute");
    await waitFor(() => expect(store.getSnapshot().status).not.toBeNull());
    expect(store.getSnapshot().isPolling).toBe(true);
  });

  it("hydrates the grid from the hot cache on the first poll", async () => {
    renderHook(() => usePrecomputeStatus());
    await waitFor(() => expect(store.getSnapshot().results.size).toBeGreaterThan(0));
    expect(store.getSnapshot().results.get("فولاد")?.armor_score).toBe(78.2);
  });

  it("reports wsConnected after the socket opens", async () => {
    const { result } = renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];

    act(() => ws.emitOpen());

    await waitFor(() => expect(result.current.wsConnected).toBe(true));
    expect(store.getSnapshot().wsConnected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("falls back to aggressive polling and clears wsConnected on close", async () => {
    const { result } = renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];

    act(() => ws.emitOpen());
    await waitFor(() => expect(result.current.wsConnected).toBe(true));

    act(() => ws.emitClose());

    await waitFor(() => expect(result.current.wsConnected).toBe(false));
    expect(store.getSnapshot().isPolling).toBe(true);
  });

  // ── event dispatcher (regression for the type-precedence bug) ─
  it("applies PRECOMPUTATION_COMPLETED instead of coercing it to PROGRESS", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_COMPLETED",
        payload: { total: 60, success: 58, failed: 2, avg_dri: 90.5, duration_seconds: 42, timestamp: "2026-09-13T09:10:00.000Z" },
      })
    );

    const status = store.getSnapshot().status;
    expect(store.getSnapshot().lastEvent).toBe("PRECOMPUTATION_COMPLETED");
    expect(status?.overall_status).toBe("SUCCESS");
    expect(status?.progress_percent).toBe(100);
    expect(status?.completed_symbols).toBe(58);
    expect(store.getSnapshot().visibleGroups).toEqual(["A", "B", "C"]);
  });

  it("triggers the sound manager on PRECOMPUTATION_COMPLETED", async () => {
    const spy = vi.spyOn(getSoundManager(), "onPrecomputationCompleted").mockImplementation(() => {});
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_COMPLETED",
        payload: { total: 60, success: 60, failed: 0, avg_dri: 92, duration_seconds: 40, timestamp: "2026-09-13T09:10:00.000Z" },
      })
    );

    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("applies PRECOMPUTATION_GROUP_COMPLETED and pings the sound manager", async () => {
    const spy = vi.spyOn(getSoundManager(), "onGroupCompleted").mockImplementation(() => {});
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_GROUP_COMPLETED",
        payload: { group: "A", total_processed: 10, failed: 1, timestamp: "2026-09-13T09:05:00.000Z" },
      })
    );

    expect(store.getSnapshot().status?.groups.A.status).toBe("SUCCESS");
    expect(store.getSnapshot().lastEvent).toBe("PRECOMPUTATION_GROUP_COMPLETED");
    expect(spy).toHaveBeenCalledWith("A");
  });

  it("accepts the {event, data} envelope", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        event: "PRECOMPUTATION_PROGRESS",
        data: { group: "B", completed: 3, total: 20, percent: 41, current_symbol: "خودرو" },
      })
    );

    const status = store.getSnapshot().status;
    expect(status?.progress_percent).toBe(41);
    expect(status?.current_symbol).toBe("خودرو");
    expect(status?.current_group).toBe("B");
  });

  it("accepts a bare progress payload without an envelope", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() => ws.emitMessage({ group: "A", completed: 2, total: 10, percent: 8, current_symbol: "فملی" }));

    expect(store.getSnapshot().status?.progress_percent).toBe(8);
    expect(store.getSnapshot().lastEvent).toBe("PRECOMPUTATION_PROGRESS");
  });

  // ── funnel flow (api/ws_manager → job_state → snapshot frames) ──
  it("applies PRECOMPUTATION_STATUS_SNAPSHOT and re-hydrates the grid", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_STATUS_SNAPSHOT",
        payload: runningStatus,
      })
    );

    expect(store.getSnapshot().status?.overall_status).toBe("RUNNING");
    expect(store.getSnapshot().status?.progress_percent).toBe(16.6);
    await waitFor(() => expect(store.getSnapshot().results.get("فولاد")?.armor_score).toBe(78.2));
  });

  it("resets to RUNNING on PRECOMPUTATION_STARTED, keeping hot-cache rows", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    // A finished previous run is on the store
    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_COMPLETED",
        payload: { total: 60, success: 58, failed: 2, avg_dri: 90.5, duration_seconds: 42, timestamp: "2026-09-13T09:10:00.000Z" },
      })
    );
    expect(store.getSnapshot().status?.overall_status).toBe("SUCCESS");

    // A new run starts → banner must flip back to RUNNING on a clean slate
    act(() => ws.emitMessage({ type: "PRECOMPUTATION_STARTED", payload: { timestamp: "2026-09-13T10:00:00.000Z", dispatched: true } }));

    const status = store.getSnapshot().status;
    expect(status?.overall_status).toBe("RUNNING");
    expect(status?.current_group).toBe("A");
    expect(status?.progress_percent).toBe(0);
    expect(status?.completed_symbols).toBe(0);
    expect(status?.failed_symbols).toBe(0);
    expect(status?.current_symbol).toBeNull();
    // the store stamps last_update client-side on every patch — must be fresh, not the old run's
    expect(Date.parse(status?.last_update ?? "")).toBeGreaterThan(Date.parse("2026-09-13T10:00:00.000Z"));
    // hot-cache rows survive the reset (they are still valid until re-computed);
    // the COMPLETED handler hydrates them via an async fetchReady()
    await waitFor(() => expect(store.getSnapshot().results.get("فولاد")).toBeDefined());
  });

  it("land subsequent PROGRESS events on the reset RUNNING state after STARTED", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() => ws.emitMessage({ type: "PRECOMPUTATION_STARTED", payload: { timestamp: "2026-09-13T10:00:00.000Z" } }));
    act(() =>
      ws.emitMessage({
        type: "PRECOMPUTATION_PROGRESS",
        payload: { group: "A", completed: 4, total: 10, percent: 40, current_symbol: "فولاد" },
      })
    );

    const status = store.getSnapshot().status;
    expect(status?.overall_status).toBe("RUNNING");
    expect(status?.groups.A).toMatchObject({ completed: 4, total: 10, status: "RUNNING" });
    expect(status?.progress_percent).toBe(40);
    expect(status?.current_symbol).toBe("فولاد");
  });

  it("adds a row on SYMBOL_RESULT_UPDATED", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    act(() =>
      ws.emitMessage({
        type: "SYMBOL_RESULT_UPDATED",
        payload: { symbol: "خودرو", group: "B", armor_score: 55.4, data_dri: 88, is_unreliable: true },
      })
    );

    const row = store.getSnapshot().results.get("خودرو");
    expect(row?.armor_score).toBe(55.4);
    expect(row?.is_unreliable).toBe(true);
    expect(row?.red_flags).toEqual([]);
  });

  it("ignores malformed websocket frames", async () => {
    renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    const before = store.getSnapshot();
    expect(() => act(() => ws.emitMessage("{not-json"))).not.toThrow();
    expect(store.getSnapshot().lastEvent).toBe(before.lastEvent);
  });

  it("POSTs to /precompute/start when triggerStart is called", async () => {
    const { result } = renderHook(() => usePrecomputeStatus());
    await waitFor(() => expect(store.getSnapshot().status).not.toBeNull());

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockClear();

    await act(async () => {
      await result.current.triggerStart();
    });

    const startCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes("/precompute/start"));
    expect(startCalls).toHaveLength(1);
    expect((startCalls[0][1] as RequestInit).method).toBe("POST");
  });

  it("closes the socket on unmount", async () => {
    const { unmount } = renderHook(() => usePrecomputeStatus());
    const ws = MockWebSocket.instances[0];
    act(() => ws.emitOpen());

    unmount();

    expect(ws.close).toHaveBeenCalled();
  });
});
