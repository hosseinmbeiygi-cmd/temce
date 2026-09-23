"use client";

import Link from "next/link";
import { Trophy } from "lucide-react";
import { useTopStocks } from "@/hooks/useMarketData";
import LiveDataBanner from "./LiveDataBanner";
import { fmtBillion, fmtInt, fmtPct } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { SectionHeader, TrendArrow } from "./primitives";

export default function TopStocksToday() {
  const { data: TOP_STOCKS_TODAY, isLive, isError, isLoading } = useTopStocks();
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={Trophy}
        tone="up"
        title="بهترین‌های بازار امروز"
        subtitle="برترین نمادهای سهام از نظر رشد قیمت"
        action={
          <Link href="/markets" className="cursor-pointer text-[11px] font-bold text-ink-3 transition-colors hover:text-ink">
            همه بازارها ←
          </Link>
        }
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="mt-3 divide-y divide-line">
        {TOP_STOCKS_TODAY.map((s, i) => (
          <Link
            key={s.symbol}
            href={`/symbol/${encodeURIComponent(s.symbol)}`}
            className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2.5 transition-colors duration-150 hover:bg-soft"
          >
            <span
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full font-mono text-[10px] font-black",
                i < 3 ? "bg-up/12 text-up" : "bg-soft text-ink-3",
              )}
            >
              {i + 1}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-bold text-ink">{s.symbol}</span>
              <span className="block truncate text-[10.5px] text-ink-3">{s.name}</span>
            </span>
            <span dir="ltr" className="hidden font-mono text-[11px] tabular-nums text-ink-2 sm:block">
              {fmtInt(s.price)}
            </span>
            <span className="hidden items-center gap-1 rounded-lg bg-soft px-2 py-1 text-[10px] font-medium text-ink-3 md:flex">
              {fmtBillion(s.tradeValueB)} م.ت
            </span>
            <span
              dir="ltr"
              className={cn("flex w-20 items-center justify-end gap-1 font-mono text-[12px] font-bold tabular-nums", s.changePct > 0 ? "text-up" : "text-down")}
            >
              <TrendArrow value={s.changePct} />
              {fmtPct(s.changePct)}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
