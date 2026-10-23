"use client";

import { useQuery } from "@tanstack/react-query";
import { getFreshness, getHealth } from "@/lib/goldApi";
import type { FreshnessSource, FreshnessStatus } from "@/types/gold";

const STATUS_STYLE: Record<FreshnessStatus, { dot: string; text: string; label: string }> = {
  ok: { dot: "bg-emerald-400", text: "text-emerald-400", label: "تازه" },
  stale: { dot: "bg-amber-400", text: "text-amber-400", label: "قدیمی" },
  empty: { dot: "bg-zinc-500", text: "text-zinc-400", label: "خالی" },
  missing: { dot: "bg-rose-500", text: "text-rose-400", label: "ناموجود" },
};

function faAge(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 1) return "همین حالا";
  if (minutes < 60) return `${Math.round(minutes).toLocaleString("fa-IR")} دقیقه پیش`;
  if (minutes < 1440) return `${Math.round(minutes / 60).toLocaleString("fa-IR")} ساعت پیش`;
  return `${Math.round(minutes / 1440).toLocaleString("fa-IR")} روز پیش`;
}

function SourceRow({ source }: { source: FreshnessSource }) {
  const style = STATUS_STYLE[source.status] ?? STATUS_STYLE.empty;
  return (
    <tr style={{ borderTop: "1px solid var(--gd-border)" }}>
      <td className="p-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${style.dot}`} />
          <span style={{ color: "var(--gd-text)" }}>{source.label}</span>
        </div>
        <div className="text-[10px] font-mono mt-0.5" style={{ color: "var(--gd-text-3)" }}>
          {source.table}.{source.column}
        </div>
      </td>
      <td className={`p-3 text-left font-semibold ${style.text}`}>{style.label}</td>
      <td className="p-3 text-left font-mono text-xs" style={{ color: "var(--gd-text-2)" }}>
        {faAge(source.age_minutes)}
      </td>
      <td className="p-3 text-left font-mono text-xs" style={{ color: "var(--gd-text-2)" }}>
        {source.rows === null ? "—" : source.rows.toLocaleString("fa-IR")}
      </td>
      <td className="p-3 text-left font-mono text-xs" style={{ color: "var(--gd-text-3)" }}>
        {source.max_age_minutes >= 1440
          ? `${Math.round(source.max_age_minutes / 1440).toLocaleString("fa-IR")} روز`
          : `${source.max_age_minutes.toLocaleString("fa-IR")} دقیقه`}
      </td>
      <td className="p-3 text-left text-[10px] max-w-[220px] truncate" style={{ color: "var(--gd-text-3)" }} title={source.detail ?? ""}>
        {source.detail ?? ""}
      </td>
    </tr>
  );
}

export default function GoldHealthPage() {
  const { data: freshness, isLoading } = useQuery({
    queryKey: ["gold", "freshness"],
    queryFn: getFreshness,
    refetchInterval: 60_000,
  });

  const { data: health } = useQuery({
    queryKey: ["gold", "health"],
    queryFn: getHealth,
    refetchInterval: 60_000,
  });

  const overall = freshness ? STATUS_STYLE[freshness.overall] : STATUS_STYLE.empty;

  return (
    <div className="space-y-6" dir="rtl">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(
          [
            ["ok", "تازه"],
            ["stale", "قدیمی"],
            ["empty", "خالی"],
            ["missing", "ناموجود"],
          ] as const
        ).map(([key, label]) => (
          <div
            key={key}
            className="rounded-xl p-4"
            style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}
          >
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--gd-text-2)" }}>
              <span className={`w-2 h-2 rounded-full ${STATUS_STYLE[key].dot}`} />
              {label}
            </div>
            <div className={`text-2xl font-bold mt-1 ${STATUS_STYLE[key].text}`}>
              {(freshness?.counts?.[key] ?? 0).toLocaleString("fa-IR")}
            </div>
          </div>
        ))}
      </div>

      <div
        className="rounded-xl p-4 flex flex-wrap items-center justify-between gap-3"
        style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}
      >
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${overall.dot}`} />
          <div>
            <div className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
              وضعیت کلی داده: <span className={overall.text}>{overall.label}</span>
            </div>
            <div className="text-[10px] font-mono" style={{ color: "var(--gd-text-3)" }}>
              {freshness?.generated_at ?? ""}
            </div>
          </div>
        </div>
        <div className="text-xs flex flex-wrap gap-4" style={{ color: "var(--gd-text-2)" }}>
          <span>
            job های GoldDesk:{" "}
            <span className="font-mono" style={{ color: "var(--gd-text)" }}>
              {freshness?.scheduler_jobs ?? health?.scheduler_jobs ?? "—"}
            </span>
          </span>
          <span>
            آخرین اسنپ‌شات:{" "}
            <span className="font-mono" style={{ color: "var(--gd-text)" }}>
              {health?.last_snapshot_at ?? "—"}
            </span>
          </span>
          <span>
            DB: <span className={health?.db_ok ? "text-emerald-400" : "text-rose-400"}>{health?.db_ok ? "✓" : "✗"}</span> |
            Redis: <span className={health?.redis_ok ? "text-emerald-400" : "text-amber-400"}>{health?.redis_ok ? "✓" : "✗"}</span>
          </span>
        </div>
      </div>

      <div
        className="rounded-xl overflow-hidden"
        style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}
      >
        <div className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
          منابع داده ({freshness?.sources.length ?? 0})
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-sm" style={{ color: "var(--gd-text-2)" }}>
            در حال بارگذاری...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
                  <th className="text-right p-3">منبع</th>
                  <th className="text-left p-3">وضعیت</th>
                  <th className="text-left p-3">سن</th>
                  <th className="text-left p-3">ردیف</th>
                  <th className="text-left p-3">حد مجاز</th>
                  <th className="text-left p-3">جزئیات</th>
                </tr>
              </thead>
              <tbody>
                {(freshness?.sources ?? []).map((s) => (
                  <SourceRow key={s.key} source={s} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="text-[11px] leading-6" style={{ color: "var(--gd-text-3)" }}>
        «قدیمی» یعنی داده موجود است ولی از حداکثر سن مجاز گذشته — معمولاً چون sync مربوطه در این محیط اجرا نمی‌شود.
        «خالی» یعنی جدول وجود دارد ولی هنوز ردیفی ندارد (مثلاً تا وقتی خریدی در پرتفوی ثبت نشده).
      </div>
    </div>
  );
}
