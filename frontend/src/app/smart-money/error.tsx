"use client";

import Link from "next/link";
import { useEffect } from "react";

/** Route-level error boundary for the smart-money section (incl. monitor). */
export default function SmartMoneyError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[SmartMoneyError]", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center">
        <div className="text-6xl mb-6" aria-hidden="true">⚠️</div>
        <h1 className="text-xl font-bold text-surface-50 mb-3">
          خطا در بخش هوشمند پول
        </h1>
        <p className="text-sm text-surface-400 leading-relaxed mb-8">
          در بارگذاری این بخش مشکلی پیش آمد. دوباره تلاش کنید.
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="px-6 py-2.5 rounded-xl bg-primary-600 text-white text-sm font-medium hover:bg-primary-500 transition-colors"
          >
            🔄 تلاش مجدد
          </button>
          <Link
            href="/smart-money"
            className="px-6 py-2.5 rounded-xl bg-surface-800 text-surface-200 text-sm font-medium hover:bg-surface-700 transition-colors"
          >
            🏠 هوشمند پول
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
