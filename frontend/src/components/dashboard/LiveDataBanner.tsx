"use client";

import { CircleAlert, WifiOff } from "lucide-react";

interface LiveDataState {
  isLive: boolean;
  isError: boolean;
  isLoading: boolean;
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
  if (state.isLoading || state.isLive) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`mb-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] font-medium ${
        state.isError
          ? "border-amber-500/40 bg-amber-500/10 text-amber-500"
          : "border-line bg-soft/60 text-ink-3"
      }`}
    >
      {state.isError ? (
        <WifiOff className="size-3.5 shrink-0" aria-hidden />
      ) : (
        <CircleAlert className="size-3.5 shrink-0" aria-hidden />
      )}
      {state.isError
        ? "ارتباط با سرور برقرار نشد — داده‌های زنده در دسترس نیستند."
        : "داده زنده‌ای از سرور دریافت نشد — این بخش تا بازگشت داده خالی می‌ماند."}
    </div>
  );
}
