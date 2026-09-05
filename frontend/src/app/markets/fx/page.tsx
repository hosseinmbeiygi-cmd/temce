"use client";

import { useQuery } from "@tanstack/react-query";

import { BubbleGauge } from "@/components/currency/BubbleGauge";
import { CurrencyArbitrageMatrix } from "@/components/currency/CurrencyArbitrageMatrix";
import { KillSwitchBanner } from "@/components/currency/KillSwitchBanner";
import { ManualDollarPositions } from "@/components/currency/ManualDollarPositions";
import { MultiRatePriceCard } from "@/components/currency/MultiRatePriceCard";
import { SignalBadge } from "@/components/currency/SignalBadge";
import { Card } from "@/components/ui/Card";
import { getCurrencyOverview } from "@/lib/currencyApi";

function fmt(n: number): string {
  return n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

/** داشبورد دلار و ارزها — سرویس مستقل currency_service (پورت 8002). */
export default function CurrencyPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["currency-overview"],
    queryFn: getCurrencyOverview,
    refetchInterval: 10_000,
  });

  if (isLoading)
    return (
      <div className="p-8 text-center text-sm opacity-70" dir="rtl">
        در حال بارگذاری داده‌های زنده ارزها…
      </div>
    );
  if (error || !data)
    return (
      <div className="p-8 text-center text-sm text-rose-500" dir="rtl">
        خطا در برقراری ارتباط با سرویس ارز — سرویس currency_service (پورت ۸۰۰۲) را بررسی کنید.
      </div>
    );

  return (
    <div className="flex flex-col gap-6 p-6" dir="rtl">
      {data.kill_switch.active && <KillSwitchBanner reasons={data.kill_switch.reasons} />}

      {/* کارت‌های نرخ زنده + گیج حباب */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MultiRatePriceCard title="دلار بازار آزاد (نقدی)" rate={data.rates.free} />
        <MultiRatePriceCard title="تتر دیجیتال (USDT)" rate={data.rates.usdt} />
        <MultiRatePriceCard title="حواله نیما" rate={data.rates.nima} />
        <Card title="شاخص حباب دلار" subtitle="نسبت به نرخ رسمی CBI">
          <BubbleGauge value={data.market_summary.bubble_index} />
        </Card>
      </div>

      {/* ماتریس آربیتراژ + پوزیشن‌ها | سایدبار سیگنال‌ها */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <CurrencyArbitrageMatrix rates={data.arbitrage_matrix} />
          <ManualDollarPositions />
        </div>

        <Card title="سیگنال‌های معاملاتی دستی">
          {data.signals.length === 0 ? (
            <p className="py-6 text-center text-xs opacity-60">
              در حال حاضر سیگنال فعالی وجود ندارد (بازار خنثی).
            </p>
          ) : (
            <div className="space-y-3">
              {data.signals.map((sig, i) => (
                <div key={i} className="space-y-2 rounded-lg border p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold">
                      {sig.asset_type === "CASH_USD" ? "دلار نقدی" : "تتر"}
                    </span>
                    <SignalBadge type={sig.signal_type} confidence={sig.confidence} />
                  </div>
                  {sig.entry_range && (
                    <div className="flex justify-between text-xs opacity-70">
                      <span>بازه ورود:</span>
                      <span className="font-mono tabular-nums">
                        {fmt(sig.entry_range.min)} – {fmt(sig.entry_range.max)} تومان
                      </span>
                    </div>
                  )}
                  {sig.target_price != null && (
                    <div className="flex justify-between text-xs opacity-70">
                      <span>هدف قیمتی:</span>
                      <span className="font-mono tabular-nums text-emerald-500">
                        {fmt(sig.target_price)} تومان
                      </span>
                    </div>
                  )}
                  {sig.stop_loss != null && (
                    <div className="flex justify-between text-xs opacity-70">
                      <span>حد ضرر:</span>
                      <span className="font-mono tabular-nums text-rose-500">
                        {fmt(sig.stop_loss)} تومان
                      </span>
                    </div>
                  )}
                  {sig.holding_period && (
                    <div className="flex justify-between text-xs opacity-70">
                      <span>افق نگهداری:</span>
                      <span>{sig.holding_period}</span>
                    </div>
                  )}
                  <p className="rounded bg-zinc-800/40 p-2 text-xs leading-relaxed opacity-80">
                    {sig.reason}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* خلاصه بازار */}
          <div className="mt-4 space-y-1.5 border-t pt-3 text-xs">
            <div className="flex justify-between">
              <span className="opacity-60">نوسان روزانه:</span>
              <span className="font-mono tabular-nums">
                {data.market_summary.daily_volatility.toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-60">اسپرد خرید/فروش:</span>
              <span className="font-mono tabular-nums">
                {data.market_summary.bid_ask_spread.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-60">آربیتراژ تتر:</span>
              <span className="font-mono tabular-nums">
                {data.market_summary.tether_arbitrage > 0 ? "+" : ""}
                {data.market_summary.tether_arbitrage.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="opacity-60">احساس بازار:</span>
              <span className="font-bold">
                {data.market_summary.sentiment === "BULLISH"
                  ? "صعودی"
                  : data.market_summary.sentiment === "BEARISH"
                    ? "نزولی"
                    : "خنثی"}
              </span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
