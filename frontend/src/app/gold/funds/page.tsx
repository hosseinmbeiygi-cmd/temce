"use client";

import { useQuery } from "@tanstack/react-query";
import { getSnapshot, isServiceUnavailable } from "@/lib/goldApi";
import { FundNAVTable } from "@/components/gold/FundNAVTable";

/**
 * تب مستقل «صندوق‌های طلا».
 *
 * منبع داده همان snapshot سرور است که NAV/حباب هر صندوق را از
 * `gold_fund_nav` (Postgres) + قیمت بازار می‌سازد؛ صفحه قبلی فقط redirect به
 * `#funds` داشبورد بود و تب مستقلی نداشت. اینجا **همهٔ** صندوق‌های snapshot
 * (نه فقط چند مورد برتر) با همان جدول مشترک نمایش داده می‌شوند.
 */
export default function GoldFundsPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: getSnapshot,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  const funds = data?.funds ?? [];

  return (
    <div className="space-y-4" dir="rtl">
      <div>
        <h1 className="text-base font-bold" style={{ color: "var(--gd-text)" }}>
          صندوق‌های طلا
        </h1>
        <p className="text-xs mt-1" style={{ color: "var(--gd-text-2)" }}>
          همهٔ صندوق‌های طلا با NAV، قیمت بازار، حباب P/NAV، BPR و ورود خالص.
          {data ? ` (${funds.length.toLocaleString("fa-IR")} صندوق)` : ""}
        </p>
      </div>

      {isError && (
        <div
          role="alert"
          className="rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: "var(--gd-danger)", background: "var(--gd-bg-2)", color: "var(--gd-danger)" }}
        >
          {isServiceUnavailable(error)
            ? "سرویس دادهٔ طلا موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید."
            : "دریافت فهرست صندوق‌ها ناموفق بود."}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-xl p-6 text-center text-sm" style={{ background: "var(--gd-bg-2)", color: "var(--gd-text-2)" }}>
          در حال دریافت صندوق‌ها...
        </div>
      ) : (
        <FundNAVTable funds={funds} />
      )}
    </div>
  );
}
