"use client";

import { Globe } from "lucide-react";
import { useGlobalMarkets } from "@/hooks/useMarketData";
import { fmtNum } from "@/lib/market-format";
import LiveDataBanner from "./LiveDataBanner";
import { DeltaBadge, SectionHeader, Sparkline } from "./primitives";

export default function GlobalMarkets() {
  const { data: markets, isLive, isError, isLoading } = useGlobalMarkets();

  return (
    <section className="space-y-3">
      <SectionHeader
        icon={Globe}
        title="بازارهای جهانی"
        subtitle="انس طلا، نفت برنت و بیت‌کوین — از BrsApi"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {markets.map((g) => (
          <div
            key={g.id}
            className="group cursor-pointer rounded-2xl border border-line bg-card p-3.5 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)]"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-[12px] font-bold text-ink">{g.title}</p>
              <DeltaBadge value={g.changePct} />
            </div>
            <p className="mt-0.5 truncate text-[10px] text-ink-3">{g.subtitle}</p>
            <div className="mt-2.5 flex items-end justify-between gap-2">
              <div className="min-w-0">
                <p dir="ltr" className="truncate font-mono text-[15px] font-bold tabular-nums text-ink">
                  {fmtNum(g.price, g.price < 1000 ? 2 : 1)}
                </p>
                <p className="text-[9.5px] text-ink-3">{g.unit}</p>
              </div>
              <Sparkline data={g.spark} width={64} height={22} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
