"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { useIndices } from "@/hooks/useMarketData";
import LiveDataBanner from "./LiveDataBanner";
import { fmtInt } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { DeltaBadge, Flash, Sparkline } from "./primitives";

export default function IndexCards() {
  const { data: INDICES, isLive, isError, isLoading } = useIndices();
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
          <span className="grid size-8 place-items-center rounded-xl border border-primary-600/20 bg-primary-600/10 text-primary-700 dark:border-brand-300/20 dark:bg-brand-300/10 dark:text-brand-200">
            <Activity className="size-4" aria-hidden />
          </span>
          شاخص‌های بازار
        </h2>
        <Link href="/markets/indices" className="cursor-pointer text-[11px] font-bold text-ink-3 transition-colors hover:text-ink">
          همه شاخص‌ها ←
        </Link>
      </div>
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {INDICES.map((idx) => {
          const pos = idx.changePct > 0;
          return (
            <Link
              key={idx.id}
              href="/markets/indices"
              style={{
                "--idx-tint": pos ? "var(--up)" : idx.changePct < 0 ? "var(--down)" : "var(--ink-3)",
              } as React.CSSProperties}
              className="group relative overflow-hidden rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)]"
            >
              {/* performance wash — fades toward the inline-start edge */}
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_left,color-mix(in_srgb,var(--idx-tint)_9%,transparent),transparent_65%)] transition-opacity duration-300 group-hover:opacity-125"
              />
              <div className="relative flex items-start justify-between gap-2">
                <p className="truncate text-[11px] font-bold text-ink-2">{idx.name}</p>
                <Sparkline data={idx.spark} width={62} height={22} />
              </div>
              <Flash value={idx.value} className="relative mt-3 max-w-full">
                <p dir="ltr" className="truncate font-mono text-[17px] font-bold tabular-nums text-ink">
                  {fmtInt(idx.value)}
                </p>
              </Flash>
              <div className="relative mt-2.5 flex flex-wrap items-center gap-2">
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
          );
        })}
      </div>
    </section>
  );
}
