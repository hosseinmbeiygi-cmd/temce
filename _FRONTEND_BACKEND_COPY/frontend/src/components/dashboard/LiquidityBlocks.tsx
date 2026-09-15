"use client";

import Link from "next/link";
import { HandCoins, Sparkles, Wallet } from "lucide-react";
import { CASH_FLOW, LIQUIDITY } from "@/lib/market-mock";
import { useMarketOverview, useTopPerformers } from "@/hooks/useMarketData";
import { fmtBillion, fmtInt, fmtPct } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { DeltaBadge, TrendArrow } from "./primitives";

export default function LiquidityBlocks() {
  const live = useMarketOverview();
  const topPerformers = useTopPerformers();
  const liquidityB = live?.tradeValueB ?? LIQUIDITY.totalB;
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {/* نقدینگی */}
      <div className="group rounded-2xl border border-line bg-card p-6 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)]">
        <div className="flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-primary-600/12 text-primary-700 dark:text-brand-300">
            <Wallet className="size-4.5" aria-hidden />
          </span>
          <h3 className="text-sm font-bold text-ink">نقدینگی بازار</h3>
        </div>
        <div className="mt-4 flex items-baseline gap-2">
          <span dir="ltr" className="font-mono text-[26px] font-black tabular-nums text-ink">
            {fmtBillion(liquidityB)}
          </span>
          <span className="text-[11px] text-ink-3">میلیارد تومان</span>
        </div>
        <DeltaBadge value={live?.avgChangePct ?? LIQUIDITY.deltaPct} className="mt-2" />
        <div className="mt-5 space-y-2">
          {LIQUIDITY.cashDistribution.map((c) => (
            <div key={c.label} className="flex items-center gap-2.5">
              <span className="w-16 shrink-0 text-[10.5px] font-medium text-ink-3">{c.label}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-soft">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${c.value}%`, background: c.color }}
                />
              </div>
              <span dir="ltr" className="w-8 shrink-0 text-left font-mono text-[10.5px] tabular-nums text-ink-2">
                {c.value}٪
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* جریان نقدینگی */}
      <div className="group rounded-2xl border border-line bg-card p-6 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)]">
        <div className="flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-up/12 text-up">
            <HandCoins className="size-4.5" aria-hidden />
          </span>
          <h3 className="text-sm font-bold text-ink">جریان نقدینگی</h3>
        </div>
        <div className="mt-4 flex items-baseline gap-2">
          <span dir="ltr" className="font-mono text-[26px] font-black tabular-nums text-up">
            +{fmtBillion(CASH_FLOW.realNetInflowB)}
          </span>
          <span className="text-[11px] text-ink-3">ورود حقیقی (م.ت)</span>
        </div>
        <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-3">
          حقوقی:
          <span dir="ltr" className="font-mono font-bold tabular-nums text-down">
            {fmtBillion(CASH_FLOW.legalNetInflowB)}
          </span>
          <span>میلیارد تومان خروج</span>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2.5">
          <div className="rounded-xl border border-line bg-soft/60 p-3">
            <p className="text-[10px] text-ink-3">صف خرید</p>
            <p dir="ltr" className="mt-1 font-mono text-lg font-bold tabular-nums text-up">{fmtInt(CASH_FLOW.queueBuy)}</p>
          </div>
          <div className="rounded-xl border border-line bg-soft/60 p-3">
            <p className="text-[10px] text-ink-3">صف فروش</p>
            <p dir="ltr" className="mt-1 font-mono text-lg font-bold tabular-nums text-down">{fmtInt(CASH_FLOW.queueSell)}</p>
          </div>
        </div>
      </div>

      {/* برترین‌ها */}
      <div className="group rounded-2xl border border-line bg-card p-6 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)] md:col-span-2 xl:col-span-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-xl bg-warn/12 text-warn">
              <Sparkles className="size-4.5" aria-hidden />
            </span>
            <h3 className="text-sm font-bold text-ink">برترین‌های بازار</h3>
          </div>
          <Link href="/markets" className="cursor-pointer text-[11px] font-bold text-ink-3 transition-colors hover:text-ink">
            همه ←
          </Link>
        </div>
        <div className="mt-4 divide-y divide-line">
          {topPerformers.map((s) => (
            <Link
              key={s.symbol}
              href={`/symbol/${encodeURIComponent(s.symbol)}`}
              className="flex cursor-pointer items-center gap-3 py-2.5 transition-colors duration-150 hover:text-ink"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-bold text-ink">{s.symbol}</span>
                <span className="block truncate text-[10px] text-ink-3">{s.name}</span>
              </span>
              <span dir="ltr" className="font-mono text-[11px] tabular-nums text-ink-2">
                {fmtInt(s.price)}
              </span>
              <span
                dir="ltr"
                className={cn(
                  "flex w-16 items-center justify-end gap-1 font-mono text-[12px] font-bold tabular-nums",
                  s.changePct > 0 ? "text-up" : "text-down",
                )}
              >
                <TrendArrow value={s.changePct} />
                {fmtPct(s.changePct)}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
