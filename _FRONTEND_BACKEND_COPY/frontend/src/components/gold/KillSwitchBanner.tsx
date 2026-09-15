"use client";
import React from "react";
import type { KillSwitchResp } from "@/lib/goldApi";

interface Props {
  status: KillSwitchResp;
  className?: string;
}

/** بنر وضعیت بحرانی. در NORMAL چیزی نشان نمی‌دهد.
 *  در WARNING: نوار زرد. در ACTIVE: نوار قرمز چشمک‌زن با دایرکتیو. */
export function KillSwitchBanner({ status, className = "" }: Props) {
  if (status.status === "NORMAL") return null;

  if (status.status === "WARNING") {
    return (
      <div
        className={`rounded-lg ring-1 ring-amber-600/50 bg-amber-950/30 backdrop-blur px-4 py-3 text-amber-200 text-sm ${className}`}
        role="alert"
      >
        <span className="font-bold">⚡ هشدار نوسان:</span> {status.reason ?? "نوسان غیرعادی در بازار"}
      </div>
    );
  }

  // ACTIVE
  return (
    <div
      className={`rounded-lg ring-2 ring-rose-500/60 bg-rose-950/50 backdrop-blur px-4 py-3 text-rose-100 text-sm kill-switch-active ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="font-bold text-base">🚨 KILL-SITCH فعال — صدور سیگنال خرید متوقف شد</div>
          <div className="mt-1 text-rose-200/90">{status.reason}</div>
          {status.directive && (
            <div className="mt-2 text-xs text-rose-200/70">
              <span className="font-semibold">دستور:</span> {status.directive}
            </div>
          )}
          {status.active_rules.length > 0 && (
            <div className="mt-2 flex gap-1 flex-wrap">
              {status.active_rules.map((r) => (
                <span
                  key={r}
                  className="text-[10px] bg-rose-900/60 ring-1 ring-rose-700/40 rounded px-2 py-0.5"
                >
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>
        {status.triggered_at && (
          <div className="text-[10px] text-rose-300/60 whitespace-nowrap">
            {new Date(status.triggered_at).toLocaleTimeString("fa-IR")}
          </div>
        )}
      </div>
    </div>
  );
}
