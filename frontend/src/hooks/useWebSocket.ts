'use client';
import { useEffect, useRef, useState, useMemo } from 'react';

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
  error: string | null;
}

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

const WS_URL = typeof window !== 'undefined'
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/market`
  : 'ws://localhost:8000/api/v1/ws/market';

const MAX_RECONNECT_DELAY = 30000;
const BASE_RECONNECT_DELAY = 1000;

export function useMarketWebSocket(symbols: string[]): UseMarketWebSocketReturn {
  const [prices, setPrices] = useState<Map<string, MarketPrice>>(new Map());
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(BASE_RECONNECT_DELAY);
  const symbolsRef = useRef(symbols);

  // Keep the latest subscribed symbols available to socket handlers.
  // (Synced in an effect so we never write to a ref during render.)
  useEffect(() => {
    symbolsRef.current = symbols;
  }, [symbols]);

  useEffect(() => {
    let disposed = false;

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

      try {
        const ws = new WebSocket(WS_URL);
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

            setPrices((prev) => {
              const next = new Map(prev);
              for (const update of updates) {
                if (update.symbol) {
                  next.set(update.symbol, {
                    ...next.get(update.symbol),
                    ...update,
                    timestamp: Date.now(),
                  });
                }
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

  return { prices, connected, error };
}

/**
 * Convenience hook that returns live prices as a plain object keyed by symbol,
 * plus connection state. Used by the ticker tape and other lightweight widgets
 * that want to merge WS updates into rendered cells.
 */
export function useSymbolPrices(symbols: string[]): {
  prices: Record<string, SymbolPriceUpdate>;
  connected: boolean;
} {
  const { prices, connected } = useMarketWebSocket(symbols);

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

  return { prices: pricesObj, connected };
}
