'use client';
import { useEffect, useRef, useState, useMemo } from 'react';
import { getStoredAccessToken } from '@/lib/api';
import { fetchWsTicket } from '@/lib/wsTicket';

interface MarketPrice {
  symbol: string;
  price: number;
  change?: number;
  change_percent?: number;
  volume?: number;
  timestamp?: number;
}

interface UseMarketWebSocketReturn {
  prices: Map<string, MarketPrice>;
  connected: boolean;
  /** True when the socket is open but no fresh message has arrived. */
  stale: boolean;
  /** Epoch ms of the last accepted price message (null before the first). */
  lastMessageAt: number | null;
  error: string | null;
}

/** The market socket pushes a price every few seconds; 30s of silence is stale. */
export const MARKET_WS_STALE_MS = 30_000;

export interface SymbolPriceUpdate {
  symbol: string;
  price?: number;
  price_change_pct?: number;
  change_pct?: number;
  change?: number;
  change_percent?: number;
  volume?: number;
  value?: number;
  timestamp?: number;
}

/**
 * Handshake URL. FE-06: only the single-use ticket goes in the query string —
 * the access token must never appear here (it leaks into access/proxy logs and
 * browser history). Non-browser clients can still send a bearer header.
 */
function _getWsUrl(ticket: string | null): string {
  const suffix = ticket ? `?ticket=${encodeURIComponent(ticket)}` : '';
  if (typeof window === 'undefined') return `ws://localhost:8000/api/v1/ws/market${suffix}`;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
  // If NEXT_PUBLIC_API_URL is absolute (http://host:8000/api/v1), derive WS from it.
  if (apiUrl.startsWith('http://') || apiUrl.startsWith('https://')) {
    try {
      const u = new URL(apiUrl);
      const wsProto = u.protocol === 'https:' ? 'wss:' : 'ws:';
      // apiUrl is expected to end with /api/v1 (or /api/v1/); keep that prefix.
      const basePath = u.pathname.replace(/\/$/, '') || '/api/v1';
      return `${wsProto}//${u.host}${basePath}/ws/market${suffix}`;
    } catch {
      // fall through to host:8000 fallback
    }
  }
  // Default dev fallback: Next.js rewrites proxy HTTP but NOT WebSocket, so
  // connecting WS to window.location.host (Next.js on :3000) always closes
  // with 1006. Connect directly to the API on :8000 instead.
  const host = window.location.hostname || 'localhost';
  const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProto}//${host}:8000/api/v1/ws/market${suffix}`;
}

const MAX_RECONNECT_DELAY = 30000;
const BASE_RECONNECT_DELAY = 1000;

export function useMarketWebSocket(symbols: string[]): UseMarketWebSocketReturn {
  const [prices, setPrices] = useState<Map<string, MarketPrice>>(new Map());
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(BASE_RECONNECT_DELAY);
  const symbolsRef = useRef(symbols);
  const prevSymbolsRef = useRef(symbols);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5_000);
    return () => clearInterval(id);
  }, []);

  const stale =
    connected && (lastMessageAt === null || now - lastMessageAt > MARKET_WS_STALE_MS);

  // Keep the latest subscribed symbols available to socket handlers and send
  // subscribe/unsubscribe deltas when the caller changes the symbol list.
  // (Synced in an effect so we never write to a ref during render.)
  useEffect(() => {
    const previous = prevSymbolsRef.current;
    const ws = wsRef.current;
    if (ws && ws.readyState === 1) {
      const removed = previous.filter((s) => !symbols.includes(s));
      const added = symbols.filter((s) => !previous.includes(s));
      if (removed.length > 0) {
        ws.send(JSON.stringify({ action: 'unsubscribe', symbols: removed }));
        // Audit FE-05: an unsubscribed symbol kept its last price forever and
        // still looked live — drop it when the caller stops watching it.
        setPrices((prev) => {
          if (!removed.some((s) => prev.has(s))) return prev;
          const next = new Map(prev);
          for (const s of removed) next.delete(s);
          return next;
        });
      }
      if (added.length > 0) {
        ws.send(JSON.stringify({ action: 'subscribe', symbols: added }));
      }
    }
    prevSymbolsRef.current = symbols;
    symbolsRef.current = symbols;
  }, [symbols]);

  useEffect(() => {
    let disposed = false;
    // Monotonic attempt id: an in-flight ticket request must not open a socket
    // after a newer connect()/teardown has superseded it.
    let connectSeq = 0;

    function closeSocket() {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      const ws = wsRef.current;
      wsRef.current = null;
      if (!ws) return;
      // Detach message/error/close handlers so a stale socket can never touch
      // state. `onopen` stays attached so a socket that was closed while still
      // CONNECTING (e.g. React StrictMode dev remount) is detected in onopen
      // and shut down there — calling close() on a CONNECTING socket makes the
      // browser log "WebSocket is closed before the connection is established".
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CLOSING) {
        ws.close();
      }
    }

    function scheduleReconnect() {
      reconnectDelayRef.current = Math.min(
        reconnectDelayRef.current * 2,
        MAX_RECONNECT_DELAY
      );
      reconnectTimerRef.current = setTimeout(() => {
        if (!disposed) connect();
      }, reconnectDelayRef.current);
    }

    function connect() {
      closeSocket();
      const seq = ++connectSeq;

      // No session (anonymous visitor, or AUTH_DISABLED): dial directly. The
      // backend accepts an unauthenticated handshake only in that mode.
      if (!getStoredAccessToken()) {
        openSocket(null);
        return;
      }

      // FE-06: trade the access token for a single-use ticket; the token
      // itself never enters the handshake URL.
      void fetchWsTicket()
        .then((ticket) => {
          if (disposed || seq !== connectSeq) return;
          if (!ticket) {
            setError('WebSocket ticket unavailable');
            scheduleReconnect();
            return;
          }
          openSocket(ticket);
        })
        .catch((err: unknown) => {
          if (disposed || seq !== connectSeq) return;
          setError(err instanceof Error ? err.message : 'Failed to obtain WebSocket ticket');
          scheduleReconnect();
        });
    }

    function openSocket(ticket: string | null) {
      try {
        const ws = new WebSocket(_getWsUrl(ticket));
        wsRef.current = ws;

        ws.onopen = () => {
          // Stale socket from a previous effect run (React StrictMode in dev):
          // the handshake completed after it was abandoned, so shut it down
          // silently without touching state.
          if (wsRef.current !== ws) {
            ws.close();
            return;
          }
          setConnected(true);
          setError(null);
          reconnectDelayRef.current = BASE_RECONNECT_DELAY;

          // Subscribe to requested symbols
          ws.send(JSON.stringify({
            action: 'subscribe',
            symbols: symbolsRef.current,
          }));
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const updates: MarketPrice[] = Array.isArray(data) ? data : data.prices || [data];
            const accepted = updates.filter((update) => update.symbol);
            if (accepted.length === 0) return;
            setLastMessageAt(Date.now());
            setPrices((prev) => {
              const next = new Map(prev);
              for (const update of accepted) {
                const serverTimestamp =
                  typeof update.timestamp === 'number' ? update.timestamp : Date.now();
                const previous = next.get(update.symbol);
                // Audit FE-05: a replayed/older frame must not overwrite a
                // newer price ("last write wins" let stale data look live).
                if (previous?.timestamp != null && serverTimestamp < previous.timestamp) {
                  continue;
                }
                next.set(update.symbol, {
                  ...previous,
                  ...update,
                  timestamp: serverTimestamp,
                });
              }
              return next;
            });
          } catch {
            // Ignore malformed messages
          }
        };

        ws.onclose = () => {
          setConnected(false);
          // Exponential backoff reconnect
          scheduleReconnect();
        };

        ws.onerror = () => {
          setError('WebSocket connection error');
        };
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect');
        // Schedule reconnect
        scheduleReconnect();
      }
    }

    connect();
    return () => {
      disposed = true;
      closeSocket();
    };
  }, []);

  return { prices, connected, stale, lastMessageAt, error };
}

/**
 * Convenience hook that returns live prices as a plain object keyed by symbol,
 * plus connection state. Used by the ticker tape and other lightweight widgets
 * that want to merge WS updates into rendered cells.
 */
export function useSymbolPrices(symbols: string[]): {
  prices: Record<string, SymbolPriceUpdate>;
  connected: boolean;
  stale: boolean;
  lastMessageAt: number | null;
} {
  const { prices, connected, stale, lastMessageAt } = useMarketWebSocket(symbols);

  const pricesObj = useMemo(() => {
    const out: Record<string, SymbolPriceUpdate> = {};
    prices.forEach((p, symbol) => {
      out[symbol] = {
        symbol,
        price: p.price,
        price_change_pct: p.change_percent ?? p.change ?? 0,
        change_pct: p.change_percent ?? p.change ?? 0,
        change: p.change,
        change_percent: p.change_percent,
        volume: p.volume,
        timestamp: p.timestamp,
      };
    });
    return out;
  }, [prices]);

  return { prices: pricesObj, connected, stale, lastMessageAt };
}
