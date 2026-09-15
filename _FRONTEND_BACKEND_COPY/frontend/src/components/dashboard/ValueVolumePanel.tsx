"use client";

import Link from "next/link";
import { ArrowUpRight, Banknote, Building2 } from "lucide-react";
import { VALUE_VOLUME, type Top5Symbol } from "@/lib/market-mock";
import { useActiveSymbols, useMarketOverview } from "@/hooks/useMarketData";
import { fmtBillion, fmtInt, fmtPct } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { MiniMetric, SectionHeader } from "./primitives";

function Top5Table({ rows, market }: { rows: Top5Symbol[]; market: "tse" | "otc" }) {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold text-ink-2">
        {market === "tse" ? <Building2 className="size-3.5" aria-hidden /> : <Banknote className="size-3.5" aria-hidden />}
        {market === "tse" ? "۱۰ نماد اول بورس" : "۱۰ نماد اول فرابورس"}
      </p>
      <div className="overflow-hidden rounded-xl border border-line">
        <div className="grid grid-cols-[1fr_auto_auto] gap-2 border-b border-line bg-soft/60 px-3 py-2 text-[9.5px] font-bold text-ink-3">
          <span>نماد</span>
          <span className="w-16 text-left">ارزش (م.ت)</span>
          <span className="w-14 text-left">تغییر</span>
        </div>
        {rows.map((s) => (
          <Link
            key={s.symbol}
            href={`/symbol/${encodeURIComponent(s.symbol)}`}
            className="grid grid-cols-[1fr_auto_auto] cursor-pointer items-center gap-2 border-b border-line/60 px-3 py-2 text-[11px] transition-colors last:border-0 hover:bg-soft"
          >
            <span className="min-w-0">
              <span className="block truncate font-bold text-ink">{s.symbol}</span>
              <span className="block truncate text-[9px] text-ink-3">{s.name}</span>
            </span>
            <span dir="ltr" className="w-16 text-left font-mono tabular-nums text-ink-2">
              {fmtBillion(s.tradeValueB)}
            </span>
            <span dir="ltr" className={cn("w-14 text-left font-mono font-bold tabular-nums", s.changePct > 0 ? "text-up" : "text-down")}>
              {fmtPct(s.changePct, 1)}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function ValueVolumePanel() {
  const live = useMarketOverview();
  const active = useActiveSymbols();
  const vv = VALUE_VOLUME;
  const tradeValueB = live?.tradeValueB ?? vv.tradeValueB;
  const volumeM = live?.volumeM ?? vv.volumeM;
  const top5Tse = active.tse;
  const top5Otc = active.otc;
  const valueDelta = ((tradeValueB - vv.prevTradeValueB) / vv.prevTradeValueB) * 100;
  const volDelta = ((volumeM - vv.prevVolumeM) / vv.prevVolumeM) * 100;
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={ArrowUpRight}
        title="ارزش و حجم معاملات"
        subtitle="بورس و فرابورس — امروز در برابر دیروز"
      />
      <div className="mt-4 grid grid-cols-3 gap-2.5">
        <MiniMetric
          label="ارزش معاملات"
          value={fmtBillion(tradeValueB)}
          tone={valueDelta >= 0 ? "up" : "down"}
          hint={`نسبت به دیروز ${fmtPct(valueDelta, 1)}`}
        />
        <MiniMetric
          label="حجم معاملات"
          value={`${fmtInt(volumeM)} میلیون`}
          tone={volDelta >= 0 ? "up" : "down"}
          hint={`نسبت به دیروز ${fmtPct(volDelta, 1)}`}
        />
        <MiniMetric label="تعداد معاملات" value={`${fmtInt(vv.dealsK)} هزار`} hint="قرارداد" />
      </div>
      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <Top5Table rows={top5Tse} market="tse" />
        <Top5Table rows={top5Otc} market="otc" />
      </div>
    </section>
  );
}
