"use client";

import { Eye } from "lucide-react";
import { CASH_FLOW, VALUE_VOLUME } from "@/lib/market-mock";
import { useMarketOverview } from "@/hooks/useMarketData";
import { fmtBillion, fmtInt, fmtNum } from "@/lib/market-format";
import { MiniMetric, SectionHeader } from "./primitives";

export default function MarketOverview() {
  const live = useMarketOverview();
  const breadth = live?.breadth ?? VALUE_VOLUME.breadth;
  const tradeValueB = live?.tradeValueB ?? VALUE_VOLUME.tradeValueB;
  const total = breadth.up + breadth.down + breadth.flat;
  const upPct = total > 0 ? (breadth.up / total) * 100 : 0;

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader icon={Eye} title="نگاه کلی به بازار" subtitle="وضعیت امروز بازار سهام" />

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
        <MiniMetric label="ارزش بازار کل" value={`${fmtBillion(VALUE_VOLUME.totalCapB)} م.ت`} hint="بورس و فرابورس" />
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
