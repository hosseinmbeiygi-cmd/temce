"use client";

import { Banknote, Bitcoin, CircleDollarSign, Coins, Euro, Gem } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { type QuoteItem } from "@/lib/market-mock";
import { useQuoteCards } from "@/hooks/useMarketData";
import LiveDataBanner from "./LiveDataBanner";
import { fmtInt } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { DeltaBadge, Flash, Sparkline, SectionHeader } from "./primitives";

const KIND_ICON: Record<QuoteItem["kind"], LucideIcon> = {
  gold: Coins,
  coin: CircleDollarSign,
  dollar: Banknote,
  tether: Bitcoin,
  euro: Euro,
  dirham: Gem,
};

const KIND_TINT: Record<QuoteItem["kind"], string> = {
  gold: "bg-warn/12 text-warn",
  coin: "bg-warn/12 text-warn",
  dollar: "bg-up/12 text-up",
  tether: "bg-emerald-600/12 text-emerald-700 dark:text-emerald-400",
  euro: "bg-primary-600/12 text-primary-700 dark:text-brand-300",
  dirham: "bg-soft text-ink-2",
};

/* Accent color + matching glow per asset kind — the card border tints and
   lights up on hover, giving each asset class its own identity. */
const KIND_ACCENT: Record<QuoteItem["kind"], string> = {
  gold: "#d97706",
  coin: "#f59e0b",
  dollar: "#16a34a",
  tether: "#059669",
  euro: "#4d6a92",
  dirham: "#64748b",
};

export default function QuoteCards() {
  const { data: QUOTES, isLive, isError, isLoading } = useQuoteCards();
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={CircleDollarSign}
        title="قیمت‌های روز"
        subtitle="طلا، سکه، ارز، تتر و دلار — تومان"
        tone="warn"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {QUOTES.map((q) => {
          const Icon = KIND_ICON[q.kind];
          const accent = KIND_ACCENT[q.kind];
          return (
            <div
              key={q.id}
              style={{ "--q-accent": accent } as React.CSSProperties}
              className="group relative cursor-pointer overflow-hidden rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-card-hover)] hover:shadow-[0_10px_30px_-8px_color-mix(in_srgb,var(--q-accent)_28%,transparent)]"
            >
              {/* asset accent edge */}
              <span
                aria-hidden
                className="absolute inset-y-0 right-0 w-[3px] opacity-70 transition-opacity duration-200 group-hover:opacity-100"
                style={{ background: `linear-gradient(180deg, transparent, ${accent}, transparent)` }}
              />
              <div className="flex items-center justify-between gap-2">
                <span className={cn("grid size-9 place-items-center rounded-xl", KIND_TINT[q.kind])}>
                  <Icon className="size-4.5" aria-hidden />
                </span>
                <DeltaBadge value={q.changePct} />
              </div>
              <p className="mt-3 text-[13px] font-bold text-ink">{q.title}</p>
              <p className="text-[10px] text-ink-3">{q.subtitle}</p>
              <div className="mt-2.5 flex items-end justify-between gap-2">
                <div className="min-w-0">
                  <Flash value={q.price} className="max-w-full">
                    <p dir="ltr" className="truncate font-mono text-[17px] font-bold tabular-nums text-ink">
                      {fmtInt(q.price)}
                    </p>
                  </Flash>
                  <p className="text-[9.5px] text-ink-3">{q.unit}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Sparkline data={q.spark} width={70} height={24} />
                  <span dir="ltr" className="font-mono text-[9.5px] font-bold tabular-nums text-ink-3">
                    {q.change > 0 ? "+" : ""}{fmtInt(Math.abs(q.change))}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
