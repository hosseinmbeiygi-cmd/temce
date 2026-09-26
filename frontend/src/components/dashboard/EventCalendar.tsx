"use client";

import { CalendarDays, FileText, HandCoins, Landmark, TrendingUp } from "lucide-react";
import { useMarketEvents, type CalendarEvent } from "@/hooks/useMarketData";
import { cn } from "@/lib/cn";
import LiveDataBanner from "./LiveDataBanner";
import { SectionHeader } from "./primitives";

type EventKind = "assembly" | "dividend" | "capitalIncrease" | "notice";

const KIND_META: Record<EventKind, { icon: typeof Landmark; cls: string; label: string }> = {
  assembly: { icon: Landmark, cls: "bg-primary-600/12 text-primary-700 dark:text-brand-300", label: "مجمع" },
  dividend: { icon: HandCoins, cls: "bg-up/12 text-up", label: "سود نقدی" },
  capitalIncrease: { icon: TrendingUp, cls: "bg-warn/12 text-warn", label: "افزایش سرمایه" },
  notice: { icon: FileText, cls: "bg-soft text-ink-2", label: "اعلامیه" },
};

/** Backend economic-calendar categories → the widget's 4 visual kinds. */
function classify(ev: CalendarEvent): EventKind {
  const text = `${ev.title} ${ev.category ?? ""}`;
  if (text.includes("مجمع")) return "assembly";
  if (text.includes("سود") || text.includes("توزیع")) return "dividend";
  if (text.includes("افزایش سرمایه") || text.includes("حق تقدم")) return "capitalIncrease";
  return "notice";
}

const WEEKDAYS_FA = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه"];

export default function EventCalendar() {
  const { data: events, isLive, isError, isLoading } = useMarketEvents();
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={CalendarDays}
        title="تقویم بازار"
        subtitle="رویدادهای اقتصادی پیش‌رو — از تقویم اقتصادی"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {events.map((ev) => {
          const kind = classify(ev);
          const meta = KIND_META[kind];
          const Icon = meta.icon;
          const weekday = WEEKDAYS_FA[new Date(ev.date).getDay()] ?? "";
          return (
            <div
              key={ev.id}
              className="group flex cursor-pointer items-center gap-3 rounded-xl border border-line/70 bg-soft/40 p-3 transition-all duration-150 hover:border-line-strong hover:bg-soft"
            >
              <div className="flex shrink-0 flex-col items-center rounded-xl border border-line bg-card px-2.5 py-1.5">
                <span dir="ltr" className="font-mono text-[15px] font-black tabular-nums text-ink">
                  {ev.date.slice(-2)}
                </span>
                <span className="text-[8.5px] text-ink-3">{weekday}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-bold text-ink">{ev.title}</p>
                <p className="mt-1 text-[10px] text-ink-3">
                  {meta.label}
                  <span aria-hidden> • </span>
                  {ev.time ? `${ev.time} — ` : ""}
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
