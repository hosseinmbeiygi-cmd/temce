"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * Route-level error boundary (Next.js App Router).
 *
 * Catches errors thrown while rendering any page under this segment and
 * shows a friendly, RTL Persian message with a "try again" action instead
 * of a blank/broken screen. Next.js automatically calls `reset()` when the
 * user clicks the retry button.
 *
 * Renders inside the existing root layout (no <html>/<body> here — that is
 * only for `global-error.tsx`).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to the console for debugging — do not leak details to the UI.
    console.error("[ErrorBoundary]", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-950 p-6">
      <div className="max-w-md w-full text-center">
        <div className="text-6xl mb-6" aria-hidden="true">⚠️</div>
        <h1 className="text-xl font-bold text-surface-50 mb-3">
          خطایی در نمایش این صفحه رخ داد
        </h1>
        <p className="text-sm text-surface-400 leading-relaxed mb-8">
          مشکلی پیش آمد اما دادههای شما در امان است. لطفاً دوباره تلاش
          کنید یا به صفحه اصلی بروید.
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="px-6 py-2.5 rounded-xl bg-primary-600 text-white text-sm font-medium hover:bg-primary-500 transition-colors"
          >
            🔄 تلاش مجدد
          </button>
          <Link
            href="/"
            className="px-6 py-2.5 rounded-xl bg-surface-800 text-surface-200 text-sm font-medium hover:bg-surface-700 transition-colors"
          >
            🏠 صفحه اصلی
          </Link>
        </div>
        {error?.digest ? (
          <p className="mt-8 text-[11px] text-surface-600 font-mono">
            کد خطا: {error.digest}
          </p>
        ) : null}
      </div>
    </div>
  );
}
