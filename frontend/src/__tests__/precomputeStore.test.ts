import { describe, it, expect, beforeEach } from "vitest";
import {
  getPrecomputeStore,
  useVisibleGroups,
  type PrecomputeStatus,
  type SymbolArmorResult,
} from "@/stores/precomputeStore";

// ── helpers ────────────────────────────────────────────────────
function makeStatus(overrides: Partial<PrecomputeStatus> = {}): PrecomputeStatus {
  return {
    overall_status: "PENDING",
    current_group: null,
    total_symbols: 0,
    completed_symbols: 0,
    failed_symbols: 0,
    progress_percent: 0,
    current_symbol: null,
    estimated_remaining_seconds: null,
    last_update: new Date().toISOString(),
    groups: {
      A: { total: 10, completed: 0, failed: 0, status: "PENDING" },
      B: { total: 20, completed: 0, failed: 0, status: "PENDING" },
      C: { total: 30, completed: 0, failed: 0, status: "PENDING" },
    },
    ...overrides,
  };
}

function makeResult(overrides: Partial<SymbolArmorResult> = {}): SymbolArmorResult {
  return {
    symbol: "فولاد",
    group: "A",
    last_price: 1000,
    closing_price: 990,
    technical_score: 60,
    liquidity_score: 70,
    money_flow_score: 50,
    armor_score: 72.5,
    data_dri: 95,
    is_unreliable: false,
    red_flags: [],
    calculated_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    version: "v4.0",
    ...overrides,
  };
}

const store = getPrecomputeStore();

describe("precomputeStore", () => {
  beforeEach(() => {
    store.reset();
  });

  // ── initial state ────────────────────────────────────────────
  it("starts empty with no visible groups", () => {
    const snap = store.getSnapshot();
    expect(snap.status).toBeNull();
    expect(snap.visibleGroups).toEqual([]);
    expect(snap.results.size).toBe(0);
    expect(snap.wsConnected).toBe(false);
    expect(snap.isPolling).toBe(false);
    expect(snap.error).toBeNull();
  });

  it("reset() restores the initial state after mutations", () => {
    store.setStatus(makeStatus({ progress_percent: 40, overall_status: "RUNNING" }));
    store.upsertResult(makeResult());
    store.setError("boom");

    store.reset();

    const snap = store.getSnapshot();
    expect(snap.status).toBeNull();
    expect(snap.results.size).toBe(0);
    expect(snap.visibleGroups).toEqual([]);
    expect(snap.error).toBeNull();
  });

  // ── progressive reveal A → B → C ─────────────────────────────
  it("reveals group A as soon as the run starts", () => {
    const next = makeStatus({ overall_status: "RUNNING", current_group: "A" });
    next.groups.A.status = "RUNNING";
    store.setStatus(next);

    expect(store.getSnapshot().visibleGroups).toEqual(["A"]);
  });

  it("adds group B only after group A completes", () => {
    store.setStatus(makeStatus({ overall_status: "RUNNING", progress_percent: 5 }));
    expect(store.getSnapshot().visibleGroups).toEqual(["A"]);

    store.applyGroupCompleted({ group: "A", total_processed: 10, failed: 0, timestamp: new Date().toISOString() });
    expect(store.getSnapshot().visibleGroups).toEqual(["A", "B"]);
  });

  it("adds group C only after group B completes", () => {
    store.applyProgress({ group: "A", completed: 10, total: 10, percent: 20, current_symbol: "فولاد" });
    store.applyProgress({ group: "B", completed: 5, total: 20, percent: 45, current_symbol: "خودرو" });
    expect(store.getSnapshot().visibleGroups).toEqual(["A", "B"]);

    store.applyGroupCompleted({ group: "B", total_processed: 20, failed: 0, timestamp: new Date().toISOString() });
    expect(store.getSnapshot().visibleGroups).toEqual(["A", "B", "C"]);
  });

  // ── PRECOMPUTATION_PROGRESS ──────────────────────────────────
  it("applyProgress updates percent, current symbol and current group", () => {
    store.applyProgress({ group: "A", completed: 4, total: 10, percent: 12.5, current_symbol: "فملی" });

    const snap = store.getSnapshot();
    expect(snap.lastEvent).toBe("PRECOMPUTATION_PROGRESS");
    expect(snap.status?.progress_percent).toBe(12.5);
    expect(snap.status?.current_symbol).toBe("فملی");
    expect(snap.status?.current_group).toBe("A");
    expect(snap.status?.groups.A.status).toBe("RUNNING");
    expect(snap.status?.groups.A.completed).toBe(4);
  });

  // ── PRECOMPUTATION_GROUP_COMPLETED ───────────────────────────
  it("applyGroupCompleted marks the group SUCCESS and advances current group", () => {
    store.applyGroupCompleted({ group: "A", total_processed: 10, failed: 1, timestamp: "2026-09-13T10:00:00.000Z" });

    const snap = store.getSnapshot();
    expect(snap.lastEvent).toBe("PRECOMPUTATION_GROUP_COMPLETED");
    expect(snap.status?.groups.A.status).toBe("SUCCESS");
    expect(snap.status?.groups.A.completed).toBe(10);
    expect(snap.status?.failed_symbols).toBe(1);
    expect(snap.status?.current_group).toBe("B");
    expect(snap.status?.last_update).toBe("2026-09-13T10:00:00.000Z");
  });

  it("applyGroupCompleted marks a fully failed group as FAILED", () => {
    store.applyGroupCompleted({ group: "B", total_processed: 7, failed: 7, timestamp: new Date().toISOString() });
    expect(store.getSnapshot().status?.groups.B.status).toBe("FAILED");
  });

  // ── PRECOMPUTATION_COMPLETED ─────────────────────────────────
  it("applyCompleted finalizes the run and shows every group", () => {
    store.setStatus(makeStatus({ overall_status: "RUNNING", progress_percent: 60 }));
    store.applyCompleted({
      total: 60,
      success: 58,
      failed: 2,
      avg_dri: 91.4,
      duration_seconds: 42,
      timestamp: "2026-09-13T10:01:00.000Z",
    });

    const snap = store.getSnapshot();
    expect(snap.lastEvent).toBe("PRECOMPUTATION_COMPLETED");
    expect(snap.status?.overall_status).toBe("SUCCESS");
    expect(snap.status?.progress_percent).toBe(100);
    expect(snap.status?.completed_symbols).toBe(58);
    expect(snap.status?.failed_symbols).toBe(2);
    expect(snap.status?.current_group).toBeNull();
    expect(snap.status?.current_symbol).toBeNull();
    expect(snap.visibleGroups).toEqual(["A", "B", "C"]);
  });

  it("applyCompleted reports FAILED when every symbol failed", () => {
    store.applyCompleted({ total: 5, success: 0, failed: 5, avg_dri: 0, duration_seconds: 3, timestamp: "" });
    expect(store.getSnapshot().status?.overall_status).toBe("FAILED");
  });

  // ── SYMBOL_RESULT_UPDATED ────────────────────────────────────
  it("upsertResult stores the symbol result", () => {
    const row = makeResult({ symbol: "فولاد", armor_score: 88.1 });
    store.upsertResult(row);

    const snap = store.getSnapshot();
    expect(snap.lastEvent).toBe("SYMBOL_RESULT_UPDATED");
    expect(snap.results.get("فولاد")?.armor_score).toBe(88.1);
  });

  it("derives is_stale from expires_at", () => {
    store.upsertResult(makeResult({ symbol: "کهنه", expires_at: new Date(Date.now() - 60_000).toISOString() }));
    store.upsertResult(makeResult({ symbol: "تازه", expires_at: new Date(Date.now() + 600_000).toISOString() }));

    const snap = store.getSnapshot();
    expect(snap.results.get("کهنه")?.is_stale).toBe(true);
    expect(snap.results.get("تازه")?.is_stale).toBe(false);
  });

  it("keeps the previous value when the same symbol is updated", () => {
    store.upsertResult(makeResult({ symbol: "فولاد", armor_score: 50 }));
    store.upsertResult(makeResult({ symbol: "فولاد", armor_score: 75 }));

    const snap = store.getSnapshot();
    expect(snap.results.size).toBe(1);
    expect(snap.results.get("فولاد")?.armor_score).toBe(75);
  });

  // ── bulk / selectors ─────────────────────────────────────────
  it("setResults bulk-loads rows and selectors filter by group", () => {
    store.setResults([
      makeResult({ symbol: "A1", group: "A" }),
      makeResult({ symbol: "A2", group: "A" }),
      makeResult({ symbol: "B1", group: "B" }),
    ]);

    expect(store.getAllResults()).toHaveLength(3);
    expect(store.getResultsByGroup("A").map((r) => r.symbol).sort()).toEqual(["A1", "A2"]);
    expect(store.getResultsByGroup("C")).toHaveLength(0);
  });

  it("clearResults drops every symbol but keeps the status", () => {
    store.setStatus(makeStatus({ overall_status: "SUCCESS", progress_percent: 100 }));
    store.upsertResult(makeResult());

    store.clearResults();

    const snap = store.getSnapshot();
    expect(snap.results.size).toBe(0);
    expect(snap.status?.overall_status).toBe("SUCCESS");
  });

  // ── subscription ─────────────────────────────────────────────
  it("notifies subscribers on mutation and stops after unsubscribe", () => {
    let calls = 0;
    const unsubscribe = store.subscribe(() => {
      calls += 1;
    });

    store.setStatus(makeStatus({ progress_percent: 10 }));
    expect(calls).toBe(1);

    unsubscribe();
    store.setStatus(makeStatus({ progress_percent: 20 }));
    expect(calls).toBe(1);
  });

  // ── connection flags ─────────────────────────────────────────
  it("tracks websocket / polling / error flags", () => {
    store.setWsConnected(true);
    store.setPolling(false);
    store.setError("socket closed");

    const snap = store.getSnapshot();
    expect(snap.wsConnected).toBe(true);
    expect(snap.isPolling).toBe(false);
    expect(snap.error).toBe("socket closed");
  });

  // ── selector hook export ─────────────────────────────────────
  it("exports a visible-groups selector hook", () => {
    expect(typeof useVisibleGroups).toBe("function");
  });
});
