"use client";

import { CircleAlert, Clock3, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { apiErrorUserMessage, isAbortError } from "@/lib/api-errors";
import { DEFAULT_FRESHNESS_MS, isDataAsOfFresh, parseIsoInstant } from "@/lib/api-envelope";

interface LiveDataState {
  isLive: boolean;
  isError: boolean;
  isLoading: boolean;
  /** Data exists even if it is stale/unknown (``isLive`` kept for legacy callers). */
  hasData?: boolean;
  /** Known timestamp inside the freshness window. */
  isFresh?: boolean;
  /** Known timestamp outside the freshness window. */
  isStale?: boolean;
  /** `data_as_of` پاکت؛ اگر بدهید، دادهٔ زندهٔ کهنه هم اعلام می‌شود. */
  dataAsOf?: string | null;
  /** Transport error, when the caller has it — drives timeout/auth copy. */
  error?: unknown;
}

function clockLabel(iso: string): string {
  // `data_as_of` از بک‌اند naive-UTC است؛ `new Date(iso)` آن را زمان محلی
  // مرورگر می‌خواند و ساعت را ۳:۳۰ (یا offset محلی) عقب نشان می‌دهد.
  const instant = parseIsoInstant(iso);
  if (instant === null) return iso;
  return new Date(instant).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Explicit degraded-state banner for widgets fed by the live hooks in
 * `useMarketData`. Hooks NEVER substitute mock data silently; whenever
 * `isLive` is false (after loading) this banner must tell the user why the
 * section is empty instead of rendering fake numbers.
 *
 * Renders nothing while the first load is in progress or when live data is
 * present, so healthy dashboards are unaffected.
 */
export default function LiveDataBanner({ state }: { state: LiveDataState }) {
  if (state.isLoading) return null;
  const hasData = state.hasData ?? state.isLive;
  // Backwards compatible fallback for callers that only pass isLive + dataAsOf.
  const isStale =
    state.isStale ??
    (hasData &&
      state.dataAsOf != null &&
      !isDataAsOfFresh(state.dataAsOf, { thresholdMs: DEFAULT_FRESHNESS_MS }));
  const isFresh = state.isFresh ?? (hasData && !isStale);

  if (state.isError) {
    // A cancelled request is not a market failure — show nothing for it.
    if (state.error != null && isAbortError(state.error)) return null;
    const detail = state.error != null ? apiErrorUserMessage(state.error, "") : "";
    return (
      <Banner tone="error">
        <WifiOff className="size-3.5 shrink-0" aria-hidden />
        {detail || "ارتباط با سرور برقرار نشد — داده‌های زنده در دسترس نیستند."}
      </Banner>
    );
  }
  if (!hasData) {
    return (
      <Banner tone="muted">
        <CircleAlert className="size-3.5 shrink-0" aria-hidden />
        داده زنده‌ای از سرور دریافت نشد — این بخش تا بازگشت داده خالی می‌ماند.
      </Banner>
    );
  }
  if (state.dataAsOf == null && state.isStale !== true && state.isFresh !== true) {
    // Audit FE-04: feeds whose endpoint carries no source timestamp cannot be
    // judged fresh or stale. A permanent "unknown" banner on every such widget
    // was alarm fatigue; with nothing to compare there is no claim to make.
    return null;
  }
  if (isStale) {
    return (
      <Banner tone="muted">
        <Clock3 className="size-3.5 shrink-0" aria-hidden />
        آخرین به‌روزرسانی داده {clockLabel(state.dataAsOf ?? "")} بوده و قدیمی است — اعداد ممکن است دیگر معتبر نباشند.
      </Banner>
    );
  }
  if (!isFresh) {
    return (
      <Banner tone="muted">
        <CircleAlert className="size-3.5 shrink-0" aria-hidden />
        داده نمایش داده می‌شود، اما زمان به‌روزرسانی آن از سرور مشخص نیست.
      </Banner>
    );
  }
  return null;
}

function Banner({ tone, children }: { tone: "error" | "muted"; children: ReactNode }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`mb-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] font-medium ${
        tone === "error"
          ? "border-amber-500/40 bg-amber-500/10 text-amber-500"
          : "border-line bg-soft/60 text-ink-3"
      }`}
    >
      {children}
    </div>
  );
}
