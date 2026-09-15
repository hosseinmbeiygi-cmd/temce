"use client";

import Link from "next/link";
import { CalendarDays, FileText, HandCoins, Landmark, TrendingUp } from "lucide-react";
import { MARKET_EVENTS, type MarketEvent } from "@/lib/market-mock";
import { cn } from "@/lib/cn";
import { SectionHeader } from "./primitives";

const TYPE_META: Record<MarketEvent["type"], { icon: typeof Landmark; cls: string }> = {
  "مجمع": { icon: Landmark, cls: "bg-primary-600/12 text-primary-700 dark:text-brand-300" },
  "سود نقدی": { icon: HandCoins, cls: "bg-up/12 text-up" },
  "افزایش سرمایه": { icon: TrendingUp, cls: "bg-warn/12 text-warn" },
  "اعلامیه": { icon: FileText, cls: "bg-soft text-ink-2" },
};

export default function EventCalendar() {
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={CalendarDays}
        title="تقویم بازار"
        subtitle="مجامع، سود نقدی و افزایش سرمایه‌های پیش‌رو"
        action={
          <Link href="/economic-calendar" className="cursor-pointer text-[11px] font-bold text-ink-3 transition-colors hover:text-ink">
            تقویم کامل ←
          </Link>
        }
      />
      <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {MARKET_EVENTS.map((ev) => {
          const meta = TYPE_META[ev.type];
          const Icon = meta.icon;
          return (
            <div
              key={ev.id}
              className="group flex cursor-pointer items-center gap-3 rounded-xl border border-line/70 bg-soft/40 p-3 transition-all duration-150 hover:border-line-strong hover:bg-soft"
            >
              <div className="flex shrink-0 flex-col items-center rounded-xl border border-line bg-card px-2.5 py-1.5">
                <span dir="ltr" className="font-mono text-[15px] font-black tabular-nums text-ink">
                  {ev.date.slice(-2)}
                </span>
                <span className="text-[8.5px] text-ink-3">{ev.day}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-bold text-ink">{ev.title}</p>
                <p className="mt-1 text-[10px] text-ink-3">
                  {ev.symbol !== "—" ? `نماد ${ev.symbol}` : "عمومی"}
                  <span aria-hidden> • </span>
                  {ev.date}
                </p>
              </div>
              <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg", meta.cls)}>
                <Icon className="size-4" aria-hidden />
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
