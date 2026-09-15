"use client";

import { Eye, Globe2 } from "lucide-react";
import { CASH_FLOW, VALUE_VOLUME } from "@/lib/market-mock";
import { useMarketOverview, useQuoteCards } from "@/hooks/useMarketData";
import { fmtBillion, fmtInt, fmtNum } from "@/lib/market-format";
import { MiniMetric, SectionHeader } from "./primitives";

export default function MarketOverview() {
  const live = useMarketOverview();
  const quotes = useQuoteCards();
  const breadth = live?.breadth ?? VALUE_VOLUME.breadth;
  const tradeValueB = live?.tradeValueB ?? VALUE_VOLUME.tradeValueB;
  const total = breadth.up + breadth.down + breadth.flat;
  const upPct = total > 0 ? (breadth.up / total) * 100 : 0;

  // Total market cap in USD billion: totalCapB (billion IRR→Toman is 1:10,
  // mock stores it in billion Toman) ÷ free-market USD rate. Live dollar quote
  // wins; mock fallback keeps the card populated offline.
  const dollar = quotes.find((q) => q.id === "dollar" || q.kind === "dollar");
  const usdRate = dollar?.price && dollar.price > 1000 ? dollar.price : 105850;
  const totalCapB = VALUE_VOLUME.totalCapB; // میلیارد تومان
  const marketCapUsdB = totalCapB / usdRate;

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader icon={Eye} title="نگاه کلی به بازار" subtitle="وضعیت امروز بازار سهام" />

      {/* Total market cap — hero metric */}
      <div className="relative mt-4 overflow-hidden rounded-2xl border border-primary-600/25 bg-gradient-to-bl from-primary-600/10 via-soft/40 to-soft/10 p-4 dark:border-brand-300/25">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-[11px] font-bold text-ink-2">
              <Globe2 className="size-3.5 text-primary-600 dark:text-brand-300" aria-hidden />
              ارزش کل بازار سهام
            </p>
            <p dir="ltr" className="mt-1.5 font-mono text-[26px] font-black leading-none tabular-nums text-ink">
              {fmtNum(marketCapUsdB, 1)}
              <span className="ms-1.5 text-[13px] font-bold">B$</span>
            </p>
            <p className="mt-1.5 text-[10px] text-ink-3">
              معادل <span dir="ltr" className="font-mono">{fmtBillion(totalCapB)}</span> میلیارد تومان — با نرخ دلار آزاد
            </p>
          </div>
          <span dir="ltr" className="shrink-0 rounded-xl border border-line bg-card/70 px-2.5 py-1 font-mono text-[10px] font-bold text-ink-2 tabular-nums">
            $1 = {fmtInt(usdRate)}
          </span>
        </div>
      </div>

      {/* Breadth bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-[11px] font-bold">
          <span className="text-up">{fmtInt(breadth.up)} نماد مثبت</span>
          <span className="text-ink-3">مثبت {upPct.toFixed(0)}٪</span>
          <span className="text-down">{fmtInt(breadth.down)} نماد منفی</span>
        </div>
        <div className="mt-2 flex h-2.5 gap-1 overflow-hidden rounded-full bg-soft" dir="rtl">
          <div className="h-full rounded-full bg-up/80 transition-all duration-500" style={{ width: `${upPct}%` }} />
          <div className="h-full flex-1 rounded-full bg-down/70 transition-all duration-500" />
        </div>
        <p className="mt-1.5 text-center text-[10px] text-ink-3">
          {fmtInt(breadth.flat)} نماد بدون تغییر
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <MiniMetric
          label="ارزش معاملات خرد"
          value={`${fmtBillion(tradeValueB)} م.ت`}
          hint="میلیارد تومان"
        />
        <MiniMetric
          label="ورود پول حقیقی"
          value={`+${fmtBillion(CASH_FLOW.realNetInflowB)}`}
          tone="up"
          hint="میلیارد تومان"
        />
        <MiniMetric label="صف خرید" value={fmtInt(CASH_FLOW.queueBuy)} tone="up" hint="نماد" />
        <MiniMetric label="صف فروش" value={fmtInt(CASH_FLOW.queueSell)} tone="down" hint="نماد" />
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-2.5">
        <MiniMetric label="حجم معاملات" value={`${fmtInt(live?.volumeM ?? VALUE_VOLUME.volumeM)} م`} hint="میلیون سهم" />
        <MiniMetric label="نسبت P/E بازار" value={fmtNum(VALUE_VOLUME.peRatio, 1)} hint="به‌روزرسانی هر روز" />
      </div>

      <div className="mt-3 rounded-xl border border-line bg-soft/60 p-3">
        <p className="text-[11px] font-bold text-ink-2">متن بازار</p>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-3">
          ارزش معاملات خرد امروز به{" "}
          <span dir="ltr" className="font-mono font-bold text-ink">{fmtBillion(tradeValueB)}</span>{" "}
          میلیارد تومان رسید؛ حقیقی‌ها <span className="font-bold text-up">+{fmtBillion(CASH_FLOW.realNetInflowB)}</span>{" "}
          میلیارد تومان وارد بازار کردند و جریان سمت حقوقی منفی ماند.
        </p>
      </div>
    </section>
  );
}
