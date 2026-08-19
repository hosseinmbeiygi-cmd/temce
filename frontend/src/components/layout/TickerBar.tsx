"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { MARKET_SESSION, type TickerItem } from "@/lib/market-mock";
import { useTickerItems } from "@/hooks/useMarketData";
import { fmtInt, fmtPct } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { TrendArrow } from "@/components/dashboard/primitives";

function TickerChip({ symbol, price, changePct }: TickerItem) {
  const tone = changePct > 0 ? "up" : changePct < 0 ? "down" : "flat";
  return (
    <Link
      href="/markets"
      className="group mx-1 flex shrink-0 cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 transition-colors duration-150 hover:bg-soft"
    >
      <span className="text-[12px] font-bold text-ink">{symbol}</span>
      <span dir="ltr" className="font-mono text-[11px] tabular-nums text-ink-2">
        {fmtInt(price)}
      </span>
      <span
        dir="ltr"
        className={cn(
          "flex items-center gap-0.5 font-mono text-[11px] font-bold tabular-nums",
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          tone === "flat" && "text-ink-3",
        )}
      >
        <TrendArrow value={changePct} className="size-3" />
        {fmtPct(changePct)}
      </span>
    </Link>
  );
}

export default function TickerBar() {
  const tickerItems = useTickerItems();
  const AVG = tickerItems.length > 0 ? tickerItems.reduce((s, t) => s + t.changePct, 0) / tickerItems.length : 0;
  const items = [...tickerItems, ...tickerItems];
  return (
    <div className="sticky top-14 z-40 border-b border-line bg-card/88 backdrop-blur supports-[backdrop-filter]:bg-card/75">
      <div className="mx-auto flex h-12 max-w-[1600px] items-center gap-3 px-3 lg:px-5">
        {/* Summary chip */}
        <div className="flex shrink-0 items-center gap-2 rounded-xl border border-line bg-soft px-3 py-1.5">
          <span className="relative flex size-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-up opacity-50" />
            <span className="relative inline-flex size-2 rounded-full bg-up" />
          </span>
          <span className="text-[11px] font-bold text-ink-2">{MARKET_SESSION.status}</span>
          <span dir="ltr" className={cn("font-mono text-[11px] font-bold tabular-nums", AVG >= 0 ? "text-up" : "text-down")}>
            {fmtPct(AVG)}
          </span>
        </div>

        <span className="hidden shrink-0 items-center gap-1.5 text-[10.5px] text-ink-3 xl:flex">
          <Activity className="size-3.5" aria-hidden />
          {MARKET_SESSION.note}
        </span>

        {/* Marquee */}
        <div className="group relative min-w-0 flex-1 overflow-hidden" dir="ltr">
          <div className="ticker-track">
            <div className="ticker-track-content flex w-max items-center animate-ticker group-hover:[animation-play-state:paused]">
              {items.map((t, i) => (
                <TickerChip key={`${t.symbol}-${i}`} {...t} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
