"use client";

import { useQuery } from "@tanstack/react-query";
import { getMacroCalendar, isServiceUnavailable } from "@/lib/goldApi";
import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { cn } from "@/lib/cn";

function EventCalendarContent({
  events,
}: {
  events: Awaited<ReturnType<typeof getMacroCalendar>>;
}) {
  if (events.length === 0) {
    return (
      <div className="text-center text-sm text-zinc-500">
        رویداد اقتصادی ذخیره‌شده‌ای وجود ندارد
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {events.map((event) => (
        <li
          key={event.event_id}
          className="flex items-center justify-between gap-3 rounded-lg bg-zinc-900/40 px-3 py-2 ring-1 ring-zinc-700/40"
        >
          <div className="min-w-0">
            <div className="truncate text-sm text-zinc-100">{event.title ?? event.event_id}</div>
            <div className="text-[11px] text-zinc-500">
              {[event.category, event.country].filter(Boolean).join(" · ") || "—"}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 font-mono text-[11px] text-zinc-400">
            <span>{event.event_date}</span>
            {event.is_high_volatility && (
              <span className={cn("rounded-full px-2 py-0.5 ring-1", "bg-rose-950/40 text-rose-300 ring-rose-700/40")}>
                پرنوسان
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function EventCalendarSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "macro-calendar"],
    queryFn: () => getMacroCalendar(20),
    refetchInterval: 300_000,
  });

  if (isLoading) {
    return <SkeletonBlock visible className="h-40 w-full" />;
  }

  if (isError) {
    return (
      <div
        data-testid="event-calendar-error"
        className="text-center text-sm text-zinc-500"
      >
        {isServiceUnavailable(error)
          ? "سرویس تقویم رویدادها موقتاً در دسترس نیست (۵۰۳)."
          : "تقویم رویدادها در دسترس نیست"}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center text-sm text-zinc-500">تقویم رویدادها در دسترس نیست</div>
    );
  }

  return (
    <section className="event-calendar space-y-2">
      <h2 className="text-sm font-semibold text-zinc-300">تقویم اقتصادی</h2>
      <EventCalendarContent events={data} />
    </section>
  );
}
