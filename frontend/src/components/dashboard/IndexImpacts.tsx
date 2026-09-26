"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, Scale } from "lucide-react";
import { useIndexImpacts, type ImpactRow } from "@/hooks/useMarketData";
import { fmtNum } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import LiveDataBanner from "./LiveDataBanner";
import { SectionHeader } from "./primitives";

function ImpactList({ rows, positive }: { rows: ImpactRow[]; positive: boolean }) {
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.impact)));
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <Link
          key={r.symbol}
          href={`/symbol/${encodeURIComponent(r.symbol)}`}
          className="group flex cursor-pointer items-center gap-3 rounded-xl border border-line/70 bg-soft/40 px-3 py-2.5 transition-all duration-150 hover:border-line-strong hover:bg-soft"
        >
          <span
            className={cn(
              "grid size-7 shrink-0 place-items-center rounded-lg",
              positive ? "bg-up/12 text-up" : "bg-down/12 text-down",
            )}
          >
            {positive ? <ArrowUp className="size-4" aria-hidden /> : <ArrowDown className="size-4" aria-hidden />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[12.5px] font-bold text-ink">{r.symbol}</span>
            <span className="block truncate text-[10px] text-ink-3">{r.name}</span>
          </span>
          <span dir="ltr" className="font-mono text-[12px] font-bold tabular-nums text-ink-2">
            {fmtNum(r.impact, 1)}
          </span>
          <div className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-soft sm:block">
            <div
              className={cn("h-full rounded-full transition-all duration-500", positive ? "bg-up" : "bg-down")}
              style={{ width: `${(Math.abs(r.impact) / max) * 100}%` }}
            />
          </div>
        </Link>
      ))}
    </div>
  );
}

export default function IndexImpacts() {
  const { data, isLive, isError, isLoading } = useIndexImpacts();
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={Scale}
        title="تأثیر بر شاخص کل"
        subtitle="سهم تقریبی هر نماد از تغییر شاخص — بر پایه جریان داده زنده"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold text-up">
            <ArrowUp className="size-3.5" aria-hidden /> تأثیر مثبت بر شاخص
          </p>
          <ImpactList rows={data.positive} positive />
        </div>
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold text-down">
            <ArrowDown className="size-3.5" aria-hidden /> تأثیر منفی بر شاخص
          </p>
          <ImpactList rows={data.negative} positive={false} />
        </div>
      </div>
    </section>
  );
}
