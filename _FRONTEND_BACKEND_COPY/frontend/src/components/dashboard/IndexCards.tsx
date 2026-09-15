"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { useIndices } from "@/hooks/useMarketData";
import { fmtInt } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { DeltaBadge, Sparkline } from "./primitives";

export default function IndexCards() {
  const INDICES = useIndices();
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
          <span className="grid size-8 place-items-center rounded-xl border border-line bg-soft text-ink-2">
            <Activity className="size-4" aria-hidden />
          </span>
          شاخص‌های بازار
        </h2>
        <Link href="/markets/indices" className="cursor-pointer text-[11px] font-bold text-ink-3 transition-colors hover:text-ink">
          همه شاخص‌ها ←
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {INDICES.map((idx) => (
          <Link
            key={idx.id}
            href="/markets/indices"
            className="group relative overflow-hidden rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)]"
          >
            <div className="flex items-start justify-between gap-2">
              <p className="truncate text-[11px] font-bold text-ink-2">{idx.name}</p>
              <Sparkline data={idx.spark} width={62} height={22} />
            </div>
            <p dir="ltr" className="mt-3 truncate font-mono text-[17px] font-bold tabular-nums text-ink">
              {fmtInt(idx.value)}
            </p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <DeltaBadge value={idx.changePct} />
              <span
                dir="ltr"
                className={cn(
                  "font-mono text-[10px] font-semibold tabular-nums",
                  idx.change > 0 ? "text-up" : idx.change < 0 ? "text-down" : "text-ink-3",
                )}
              >
                {idx.change > 0 ? "+" : ""}
                {fmtInt(idx.change)}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
