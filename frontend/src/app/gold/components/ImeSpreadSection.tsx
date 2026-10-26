"use client";

import { useQuery } from "@tanstack/react-query";
import { getArbitrage, isServiceUnavailable } from "@/lib/goldApi";
import { cn } from "@/lib/cn";

const fmtPct = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)}٪`;
};

export default function ImeSpreadSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "arbitrage"],
    queryFn: getArbitrage,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return <div className="text-center text-sm text-zinc-500">در حال محاسبهٔ اسپرد…</div>;
  }

  if (isError) {
    return (
      <div
        data-testid="ime-spread-error"
        className="text-center text-sm text-zinc-500"
      >
        {isServiceUnavailable(error)
          ? "سرویس اسپرد آربیتراژ موقتاً در دسترس نیست (۵۰۳)."
          : "اسپرد آربیتراژ IME در دسترس نیست"}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center text-sm text-zinc-500">اسپرد آربیتراژ IME در دسترس نیست</div>
    );
  }

  // STEP 8: the endpoint answers {available: false, reason} when its inputs
  // are missing — that payload has no spread fields, so it must render as
  // explicit no-data instead of dereferencing undefined numbers.
  if (data.available === false) {
    return (
      <div
        data-testid="ime-spread-unavailable"
        className="text-center text-sm text-zinc-500"
      >
        اسپرد آربیتراژ IME در دسترس نیست
        {data.reason ? `: ${data.reason}` : ""}
      </div>
    );
  }

  return (
    <section className="ime-spread space-y-1">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium text-zinc-300">
          اسپرد آربیتراژ ETF ↔ طلای فیزیکی
        </span>
        <span
          className={cn(
            "font-mono text-xl font-bold",
            (data.net_spread_pct ?? 0) > 0 ? "text-emerald-300" : "text-zinc-400",
          )}
        >
          {fmtPct(data.net_spread_pct)}
        </span>
      </div>
      <div className="text-[11px] text-zinc-500">
        {data.pair ?? "—"} · {data.action ?? "—"} · ناخالص {fmtPct(data.gross_spread_pct)}
      </div>
      <div className="text-[10px] text-zinc-600">
        نسبت تحلیلی محاسبه‌شده از اسنپ‌شات؛ قیمت مستقل بازار یا پیشنهاد معامله نیست.
      </div>
    </section>
  );
}
