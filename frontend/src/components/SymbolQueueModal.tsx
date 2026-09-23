"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import Skeleton from "@/components/Skeleton";

// ── Types ───────────────────────────────────────────────────────────

interface QueueSymbolData {
  symbol: string;
  name?: string;
  queue_status: "BUY_QUEUE" | "SELL_QUEUE" | "NONE";
  queue_volume_ratio: number;
  queue_days_streak: number;
  queue_type_change: string;
  distance_to_limit: number;
  last_price: number;
  limit_up?: number;
  limit_down?: number;
  queue_buy_volume?: number;
  queue_sell_volume?: number;
  interpretation?: Record<string, string>;
  adjustments?: Record<string, unknown>;
  final_decision?: string;
  override_reason?: string;
  [key: string]: unknown;
}

// ── Helpers ─────────────────────────────────────────────────────────

function statusColor(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "#10b981";
    case "SELL_QUEUE": return "#ef4444";
    default: return "#475569";
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "صف خرید 🟢";
    case "SELL_QUEUE": return "صف فروش 🔴";
    default: return "بدون صف ⚪";
  }
}

function typeChangeLabel(tc: string): string {
  switch (tc) {
    case "NEW_BUY_QUEUE": return "🟢 صف خرید جدید";
    case "NEW_SELL_QUEUE": return "🔴 صف فروش جدید";
    case "QUEUE_BROKEN": return "🟡 صف شکسته شد";
    default: return "";
  }
}

function typeChangeColor(tc: string): string {
  switch (tc) {
    case "NEW_BUY_QUEUE": return "#10b981";
    case "NEW_SELL_QUEUE": return "#ef4444";
    case "QUEUE_BROKEN": return "#f59e0b";
    default: return "#64748b";
  }
}

// ── Component ───────────────────────────────────────────────────────

interface SymbolQueueModalProps {
  symbol: string;
  onClose: () => void;
}

export default function SymbolQueueModal({ symbol, onClose }: SymbolQueueModalProps) {
  const [result, setResult] = useState<QueueSymbolData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Close on Escape ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // ── Fetch data ──
  useEffect(() => {
    let cancelled = false;
    // Set loading state synchronously on mount/symbol change; intentional UX pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    apiGet<QueueSymbolData>(`/queue-analysis/${encodeURIComponent(symbol)}`)
      .then((data) => {
        if (!cancelled) {
          setResult(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "خطا در دریافت اطلاعات");
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [symbol]);

  // ── Prevent row click from triggering ──
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={handleBackdropClick}
      dir="rtl"
    >
      <div className="relative w-full max-w-md rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl overflow-hidden">
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-800">
          <div className="flex items-center gap-2">
            <span className="material-icons text-primary-400 text-lg">move_up</span>
            <span className="text-sm font-bold text-surface-200">تحلیل صف</span>
            <span className="text-xs font-mono font-bold text-primary-300 bg-primary-600/10 px-2 py-0.5 rounded-lg">
              {symbol}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-800 transition-all"
          >
            <span className="material-icons text-sm">close</span>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="px-4 py-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full rounded-xl" />
              <Skeleton className="h-20 w-full rounded-xl" />
              <Skeleton className="h-12 w-3/4 rounded-xl" />
            </div>
          )}

          {error && (
            <div className="text-center py-6">
              <span className="material-icons text-2xl text-accent-rose mb-2">cloud_off</span>
              <p className="text-xs text-surface-500">{error}</p>
              <button
                onClick={onClose}
                className="mt-3 text-[10px] px-3 py-1.5 bg-surface-800 rounded-lg text-surface-400 hover:text-surface-200 transition-all"
              >
                بستن
              </button>
            </div>
          )}

          {result && !loading && (
            <div className="space-y-3">
              {/* ── Status Card ── */}
              <div
                className="rounded-xl p-3 border"
                style={{
                  borderColor: statusColor(result.queue_status) + "30",
                  backgroundColor: statusColor(result.queue_status) + "08",
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-surface-400">وضعیت صف</span>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white"
                    style={{ backgroundColor: statusColor(result.queue_status) }}
                  >
                    {statusLabel(result.queue_status)}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-[11px]">
                  <div>
                    <span className="text-surface-500">نسبت حجم صف: </span>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${(result.queue_volume_ratio * 100).toFixed(0)}%`,
                            backgroundColor: statusColor(result.queue_status),
                          }}
                        />
                      </div>
                      <span className="font-mono text-surface-200 font-bold">
                        {(result.queue_volume_ratio * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="text-surface-500">تداوم: </span>
                    <span className="font-mono text-surface-200 font-bold mr-1">
                      {result.queue_days_streak} روز
                    </span>
                  </div>
                </div>
              </div>

              {/* ── Details Grid ── */}
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="rounded-xl p-2.5 bg-surface-800/30 border border-surface-700/30">
                  <span className="text-surface-500">فاصله تا دامنه</span>
                  <div className="font-mono text-surface-200 font-bold mt-0.5">
                    {result.distance_to_limit.toFixed(1)}%
                  </div>
                </div>
                <div className="rounded-xl p-2.5 bg-surface-800/30 border border-surface-700/30">
                  <span className="text-surface-500">قیمت</span>
                  <div className="font-mono text-surface-200 font-bold mt-0.5">
                    {result.last_price?.toLocaleString("en-US")}
                  </div>
                </div>
                <div className="rounded-xl p-2.5 bg-surface-800/30 border border-surface-700/30">
                  <span className="text-surface-500">سقف دامنه</span>
                  <div className="font-mono text-surface-200 mt-0.5">
                    {result.limit_up?.toLocaleString("en-US") ?? "—"}
                  </div>
                </div>
                <div className="rounded-xl p-2.5 bg-surface-800/30 border border-surface-700/30">
                  <span className="text-surface-500">کف دامنه</span>
                  <div className="font-mono text-surface-200 mt-0.5">
                    {result.limit_down?.toLocaleString("en-US") ?? "—"}
                  </div>
                </div>
              </div>

              {/* ── Type Change ── */}
              {result.queue_type_change && result.queue_type_change !== "NO_CHANGE" && (
                <div
                  className="text-[10px] px-2.5 py-1.5 rounded-lg inline-flex items-center gap-1"
                  style={{
                    backgroundColor: typeChangeColor(result.queue_type_change) + "12",
                    color: typeChangeColor(result.queue_type_change),
                  }}
                >
                  {typeChangeLabel(result.queue_type_change)}
                </div>
              )}

              {/* ── Interpretation ── */}
              {result.interpretation && (
                <div className="space-y-0.5">
                  {Object.values(result.interpretation).map((text, i) => (
                    <div key={i} className="text-[10px] text-surface-400 flex items-start gap-1">
                      <span className="text-surface-600 mt-0.5">•</span>
                      <span>{text as string}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Override Warning ── */}
              {result.override_reason && (
                <div className="text-[10px] px-2.5 py-1.5 rounded-lg bg-accent-amber/10 text-accent-300 flex items-start gap-1.5">
                  <span className="material-icons text-xs mt-0.5">warning</span>
                  <span>{result.override_reason}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="px-4 py-2.5 border-t border-surface-800 flex items-center justify-between">
          <span className="text-[9px] text-surface-600">
            منبع: سامانه تحلیل صف هوشمند
          </span>
          <button
            onClick={onClose}
            className="text-[10px] px-3 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg transition-all"
          >
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
