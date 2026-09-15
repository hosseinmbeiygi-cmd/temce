"use client";

/**
 * usePrecomputeStatus — Armor Dashboard
 * ======================================
 * WebSocket hook for live precomputation progress with Fallback Polling.
 * - Connects to ws://host:8000/api/v1/ws/precompute (or /ws/precompute via NEXT_PUBLIC_API_URL)
 * - Falls back to polling GET /api/v1/precompute/status every 3s when WS is disconnected
 * - Parses contracts/events.md events: PRECOMPUTATION_PROGRESS / GROUP_COMPLETED / COMPLETED / SYMBOL_RESULT_UPDATED
 * - Feeds getPrecomputeStore() and triggers SoundEffectManager on COMPLETED
 *
 * Reuses patterns from frontend/src/hooks/useWebSocket.ts (reconnect backoff, StrictMode-safe close).
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { apiGet } from "@/lib/api";
import { getPrecomputeStore, type PrecomputeStatus, type SymbolArmorResult } from "@/stores/precomputeStore";
import { getSoundManager } from "@/lib/sound/SoundEffectManager";

// ── WS URL helper ──────────────────────────────────────────────
const DEFAULT_API_BASE_PATH = "/api/v1";
const LOCAL_API_PORT = "8000";

export interface PrecomputeWsUrlInput {
  /** NEXT_PUBLIC_WS_URL — explicit override, wins over everything else. */
  explicitWsUrl?: string;
  /** NEXT_PUBLIC_API_URL — may be relative ("/api/v1") or absolute ("https://api.example.com/api/v1"). */
  apiBaseUrl?: string;
  hostname: string;
  /** window.location.host — hostname + port, used for the same-origin path. */
  host: string;
  protocol: string;
}

/**
 * Resolve the Armor precompute WebSocket URL.
 *
 * Priority:
 *  1. NEXT_PUBLIC_WS_URL (explicit)
 *  2. Derived from an absolute NEXT_PUBLIC_API_URL
 *  3. Localhost dev → direct backend port (Next rewrites do not proxy WS upgrades)
 *  4. Otherwise same-origin, so a reverse proxy can upgrade it and the strict
 *     production CSP (`connect-src 'self'`) does not block the socket.
 *
 * Every branch is covered by the polling fallback, so a wrong guess degrades
 * to a 3s poll rather than a dead dashboard.
 */
export function buildPrecomputeWsUrl(input: PrecomputeWsUrlInput): string {
  const { explicitWsUrl, apiBaseUrl, hostname, host, protocol } = input;
  if (explicitWsUrl) return explicitWsUrl;

  if (apiBaseUrl && (apiBaseUrl.startsWith("http://") || apiBaseUrl.startsWith("https://"))) {
    try {
      const u = new URL(apiBaseUrl);
      const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
      const basePath = u.pathname.replace(/\/$/, "") || DEFAULT_API_BASE_PATH;
      return `${wsProto}//${u.host}${basePath}/ws/precompute`;
    } catch {
      // fall through to the browser-derived candidates
    }
  }

  const wsProto = protocol === "https:" ? "wss:" : "ws:";
  const isLocalHost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1" || hostname === "[::1]";
  if (isLocalHost) return `${wsProto}//${hostname}:${LOCAL_API_PORT}${DEFAULT_API_BASE_PATH}/ws/precompute`;

  return `${wsProto}//${host}${DEFAULT_API_BASE_PATH}/ws/precompute`;
}

function getPrecomputeWsUrl(): string {
  if (typeof window === "undefined") return `ws://localhost:${LOCAL_API_PORT}${DEFAULT_API_BASE_PATH}/ws/precompute`;
  return buildPrecomputeWsUrl({
    explicitWsUrl: process.env.NEXT_PUBLIC_WS_URL,
    apiBaseUrl: process.env.NEXT_PUBLIC_API_URL,
    hostname: window.location.hostname || "localhost",
    host: window.location.host || `localhost:${LOCAL_API_PORT}`,
    protocol: window.location.protocol,
  });
}

const WS_URL = typeof window !== "undefined" ? getPrecomputeWsUrl() : `ws://localhost:${LOCAL_API_PORT}${DEFAULT_API_BASE_PATH}/ws/precompute`;

const MAX_RECONNECT_DELAY = 30000;
const BASE_RECONNECT_DELAY = 1000;
const POLL_INTERVAL_MS = 3000;
const POLL_WHEN_WS_UP_MS = 15000; // lightweight health poll even when WS connected

// ── Event payload types (contracts/events.md) ──────────────────
interface ProgressPayload {
  group: "A" | "B" | "C";
  completed: number;
  total: number;
  percent: number;
  current_symbol: string;
}
interface GroupCompletedPayload {
  group: "A" | "B" | "C";
  total_processed: number;
  failed: number;
  timestamp: string;
}
interface CompletedPayload {
  total: number;
  success: number;
  failed: number;
  avg_dri: number;
  duration_seconds: number;
  timestamp: string;
}
interface SymbolUpdatedPayload {
  symbol: string;
  group: "A" | "B" | "C";
  armor_score: number;
  data_dri: number;
  is_unreliable: boolean;
}

// ── Hook return ────────────────────────────────────────────────
export interface UsePrecomputeStatusReturn {
  status: PrecomputeStatus | null;
  wsConnected: boolean;
  isPolling: boolean;
  error: string | null;
  triggerStart: () => Promise<void>;
  refresh: () => Promise<void>;
}

// ── Polling fetchers ───────────────────────────────────────────
async function fetchStatus(): Promise<PrecomputeStatus | null> {
  try {
    const res = await apiGet<{ success?: boolean; data?: PrecomputeStatus } | PrecomputeStatus>("/precompute/status");
    // backend may wrap in {success, data} or return raw
    const raw = (res as unknown as { data?: PrecomputeStatus })?.data ?? (res as PrecomputeStatus);
    if (raw && typeof raw.progress_percent === "number") return raw as PrecomputeStatus;
    return null;
  } catch {
    return null;
  }
}

async function fetchReady(): Promise<SymbolArmorResult[]> {
  try {
    const res = await apiGet<{ success?: boolean; data?: SymbolArmorResult[] } | SymbolArmorResult[]>("/dashboard/ready");
    const arr = (res as unknown as { data?: unknown })?.data ?? res;
    if (Array.isArray(arr)) return arr as SymbolArmorResult[];
    if (arr && typeof arr === "object" && Array.isArray((arr as { items?: unknown[] }).items)) {
      return (arr as { items: SymbolArmorResult[] }).items;
    }
    return [];
  } catch {
    return [];
  }
}

// ── Main hook ──────────────────────────────────────────────────
export function usePrecomputeStatus(options?: { autoConnect?: boolean; pollWhenHidden?: boolean }): UsePrecomputeStatusReturn {
  const autoConnect = options?.autoConnect ?? true;
  const store = getPrecomputeStore();
  const [wsConnected, setWsConnected] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep status in sync via store subscription
  const [status, setStatus] = useState<PrecomputeStatus | null>(() => store.getSnapshot().status);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(BASE_RECONNECT_DELAY);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const disposedRef = useRef(false);
  // First successful poll always hydrates results from the Hot cache, even when
  // the persisted job status is PENDING (e.g. backend restarted but Redis still
  // holds the previous run). Without this the grid renders "nothing computed yet"
  // while valid cached symbols exist.
  const hydratedRef = useRef(false);

  // Subscribe to store status changes
  useEffect(() => {
    const unsub = store.subscribe(() => {
      setStatus(store.getSnapshot().status);
      setWsConnected(store.getSnapshot().wsConnected);
      setIsPolling(store.getSnapshot().isPolling);
      setError(store.getSnapshot().error);
    });
    // initial sync
    setStatus(store.getSnapshot().status);
    return unsub;
  }, [store]);

  // ── Polling ──────────────────────────────────────────────────
  const doPoll = useCallback(async () => {
    const s = await fetchStatus();
    if (s) {
      store.setStatus(s);
      // also fetch ready results if completed or to hydrate progressive grid
      if (!hydratedRef.current || s.overall_status === "SUCCESS" || s.progress_percent > 0) {
        const ready = await fetchReady();
        if (ready.length > 0) store.setResults(ready);
        hydratedRef.current = true;
      }
    }
  }, [store]);

  const startPolling = useCallback(
    (intervalMs: number) => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      store.setPolling(true);
      setIsPolling(true);
      // immediate fetch
      void doPoll();
      pollTimerRef.current = setInterval(() => {
        if (disposedRef.current) return;
        void doPoll();
      }, intervalMs);
    },
    [doPoll, store]
  );

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    store.setPolling(false);
    setIsPolling(false);
  }, [store]);

  // ── WS message handler ───────────────────────────────────────
  const handleMessage = useCallback(
    (raw: string) => {
      let msg: { type?: string; event?: string; payload?: unknown; data?: unknown };
      try {
        msg = JSON.parse(raw);
      } catch {
        return;
      }
      // Support both {type, payload} and {event, data} envelopes, plus bare payload with group field
      const declaredType = typeof msg.type === "string" ? msg.type : typeof msg.event === "string" ? msg.event : "";
      const bareGroup = (msg as unknown as { group?: unknown }).group;
      const type: string = declaredType || (typeof bareGroup === "string" ? "PRECOMPUTATION_PROGRESS" : "");
      const payload: unknown = msg.payload ?? msg.data ?? msg;

      if (!type && payload && typeof payload === "object" && "percent" in (payload as Record<string, unknown>)) {
        // Bare progress payload without envelope
        store.applyProgress(payload as ProgressPayload);
        return;
      }

      switch (type) {
        case "PRECOMPUTATION_STATUS_SNAPSHOT": {
          // Emitted by api/ws_manager.py right after (re)connect, and re-broadcast
          // by api/job_state.save_status on EVERY state change (the live-funnel
          // design: raw worker events first, then the recomputed snapshot).
          // Restores status and re-hydrates the grid, because
          // SYMBOL_RESULT_UPDATED events that fired while the socket was down
          // are otherwise lost.
          const snap = (payload ?? msg) as PrecomputeStatus;
          if (snap && typeof snap.progress_percent === "number") {
            store.setStatus(snap);
            void fetchReady().then((rows) => {
              if (rows.length > 0) store.setResults(rows);
            });
          }
          break;
        }
        case "PRECOMPUTATION_STARTED": {
          // The funnel flow really starts here: the API broadcasts STARTED right
          // after the dispatcher goes live.  Reset to a RUNNING state so a
          // previous run's SUCCESS/FAILED banner and counters cannot leak into
          // the new run — subsequent PROGRESS / GROUP_COMPLETED / SYMBOL events
          // then land on a clean slate.  Hydrated results from the hot cache
          // are kept (they remain valid for the grid), only job state resets.
          // (patchStatus stamps last_update client-side; the STARTED timestamp
          // only matters for server-side bookkeeping)
          store.patchStatus({
            overall_status: "RUNNING",
            current_group: "A",
            current_symbol: null,
            progress_percent: 0,
            completed_symbols: 0,
            failed_symbols: 0,
            estimated_remaining_seconds: null,
          });
          hydratedRef.current = false; // next SUCCESS poll re-hydrates from the fresh hot cache
          break;
        }
        case "PRECOMPUTATION_PROGRESS": {
          store.applyProgress(payload as ProgressPayload);
          break;
        }
        case "PRECOMPUTATION_GROUP_COMPLETED": {
          store.applyGroupCompleted(payload as GroupCompletedPayload);
          // subtle sound for non-C groups
          try {
            getSoundManager().onGroupCompleted((payload as GroupCompletedPayload).group);
          } catch {
            // ignore
          }
          break;
        }
        case "PRECOMPUTATION_COMPLETED": {
          store.applyCompleted(payload as CompletedPayload);
          try {
            getSoundManager().onPrecomputationCompleted();
          } catch {
            // ignore
          }
          // on completion, fetch ready symbols to hydrate grid
          void fetchReady().then((rows) => {
            if (rows.length > 0) store.setResults(rows);
          });
          break;
        }
        case "SYMBOL_RESULT_UPDATED": {
          const p = payload as SymbolUpdatedPayload & Partial<SymbolArmorResult>;
          // If full result is in payload, use it; otherwise construct minimal row
          if (p.armor_score !== undefined) {
            const existing = store.getSnapshot().results.get(p.symbol);
            const merged: SymbolArmorResult = {
              symbol: p.symbol,
              group: p.group,
              armor_score: p.armor_score,
              data_dri: p.data_dri,
              is_unreliable: p.is_unreliable,
              last_price: (p as unknown as { last_price?: number }).last_price ?? existing?.last_price ?? 0,
              closing_price: (p as unknown as { closing_price?: number }).closing_price ?? existing?.closing_price ?? 0,
              technical_score: (p as unknown as { technical_score?: number }).technical_score ?? existing?.technical_score ?? 0,
              liquidity_score: (p as unknown as { liquidity_score?: number }).liquidity_score ?? existing?.liquidity_score ?? 0,
              money_flow_score: (p as unknown as { money_flow_score?: number }).money_flow_score ?? existing?.money_flow_score ?? 0,
              red_flags: (p as unknown as { red_flags?: string[] }).red_flags ?? existing?.red_flags ?? [],
              calculated_at: (p as unknown as { calculated_at?: string }).calculated_at ?? existing?.calculated_at ?? new Date().toISOString(),
              expires_at: (p as unknown as { expires_at?: string }).expires_at ?? existing?.expires_at ?? new Date(Date.now() + 3600_000).toISOString(),
              version: (p as unknown as { version?: string }).version ?? existing?.version ?? "v4.0",
            };
            store.upsertResult(merged);
          }
          break;
        }
        default: {
          // Unknown type — if payload looks like a status snapshot, apply it
          if (payload && typeof payload === "object" && "progress_percent" in (payload as Record<string, unknown>)) {
            store.setStatus(payload as PrecomputeStatus);
          }
          break;
        }
      }
    },
    [store]
  );

  // ── WS lifecycle ─────────────────────────────────────────────
  useEffect(() => {
    if (!autoConnect) return;
    disposedRef.current = false;

    function closeSocket() {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      const ws = wsRef.current;
      wsRef.current = null;
      if (!ws) return;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CLOSING) ws.close();
    }

    function scheduleReconnect() {
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, MAX_RECONNECT_DELAY);
      reconnectTimerRef.current = setTimeout(() => {
        if (!disposedRef.current) connect();
      }, reconnectDelayRef.current);
    }

    function connect() {
      closeSocket();
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (wsRef.current !== ws) {
            ws.close();
            return;
          }
          store.setWsConnected(true);
          setWsConnected(true);
          setError(null);
          store.setError(null);
          reconnectDelayRef.current = BASE_RECONNECT_DELAY;
          // When WS is up, keep a slow health poll; stop aggressive polling
          stopPolling();
          // Light poll as backup
          startPolling(POLL_WHEN_WS_UP_MS);
        };

        ws.onmessage = (event) => {
          const data = typeof event.data === "string" ? event.data : "";
          handleMessage(data);
        };

        ws.onclose = () => {
          store.setWsConnected(false);
          setWsConnected(false);
          // Fallback to aggressive polling
          stopPolling();
          startPolling(POLL_INTERVAL_MS);
          scheduleReconnect();
        };

        ws.onerror = () => {
          // error will be followed by close; set a soft error
          store.setError("WebSocket error — fallback to polling");
          setError("WebSocket error — fallback to polling");
        };
      } catch (err) {
        store.setError(err instanceof Error ? err.message : "WebSocket connect failed");
        setError(err instanceof Error ? err.message : "WebSocket connect failed");
        stopPolling();
        startPolling(POLL_INTERVAL_MS);
        scheduleReconnect();
      }
    }

    // Initial: start polling immediately (covers before WS connects), then try WS
    startPolling(POLL_INTERVAL_MS);
    connect();

    return () => {
      disposedRef.current = true;
      closeSocket();
      stopPolling();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [autoConnect, handleMessage, startPolling, stopPolling, store]);

  // ── Actions ──────────────────────────────────────────────────
  const triggerStart = useCallback(async () => {
    try {
      setError(null);
      store.setError(null);
      const res = await fetch(`${(process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "")}/precompute/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      // Kick a poll to reflect RUNNING quickly
      void doPoll();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to start precompute";
      setError(msg);
      store.setError(msg);
      throw e;
    }
  }, [doPoll, store]);

  const refresh = useCallback(async () => {
    await doPoll();
    const rows = await fetchReady();
    if (rows.length > 0) store.setResults(rows);
  }, [doPoll, store]);

  return { status, wsConnected, isPolling, error, triggerStart, refresh };
}

export default usePrecomputeStatus;
