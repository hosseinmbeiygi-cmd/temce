// F6 / C10 — لایهٔ زنده: هر دو نوع پیام، reconnect با backoff نمایی، و کهنگی.
//
// پیش از این اصلاح، `onmessage` فقط `type === "snapshot"` را می‌فهمید و `hot`
// دور ریخته می‌شد، و layout با یک `setTimeout(…, 3000)` نشانگر Live را فارغ از
// وضعیت واقعی سوکت خاموش می‌کرد.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

/** کلاس WebSocket ساختگی: شمارش نمونه‌ها + دستی fire کردن رویدادها. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  frame(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  drop() {
    this.readyState = 3;
    this.onclose?.();
  }
}

const HOT_FRAME = {
  type: "hot",
  data: {
    status: "ok",
    timestamp: "2026-10-24T10:00:00Z",
    refs: { xau_usd: 2345.67, usd_irt: 900000, aed_gap_pct: 1.25 },
    score: { total: 55, decision: "YELLOW" },
    signal: { action: "HOLD", confidence: 0.4, reason: "neutral" },
  },
};

const SNAPSHOT_FRAME = {
  type: "snapshot",
  data: {
    snapshot_at: "2026-10-24T10:00:00Z",
    references: {
      xau_usd: 2345.67,
      usd_irt: 900000,
      aed_irt: 245000,
      aed_parity_usd: 3.6725,
      aed_gap_pct: 1.25,
      source: "brsapi",
      age_seconds: 2,
    },
    gold: {},
    coins: {},
    funds: [],
    score: {
      total: 55,
      decision: "YELLOW",
      components: {},
      hard_stop_active: false,
      hard_stop_reason: null,
    },
    quality_flag: "clean",
  },
};

async function freshManager() {
  vi.resetModules();
  const api = await import("@/lib/api");
  api.storeAuth({ user: {}, access_token: "tok" });
  const gold = await import("@/lib/goldApi");
  return { gold, api };
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("GoldWSManager (C10)", () => {
  it("accepts both hot and snapshot frames and timestamps them", async () => {
    const { gold } = await freshManager();
    const seen: Array<{ state: string; snap: unknown; info: Record<string, unknown> }> = [];

    gold.getGoldWSManager().subscribe((state, snap, info) => {
      seen.push({ state, snap, info: info as unknown as Record<string, unknown> });
    });

    const socket = FakeWebSocket.instances[0];
    expect(socket).toBeDefined();
    socket.open();

    socket.frame(HOT_FRAME);
    let last = seen[seen.length - 1];
    expect(last.info.lastHot).toBeTruthy();
    expect(last.info.lastMessageAt).toBeTypeOf("number");
    expect(last.info.lastSnapshotAt).toBeNull();

    const hotAt = last.info.lastMessageAt as number;
    vi.advanceTimersByTime(1000);
    socket.frame(SNAPSHOT_FRAME);
    last = seen[seen.length - 1];
    // snapshot جای hot را نمی‌گیرد، ولی lastSnapshotAt را پر می‌کند
    expect(last.info.lastSnapshotAt).toBeTypeOf("number");
    expect(last.snap).toBeTruthy();
    expect((last.info.lastMessageAt as number) > hotAt).toBe(true);
  });

  it("reconnects with exponential backoff and resets after a successful open", async () => {
    const { gold } = await freshManager();
    const unsubscribe = gold.getGoldWSManager().subscribe(() => {});

    expect(FakeWebSocket.instances).toHaveLength(1);
    FakeWebSocket.instances[0].drop();

    // ۱ ثانیه اول
    vi.advanceTimersByTime(999);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    // دومین تلاش باید ۲ ثانیه بعد بیاید، نه ۱ ثانیه بعد
    FakeWebSocket.instances[1].drop();
    vi.advanceTimersByTime(1999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    // بعد از یک اتصال موفق backoff به اول برمی‌گردد
    FakeWebSocket.instances[2].open();
    FakeWebSocket.instances[2].drop();
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(4);

    unsubscribe();
  });

  it("never lets the backoff exceed its ceiling", async () => {
    const { gold } = await freshManager();
    gold.getGoldWSManager().subscribe(() => {});
    for (let i = 0; i < 12; i++) {
      FakeWebSocket.instances[FakeWebSocket.instances.length - 1].drop();
      vi.advanceTimersByTime(30_000);
    }
    // ۱+۲+۴+۸+۱۶ سپس سقف ۳۰ ثانیه؛ هیچ‌وقت بیشتر از سقف نمی‌شود
    const sockets = FakeWebSocket.instances;
    expect(sockets.length).toBeGreaterThan(6);
    expect(sockets.length).toBeLessThan(15);
  });
});

describe("useGoldWS staleness (F6)", () => {
  it("marks the stream stale once no frame has arrived for more than 2× the hot interval", async () => {
    vi.resetModules();
    const api = await import("@/lib/api");
    api.storeAuth({ user: {}, access_token: "tok" });
    const { useGoldWS } = await import("@/hooks/useGoldWS");

    const { result } = renderHook(() => useGoldWS());
    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.open();
      socket.frame(HOT_FRAME);
    });

    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(result.current.connected).toBe(true);
    expect(result.current.stale).toBe(false);
    expect(result.current.ageSeconds).toBe(5);

    // ۲× بازهٔ hot = ۲۰ ثانیه؛ کمی بعدش باید کهنگی اعلام شود
    act(() => {
      vi.advanceTimersByTime(16_000);
    });
    expect(result.current.stale).toBe(true);
    expect(result.current.ageSeconds).toBe(21);

    // یک پیام تازه کهنگی را پاک می‌کند
    act(() => {
      socket.frame(HOT_FRAME);
    });
    expect(result.current.stale).toBe(false);
  });

  it("is not stale-but-connected while the socket itself is down", async () => {
    vi.resetModules();
    const api = await import("@/lib/api");
    api.storeAuth({ user: {}, access_token: "tok" });
    const { useGoldWS } = await import("@/hooks/useGoldWS");

    const { result } = renderHook(() => useGoldWS());
    act(() => {
      FakeWebSocket.instances[0].open();
      FakeWebSocket.instances[0].drop();
    });

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(result.current.connected).toBe(false);
    expect(result.current.stale).toBe(false);
  });
});
