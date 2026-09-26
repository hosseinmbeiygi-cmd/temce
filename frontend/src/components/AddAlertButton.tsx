"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

interface AddAlertButtonProps {
  symbol: string;
  market?: string;
  timeframe?: string;
  /** DB-backed signal id (new pipeline). When present -> POST /alerts/from-signal */
  signalId?: string;
  /** Numeric levels for orchestrator signals (strings like entry_zone/targets are ranges) */
  entry?: number;
  takeProfit?: number;
  stopLoss?: number;
  direction?: string;
  instrumentId?: string;
  compact?: boolean;
}

/**
 * One-click "add to alerts" usable from EVERY section (signals, funds, gold,
 * options, commodity, market-watch...). Creates TP + SL alerts when levels are
 * known, otherwise a single price alert at the current price.
 */
export default function AddAlertButton({
  symbol,
  market = "",
  timeframe = "",
  signalId,
  entry,
  takeProfit,
  stopLoss,
  direction = "buy",
  instrumentId = "",
  compact = false,
}: AddAlertButtonProps) {
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");

  async function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (state === "saving" || state === "done") return;
    setState("saving");
    try {
      if (signalId) {
        await apiPost("/alerts/from-signal", { signal_id: signalId, channels: ["console"] });
      } else {
        const jobs: Promise<unknown>[] = [];
        const base = { symbol, instrument_id: instrumentId, market, timeframe, channels: ["console"] };
        if (takeProfit && takeProfit > 0) {
          jobs.push(
            apiPost("/alerts/", {
              ...base,
              alert_type: direction === "sell" ? "price_below" : "price_above",
              condition: { field: "price", operator: direction === "sell" ? "lte" : "gte", threshold: takeProfit },
              description: `هدف ${symbol}`,
            })
          );
        }
        if (stopLoss && stopLoss > 0) {
          jobs.push(
            apiPost("/alerts/", {
              ...base,
              alert_type: direction === "sell" ? "price_above" : "price_below",
              condition: { field: "price", operator: direction === "sell" ? "gte" : "lte", threshold: stopLoss },
              description: `حد ضرر ${symbol}`,
            })
          );
        }
        if (jobs.length === 0) {
          const ref = entry && entry > 0 ? entry : undefined;
          if (ref === undefined) throw new Error("no-level");
          jobs.push(
            apiPost("/alerts/", {
              ...base,
              alert_type: "price_above",
              condition: { field: "price", operator: "gte", threshold: ref },
              description: `هشدار قیمت ${symbol}`,
            })
          );
        }
        await Promise.all(jobs);
      }
      setState("done");
    } catch {
      setState("error");
      setTimeout(() => setState("idle"), 2500);
    }
  }

  const label =
    state === "done" ? "✓ در هشدارها" : state === "saving" ? "..." : state === "error" ? "خطا! مجدد" : "+ هشدار";

  return (
    <button
      type="button"
      onClick={handleClick}
      title="افزودن به هشدارها"
      className={
        compact
          ? `text-[10px] px-1.5 py-0.5 rounded-full border transition-all ${
              state === "done"
                ? "border-accent-emerald/40 text-accent-emerald"
                : "border-surface-600/40 text-surface-400 hover:border-primary-500/40 hover:text-primary-300"
            }`
          : `text-[11px] px-2.5 py-1 rounded-lg border transition-all ${
              state === "done"
                ? "border-accent-emerald/40 text-accent-emerald"
                : "border-surface-600/40 text-surface-300 hover:border-primary-500/40 hover:text-primary-300"
            }`
      }
    >
      {label}
    </button>
  );
}
