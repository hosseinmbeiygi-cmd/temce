"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import ChartContainer from "@/components/charts/ChartContainer";
import { apiGet, apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────

interface CountItem {
  count: number;
}
interface JobNameItem extends CountItem {
  name: string;
}
interface ErrorCategoryItem extends CountItem {
  category: string;
}
interface TopErrorItem extends CountItem {
  error: string;
}
interface RepeatedItem extends CountItem {
  job_name: string;
  job_id: string;
}

interface DeadLetterSummary {
  total: number;
  queue: string;
  window?: string;
  since?: number | null;
  malformed: number;
  job_names: JobNameItem[];
  error_categories: ErrorCategoryItem[];
  top_errors: TopErrorItem[];
  repeated: RepeatedItem[];
  repeated_messages: number;
}

interface ReplayResult {
  mode: string;
  total: number;
  replayed: number;
  failed: number;
  discarded: number;
  queue: string;
  dead_queue: string;
  queue_size: number;
  dead_size: number;
}

interface ReplayState {
  status: "idle" | "running" | "done" | "error";
  replayed?: number;
  failed?: number;
  message?: string;
}

const REPLAY_IDLE: ReplayState = { status: "idle" };

const EMPTY: DeadLetterSummary = {
  total: 0, queue: "job:dead", window: "today", since: null, malformed: 0,
  job_names: [], error_categories: [], top_errors: [], repeated: [], repeated_messages: 0,
};

const WINDOWS: { key: string; label: string }[] = [
  { key: "today", label: "امروز" },
  { key: "week", label: "این هفته" },
  { key: "24h", label: "۲۴ ساعت" },
  { key: "all", label: "همه" },
];

// ── Config ────────────────────────────────────────────────────────────

const CATEGORY_META: Record<string, { label: string; color: string; icon: string }> = {
  db_error:      { label: "خطای دیتابیس",   color: "#ef4444", icon: "🗄️" },
  parse_error:   { label: "خطای پارس",      color: "#f59e0b", icon: "🧩" },
  timeout:       { label: "تایم‌اوت",       color: "#a855f7", icon: "⏳" },
  rate_limit:    { label: "محدودیت نرخ",    color: "#f97316", icon: "🚦" },
  http_error:    { label: "خطای HTTP",      color: "#e11d48", icon: "🌐" },
  auth:          { label: "احراز هویت",     color: "#ec4899", icon: "🔐" },
  lock_duplicate:{ label: "قفل/تکراری",     color: "#22d3ee", icon: "🔒" },
  other:         { label: "سایر",           color: "#64748b", icon: "❓" },
  no_error:      { label: "بدون خطا",       color: "#10b981", icon: "✅" },
};

const fallbackMeta = (key: string) => CATEGORY_META[key] ?? { label: key, color: "#64748b", icon: "❓" };

// ── Chart tooltip ─────────────────────────────────────────────────────

function ChartTip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number | string; payload: { full: string } }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-3 py-2 shadow-2xl text-xs border backdrop-blur-xl" style={{ background: "rgba(15,23,42,0.96)", border: "1px solid rgba(71,85,105,0.5)", color: "#e2e8f0" }}>
      <p className="font-bold text-surface-200 text-[11px] mb-1">{label}</p>
      <div className="flex items-center justify-between gap-4">
        <span className="text-surface-400 text-[11px]">تعداد</span>
        <span className="font-mono font-bold text-surface-100" dir="ltr">{Number(payload[0].value).toLocaleString("fa-IR")}</span>
      </div>
    </div>
  );
}

// ── Widget ────────────────────────────────────────────────────────────

export default function DeadLetterWidget() {
  const qc = useQueryClient();
  const [window, setWindow] = useState<string>("today");
  const [armed, setArmed] = useState(false);
  const [replay, setReplay] = useState<ReplayState>(REPLAY_IDLE);
  const windowLabel = WINDOWS.find((w) => w.key === window)?.label ?? window;

  const handleReplay = async () => {
    // Two-step confirm — first click arms, second click executes.
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), 4000);
      return;
    }
    setArmed(false);
    setReplay({ status: "running" });
    try {
      const r = await apiPost<{ success: boolean; data?: ReplayResult; error?: { message?: string } }>(
        "/jobs/queue/replay"
      );
      if (!r?.success) {
        throw new Error(r?.error?.message ?? "بازگشت پیام‌ها ناموفق بود");
      }
      const d = r.data;
      setReplay({
        status: "done",
        replayed: d?.replayed ?? 0,
        failed: d?.failed ?? 0,
        message: `${d?.queue ?? "job:queue"} = ${d?.queue_size ?? "?"} | ${d?.dead_queue ?? "job:dead"} = ${d?.dead_size ?? "?"}`,
      });
      qc.invalidateQueries({ queryKey: ["admin-dead-letter-summary"] });
    } catch (err) {
      setReplay({
        status: "error",
        message: err instanceof Error ? err.message : "خطا در replay",
      });
    }
  };

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["admin-dead-letter-summary", window],
    queryFn: async (): Promise<DeadLetterSummary> => {
      const r = await apiGet<{ success: boolean; data: DeadLetterSummary }>(
        `/jobs/queue/summary?window=${window}`
      );
      return r?.data ?? EMPTY;
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const summary = data ?? EMPTY;

  const chartData = useMemo(
    () =>
      summary.error_categories.map((c) => {
        const meta = fallbackMeta(c.category);
        return { name: meta.icon + " " + meta.label, full: c.category, value: c.count, color: meta.color };
      }),
    [summary.error_categories]
  );

  const totalLabel = summary.total.toLocaleString("fa-IR");

  return (
    <div className="space-y-4">
      {/* Time window selector */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-surface-500">🕒 بازهٔ زمانی:</span>
        <div className="flex gap-1 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              onClick={() => {
                setWindow(w.key);
                setArmed(false); // replay acts on the whole queue — reset confirm on window switch
              }}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap ${
                window === w.key
                  ? "bg-primary-600/30 text-primary-300 shadow-sm"
                  : "text-surface-400 hover:text-surface-200"
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-surface-600">
          {summary.window && summary.window !== "all"
            ? `نمایش پیام‌های dead-letter شده از ${
                summary.since
                  ? new Date(summary.since * 1000).toLocaleString("fa-IR", { dateStyle: "medium" })
                  : "مبدأ"
              }`
            : "نمایش همهٔ پیام‌ها"}
        </span>
      </div>

      {/* Replay action bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap rounded-xl border border-surface-700/40 bg-surface-800/30 p-3">
        <div className="min-w-0">
          <p className="text-[11px] font-bold text-surface-200">🔁 بازگشت پیام‌های dead-letter به صف اصلی</p>
          <p className="text-[9px] text-surface-500 mt-0.5">
            {summary.total > 0
              ? `${summary.total.toLocaleString("fa-IR")} پیام در بازهٔ «${windowLabel}» — replay همهٔ پیام‌های صف (بدون فیلتر بازه) را به صف اصلی برمی‌گرداند.`
              : `در بازهٔ «${windowLabel}» پیامی نیست — replay همهٔ پیام‌های صف را (بدون فیلتر بازه) بررسی می‌کند.`}
          </p>
        </div>
        <button
          onClick={handleReplay}
          disabled={replay.status === "running"}
          className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap border ${
            armed
              ? "bg-accent-amber/20 text-accent-amber border-accent-amber/40 animate-pulse"
              : "bg-accent-rose/15 text-accent-rose border-accent-rose/30 hover:bg-accent-rose/25 disabled:opacity-40 disabled:cursor-not-allowed"
          }`}
        >
          {replay.status === "running"
            ? "⏳ در حال replay..."
            : armed
              ? "⚠️ مطمئنید؟ — دوباره کلیک کنید"
              : "🔁 Replay همهٔ پیام‌ها"}
        </button>
      </div>

      {/* Replay result banner */}
      {replay.status !== "idle" && (
        <div
          className={`flex items-center justify-between gap-3 rounded-xl border p-3 text-xs ${
            replay.status === "running"
              ? "border-primary-500/30 bg-primary-500/10 text-primary-300"
              : replay.status === "done"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : "border-accent-rose/40 bg-accent-rose/10 text-accent-rose"
          }`}
        >
          <span className="min-w-0">
            {replay.status === "running"
              ? "در حال بازگرداندن پیام‌ها به صف اصلی..."
              : replay.status === "done"
                ? `✅ ${(replay.replayed ?? 0).toLocaleString("fa-IR")} پیام replay شد | ❌ ${(replay.failed ?? 0).toLocaleString("fa-IR")} ناموفق — ${replay.message}`
                : `❌ ${replay.message}`}
          </span>
          {replay.status !== "running" && (
            <button
              onClick={() => setReplay(REPLAY_IDLE)}
              className="text-[10px] px-2 py-0.5 rounded-lg hover:bg-surface-800/60 shrink-0"
              aria-label="بستن نتیجه"
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* Metric chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card p-3 text-center">
          <p className={`text-2xl font-black ${summary.total > 0 ? "text-accent-rose" : "text-surface-500"}`}>{totalLabel}</p>
          <p className="text-[9px] text-surface-500">
            {summary.window && summary.window !== "all" ? "پیام در بازه" : `پیام در ${summary.queue}`}
          </p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-black text-surface-200">{summary.job_names.length.toLocaleString("fa-IR")}</p>
          <p className="text-[9px] text-surface-500">Job مختلف</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-2xl font-black text-accent-amber">{summary.repeated_messages.toLocaleString("fa-IR")}</p>
          <p className="text-[9px] text-surface-500">پیام تکراری</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className={`text-2xl font-black ${summary.malformed > 0 ? "text-accent-amber" : "text-surface-500"}`}>{summary.malformed.toLocaleString("fa-IR")}</p>
          <p className="text-[9px] text-surface-500">Malformed</p>
        </div>
      </div>

      {/* Error distribution chart */}
      <Card
        title="🐛 توزیع دسته‌های خطا"
        actions={
          <div className="flex items-center gap-2">
            {isFetching && <span className="text-[10px] text-surface-500 animate-pulse">در حال بروزرسانی...</span>}
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ["admin-dead-letter-summary"] })}
              className="text-[10px] px-2 py-1 rounded-lg bg-surface-800 text-surface-400 border border-surface-700 hover:text-primary-300 transition-all"
            >
              🔄 تازه‌سازی
            </button>
          </div>
        }
      >
        {isLoading ? (
          <Skeleton className="h-[220px] w-full rounded-xl" />
        ) : chartData.length === 0 ? (
          <div className="flex items-center justify-center h-[220px] text-surface-500 text-sm">
            {isError ? "خطا در دریافت داده — Redis در دسترس نیست؟" : "صف dead-letter خالی است — خطایی ثبت نشده 🎉"}
          </div>
        ) : (
          <ChartContainer height={240}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 5 }}>
                <defs>
                  {chartData.map((d, i) => (
                    <linearGradient key={i} id={`dlGrad${i}`} x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor={d.color} stopOpacity={0.85} />
                      <stop offset="100%" stopColor={d.color} stopOpacity={0.35} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.1)" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#64748b", fontSize: 9, fontWeight: 500 }}
                  tickLine={false}
                  axisLine={{ stroke: "rgba(100,116,139,0.15)" }}
                  interval={0}
                  height={40}
                />
                <YAxis
                  tick={{ fill: "#64748b", fontSize: 9 }}
                  tickLine={false}
                  axisLine={{ stroke: "rgba(100,116,139,0.15)" }}
                  width={40}
                  allowDecimals={false}
                />
                <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(148,163,184,0.06)" }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={46} isAnimationActive animationDuration={500}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={`url(#dlGrad${i})`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* job_names table */}
        <Card title="📋 توزیع Jobها" subtitle="کدام جاب‌ها بیشتر dead-letter شده‌اند">
          {isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : summary.job_names.length === 0 ? (
            <p className="text-surface-600 text-sm text-center py-8">—</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="text-right py-2 px-2">نام جاب</th>
                    <th className="text-center py-2 px-2">تعداد</th>
                    <th className="py-2 px-2 w-[40%]">سهم</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.job_names.map((j) => {
                    const pct = summary.total > 0 ? Math.round((j.count / summary.total) * 100) : 0;
                    return (
                      <tr key={j.name} className="border-b border-surface-800/30 hover:bg-surface-800/20">
                        <td className="py-2 px-2 font-mono text-surface-300">{j.name}</td>
                        <td className="py-2 px-2 text-center font-mono font-bold text-surface-200">{j.count.toLocaleString("fa-IR")}</td>
                        <td className="py-2 px-2">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 rounded-full bg-surface-800 overflow-hidden">
                              <div className="h-full rounded-full bg-primary-500/70" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-[9px] text-surface-500 w-8 text-left">{pct}٪</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Repeated messages */}
        <Card title="🔄 پیام‌های تکراری (job_id مشترک)" subtitle="همان پیام چند بار dead شده — نشانهٔ خطای مداوم">
          {isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : summary.repeated.length === 0 ? (
            <p className="text-surface-600 text-sm text-center py-8">هیچ پیام تکراری یافت نشد</p>
          ) : (
            <div className="space-y-2 max-h-[260px] overflow-y-auto">
              {summary.repeated.map((r, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-surface-800/30 border border-surface-700/30">
                  <div className="min-w-0">
                    <p className="font-mono text-surface-200 text-[11px] truncate">{r.job_name}</p>
                    <p className="text-[9px] text-surface-500 font-mono truncate" dir="ltr">{r.job_id}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber text-[10px] font-bold shrink-0">
                    {r.count.toLocaleString("fa-IR")}×
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Top raw errors */}
      {summary.top_errors.length > 0 && (
        <Card title="🔁 خطاهای خام پرتکرار" subtitle="متن دقیق خطاهایی که بیشترین تکرار را داشته‌اند">
          <div className="space-y-1.5">
            {summary.top_errors.map((t, i) => (
              <div key={i} className="flex items-center gap-3 py-1.5 px-3 rounded-lg hover:bg-surface-800/20">
                <span className="w-6 text-center text-[10px] font-bold text-surface-500 shrink-0">{i + 1}</span>
                <span className="px-2 py-0.5 rounded-full bg-accent-rose/10 text-accent-rose text-[10px] font-bold shrink-0">
                  {t.count.toLocaleString("fa-IR")}×
                </span>
                <span className="text-[11px] text-surface-400 font-mono truncate" dir="ltr">{t.error}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
