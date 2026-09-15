"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

export interface BackfillState {
  status: "idle" | "running" | "done" | "cancelled" | "error";
  started_at: string | null;
  finished_at: string | null;
  total_symbols: number;
  processed: number;
  ok: number;
  fail: number;
  items: number;
  current_symbol: string | null;
  message: string | null;
  error: string | null;
}

export const IDLE_BACKFILL: BackfillState = {
  status: "idle",
  started_at: null,
  finished_at: null,
  total_symbols: 0,
  processed: 0,
  ok: 0,
  fail: 0,
  items: 0,
  current_symbol: null,
  message: null,
  error: null,
};

interface StartResponse {
  started: boolean;
  message: string;
}

interface CancelResponse {
  cancelled: boolean;
  message: string;
}

/**
 * Polls a server-side background backfill (e.g. the BrsApi full-market
 * candlestick / shareholder downloads) and exposes start / cancel actions.
 *
 * Long-running downloads are executed as `asyncio.create_task` on the API
 * server and polled here every 5s, so the UI never blocks on a multi-hour
 * request. State is re-synced on mount so a backfill that is already
 * running (e.g. after a page refresh) resumes live polling.
 */
export function useBackgroundBackfill(startUrl: string, statusUrl: string, cancelUrl: string) {
  const [backfill, setBackfill] = useState<BackfillState>(IDLE_BACKFILL);
  const pollRef = useRef<number | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async (): Promise<BackfillState | undefined> => {
    try {
      const res = await apiGet<{ success: boolean; data: BackfillState }>(statusUrl);
      if (res?.data) {
        setBackfill(res.data);
        if (["done", "cancelled", "error"].includes(res.data.status)) stopPoll();
      }
      return res?.data;
    } catch {
      return undefined;
    }
  }, [statusUrl, stopPoll]);

  const startPoll = useCallback(() => {
    stopPoll();
    pollRef.current = window.setInterval(fetchStatus, 5000);
  }, [stopPoll, fetchStatus]);

  // Stop polling on unmount
  useEffect(() => () => stopPoll(), [stopPoll]);

  // Re-sync with the server when the page mounts (a backfill may already
  // be running — resume live polling in that case).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional one-time mount sync with the running backfill task
    fetchStatus().then(data => {
      if (data?.status === "running") startPoll();
    });
  }, [fetchStatus, startPoll]);

  const startBackfill = useCallback(async (): Promise<StartResponse | undefined> => {
    try {
      const res = await apiPost<{ success: boolean; data: StartResponse }>(startUrl);
      setBackfill({ ...IDLE_BACKFILL, status: "running", message: "در حال راه‌اندازی..." });
      await fetchStatus();
      startPoll();
      return res?.data;
    } catch {
      return undefined;
    }
  }, [startUrl, fetchStatus, startPoll]);

  const cancelBackfill = useCallback(async (): Promise<string | undefined> => {
    try {
      const res = await apiPost<{ success: boolean; data: CancelResponse }>(cancelUrl);
      return res?.data?.message;
    } catch {
      return undefined;
    }
  }, [cancelUrl]);

  return { backfill, setBackfill, fetchStatus, startBackfill, cancelBackfill };
}
