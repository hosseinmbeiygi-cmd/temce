"use client";

/**
 * Precompute Store — Armor Dashboard
 * ===================================
 * Lightweight Zustand-like store without external dependency.
 * Keeps the single source of truth for precompute progress,
 * group states, and symbol-level armor results.
 *
 * Contracts: contracts/schemas.py (PrecomputeStatusResponse, SymbolComputationResult, SymbolGroup, GroupProgress)
 *            contracts/events.md  (PRECOMPUTATION_* events)
 *
 * Decoupled: no import from ingestion / precompute / api modules.
 */

import { useSyncExternalStore } from "react";

// ── Types mirroring contracts/schemas.py ───────────────────────
export type SymbolGroup = "A" | "B" | "C";
export type JobStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED" | "RETRYING" | "SKIPPED" | "STALE";

export interface GroupProgress {
  total: number;
  completed: number;
  failed: number;
  status: JobStatus;
}

export interface PrecomputeStatus {
  overall_status: JobStatus;
  current_group: SymbolGroup | null;
  total_symbols: number;
  completed_symbols: number;
  failed_symbols: number;
  progress_percent: number;
  current_symbol: string | null;
  estimated_remaining_seconds: number | null;
  last_update: string;
  groups: Record<SymbolGroup, GroupProgress>;
}

export interface SymbolArmorResult {
  symbol: string;
  group: SymbolGroup;
  last_price: number;
  closing_price: number;
  technical_score: number;
  liquidity_score: number;
  money_flow_score: number;
  armor_score: number;
  data_dri: number; // 0..100
  is_unreliable: boolean;
  red_flags: string[];
  calculated_at: string;
  expires_at: string;
  version: string;
  // STALE derived flag (client-side)
  is_stale?: boolean;
}

export interface PrecomputeStoreState {
  status: PrecomputeStatus | null;
  results: Map<string, SymbolArmorResult>;
  wsConnected: boolean;
  isPolling: boolean;
  error: string | null;
  lastEvent: string | null;
  // derived
  visibleGroups: SymbolGroup[]; // progressive reveal: A first, then B, C
}

const INITIAL_STATUS: PrecomputeStatus = {
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
    A: { total: 0, completed: 0, failed: 0, status: "PENDING" },
    B: { total: 0, completed: 0, failed: 0, status: "PENDING" },
    C: { total: 0, completed: 0, failed: 0, status: "PENDING" },
  },
};

function cloneStatus(s: PrecomputeStatus): PrecomputeStatus {
  return {
    ...s,
    groups: {
      A: { ...s.groups.A },
      B: { ...s.groups.B },
      C: { ...s.groups.C },
    },
  };
}

function computeVisibleGroups(status: PrecomputeStatus | null): SymbolGroup[] {
  if (!status) return [];
  const groups: SymbolGroup[] = [];
  // A is visible as soon as RUNNING or any completion
  if (status.groups.A.status !== "PENDING" || status.progress_percent > 0) groups.push("A");
  // B appears when A is SUCCESS/SKIPPED or B started
  if (status.groups.B.status !== "PENDING" || status.groups.A.status === "SUCCESS") groups.push("B");
  // C appears when B is SUCCESS/SKIPPED or C started
  if (status.groups.C.status !== "PENDING" || status.groups.B.status === "SUCCESS") groups.push("C");
  // If no progress yet but we have status, show at least A placeholder during RUNNING
  if (groups.length === 0 && status.overall_status === "RUNNING") groups.push("A");
  return groups;
}

// ── Store implementation ───────────────────────────────────────
class PrecomputeStore {
  private state: PrecomputeStoreState = {
    status: null,
    results: new Map(),
    wsConnected: false,
    isPolling: false,
    error: null,
    lastEvent: null,
    visibleGroups: [],
  };
  private listeners = new Set<() => void>();

  // -- subscription (useSyncExternalStore compatible) --
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): PrecomputeStoreState => this.state;

  private emit() {
    for (const l of this.listeners) l();
  }

  // -- mutations -------------------------------------------------
  setStatus(status: PrecomputeStatus | null) {
    this.state = {
      ...this.state,
      status,
      visibleGroups: computeVisibleGroups(status),
      error: null,
    };
    this.emit();
  }

  patchStatus(patch: Partial<PrecomputeStatus>) {
    if (!this.state.status) {
      this.setStatus({ ...INITIAL_STATUS, ...patch, last_update: new Date().toISOString() } as PrecomputeStatus);
      return;
    }
    const next = cloneStatus(this.state.status);
    Object.assign(next, patch);
    next.last_update = new Date().toISOString();
    this.state = { ...this.state, status: next, visibleGroups: computeVisibleGroups(next) };
    this.emit();
  }

  // contracts/events.md: PRECOMPUTATION_PROGRESS { group, completed, total, percent, current_symbol }
  applyProgress(payload: { group: SymbolGroup; completed: number; total: number; percent: number; current_symbol: string }) {
    const base = this.state.status ?? cloneStatus(INITIAL_STATUS);
    const next = cloneStatus(base);
    const g = payload.group;
    if (next.groups[g]) {
      next.groups[g].completed = payload.completed;
      next.groups[g].total = payload.total;
      next.groups[g].status = "RUNNING";
    }
    next.current_group = g;
    next.current_symbol = payload.current_symbol;
    next.progress_percent = payload.percent;
    // derive completed_symbols as sum
    next.completed_symbols = (next.groups.A.completed + next.groups.B.completed + next.groups.C.completed);
    next.total_symbols = next.groups.A.total + next.groups.B.total + next.groups.C.total;
    next.overall_status = "RUNNING";
    next.last_update = new Date().toISOString();
    this.state = { ...this.state, status: next, visibleGroups: computeVisibleGroups(next), lastEvent: "PRECOMPUTATION_PROGRESS" };
    this.emit();
  }

  // PRECOMPUTATION_GROUP_COMPLETED { group, total_processed, failed, timestamp }
  applyGroupCompleted(payload: { group: SymbolGroup; total_processed: number; failed: number; timestamp: string }) {
    const base = this.state.status ?? cloneStatus(INITIAL_STATUS);
    const next = cloneStatus(base);
    const g = payload.group;
    if (next.groups[g]) {
      next.groups[g].completed = payload.total_processed;
      next.groups[g].failed = payload.failed;
      next.groups[g].status = payload.failed > 0 && payload.total_processed === payload.failed ? "FAILED" : "SUCCESS";
    }
    next.failed_symbols = next.groups.A.failed + next.groups.B.failed + next.groups.C.failed;
    next.last_update = payload.timestamp || new Date().toISOString();
    // move current_group forward
    if (g === "A" && next.groups.B.status === "PENDING") next.current_group = "B";
    else if (g === "B" && next.groups.C.status === "PENDING") next.current_group = "C";
    else if (g === "C") next.current_group = null;
    this.state = { ...this.state, status: next, visibleGroups: computeVisibleGroups(next), lastEvent: "PRECOMPUTATION_GROUP_COMPLETED" };
    this.emit();
  }

  // PRECOMPUTATION_COMPLETED { total, success, failed, avg_dri, duration_seconds, timestamp }
  applyCompleted(payload: { total: number; success: number; failed: number; avg_dri: number; duration_seconds: number; timestamp: string }) {
    const base = this.state.status ?? cloneStatus(INITIAL_STATUS);
    const next = cloneStatus(base);
    next.total_symbols = payload.total;
    next.completed_symbols = payload.success;
    next.failed_symbols = payload.failed;
    next.progress_percent = 100;
    next.overall_status = payload.failed === payload.total ? "FAILED" : "SUCCESS";
    next.current_group = null;
    next.current_symbol = null;
    next.last_update = payload.timestamp || new Date().toISOString();
    // mark all pending groups as SKIPPED if they never ran, else SUCCESS
    (["A", "B", "C"] as SymbolGroup[]).forEach((g) => {
      if (next.groups[g].status === "PENDING" && next.groups[g].total === 0) next.groups[g].status = "SKIPPED";
      else if (next.groups[g].status === "RUNNING") next.groups[g].status = "SUCCESS";
    });
    this.state = { ...this.state, status: next, visibleGroups: ["A", "B", "C"] as SymbolGroup[], lastEvent: "PRECOMPUTATION_COMPLETED" };
    this.emit();
  }

  // SYMBOL_RESULT_UPDATED { symbol, group, armor_score, data_dri, is_unreliable } + full result if available
  upsertResult(result: SymbolArmorResult) {
    const nextMap = new Map(this.state.results);
    // derive STALE
    const isStale = result.expires_at ? new Date(result.expires_at).getTime() < Date.now() : false;
    nextMap.set(result.symbol, { ...result, is_stale: isStale });
    this.state = { ...this.state, results: nextMap, lastEvent: "SYMBOL_RESULT_UPDATED" };
    this.emit();
  }

  // bulk upsert (e.g. from /api/dashboard/ready)
  setResults(results: SymbolArmorResult[]) {
    const nextMap = new Map(this.state.results);
    for (const r of results) {
      const isStale = r.expires_at ? new Date(r.expires_at).getTime() < Date.now() : false;
      nextMap.set(r.symbol, { ...r, is_stale: isStale });
    }
    this.state = { ...this.state, results: nextMap };
    this.emit();
  }

  clearResults() {
    this.state = { ...this.state, results: new Map() };
    this.emit();
  }

  setWsConnected(connected: boolean) {
    this.state = { ...this.state, wsConnected: connected };
    this.emit();
  }

  setPolling(polling: boolean) {
    this.state = { ...this.state, isPolling: polling };
    this.emit();
  }

  setError(error: string | null) {
    this.state = { ...this.state, error };
    this.emit();
  }

  reset() {
    this.state = {
      status: null,
      results: new Map(),
      wsConnected: false,
      isPolling: false,
      error: null,
      lastEvent: null,
      visibleGroups: [],
    };
    this.emit();
  }

  // selectors
  getResultsByGroup(group: SymbolGroup): SymbolArmorResult[] {
    return Array.from(this.state.results.values()).filter((r) => r.group === group);
  }

  getAllResults(): SymbolArmorResult[] {
    return Array.from(this.state.results.values());
  }
}

// singleton
let _store: PrecomputeStore | null = null;

export function getPrecomputeStore(): PrecomputeStore {
  if (!_store) _store = new PrecomputeStore();
  return _store;
}

// React hook — Zustand-like ergonomics
export function usePrecomputeStore<T>(selector: (state: PrecomputeStoreState) => T): T {
  const store = getPrecomputeStore();
  return useSyncExternalStore(store.subscribe, () => selector(store.getSnapshot()), () => selector(store.getSnapshot()));
}

// Convenience selectors
export function usePrecomputeStatusState() {
  return usePrecomputeStore((s) => s.status);
}
export function usePrecomputeResults() {
  return usePrecomputeStore((s) => s.results);
}
export function useVisibleGroups() {
  return usePrecomputeStore((s) => s.visibleGroups ?? []);
}

export default getPrecomputeStore;
