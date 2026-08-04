"use client";

import { useEffect } from "react";

/**
 * Top-level error boundary — replaces the entire root layout when a
 * catastrophic error occurs (e.g. inside layout.tsx or Providers).
 *
 * Unlike `error.tsx`, this file must render its own <html>/<body> because
 * the root layout itself may have failed.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[GlobalErrorBoundary]", error);
  }, [error]);

  return (
    <html lang="fa" dir="rtl">
      <body className="bg-surface-950">
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center">
            <div className="text-6xl mb-6" aria-hidden="true">⚠️</div>
            <h1 className="text-xl font-bold text-surface-50 mb-3">
              خطای غیرمنتظره
            </h1>
            <p className="text-sm text-surface-400 leading-relaxed mb-8">
              خطایی جدی رخ داد. لطفاً دوباره تلاش کنید.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={reset}
                className="px-6 py-2.5 rounded-xl bg-primary-600 text-white text-sm font-medium hover:bg-primary-500 transition-colors"
              >
                🔄 تلاش مجدد
              </button>
              <button
                onClick={() => { window.location.href = "/"; }}
                className="px-6 py-2.5 rounded-xl bg-surface-800 text-surface-200 text-sm font-medium hover:bg-surface-700 transition-colors"
              >
                🏠 صفحه اصلی
              </button>
            </div>
            {error?.digest ? (
              <p className="mt-8 text-[11px] text-surface-600 font-mono">
                کد خطا: {error.digest}
              </p>
            ) : null}
          </div>
        </div>
      </body>
    </html>
  );
}
