"use client";

import { useQuery } from "@tanstack/react-query";
import { getFreshness, isServiceUnavailable } from "@/lib/goldApi";
import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { cn } from "@/lib/cn";
import type { FreshnessReport, FreshnessStatus } from "@/types/gold";

const STATUS_LABEL: Record<FreshnessStatus, string> = {
  ok: "سالم",
  stale: "قدیمی",
  empty: "خالی",
  missing: "موجود نیست",
};

const STATUS_STYLE: Record<FreshnessStatus, string> = {
  ok: "bg-emerald-950/40 text-emerald-300 ring-emerald-700/40",
  stale: "bg-amber-950/40 text-amber-300 ring-amber-700/40",
  empty: "bg-zinc-800/60 text-zinc-300 ring-zinc-700/40",
  missing: "bg-rose-950/40 text-rose-300 ring-rose-700/40",
};

function FeedHealthContent({ report }: { report: FreshnessReport }) {
  const problems = report.sources
    .filter((source) => source.status !== "ok")
    .slice(0, 6);

  return (
    <section className="feed-health space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-300">سلامت فید داده</h2>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-semibold ring-1",
            STATUS_STYLE[report.overall],
          )}
        >
          وضعیت کلی: {STATUS_LABEL[report.overall]}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 text-[11px] text-zinc-400">
        <span>سالم: {report.counts.ok}</span>
        <span>قدیمی: {report.counts.stale}</span>
        <span>خالی: {report.counts.empty}</span>
        <span>موجود نیست: {report.counts.missing}</span>
        {typeof report.scheduler_jobs === "number" && (
          <span>jobهای زمان‌بندی: {report.scheduler_jobs}</span>
        )}
      </div>

      {problems.length > 0 ? (
        <ul className="space-y-1 text-xs">
          {problems.map((source) => (
            <li key={source.key} className="flex items-center justify-between gap-3">
              <span className="text-zinc-300">{source.label}</span>
              <span className={cn("rounded-full px-2 py-0.5 ring-1", STATUS_STYLE[source.status])}>
                {STATUS_LABEL[source.status]}
                {source.detail ? ` — ${source.detail}` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-xs text-emerald-300">همهٔ منابع داده تازه هستند.</div>
      )}
    </section>
  );
}

export default function FeedHealthSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "freshness"],
    queryFn: getFreshness,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return <SkeletonBlock visible className="h-32 w-full" />;
  }

  if (isError) {
    return (
      <div
        data-testid="feed-health-error"
        className="text-center text-sm text-zinc-500"
      >
        {isServiceUnavailable(error)
          ? "سرویس سلامت فید موقتاً در دسترس نیست (۵۰۳)."
          : "گزارش سلامت فید در دسترس نیست"}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center text-sm text-zinc-500">گزارش سلامت فید در دسترس نیست</div>
    );
  }

  return <FeedHealthContent report={data} />;
}
