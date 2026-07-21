"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";

// ── Dynamic chart (prevent SSR issues with Recharts) ──
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 200 }} />,
});

// ── Types ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface SchedulerJob {
  name: string;
  enabled: boolean;
  cron: string;
  description: string;
  endpoint: string;
  category: string;
  next_run_time: string | null;
}

interface SchedulerResponse {
  jobs: SchedulerJob[];
  total: number;
  enabled: number;
  disabled: number;
}

interface ToggleResult {
  name: string;
  enabled: boolean;
  message: string;
}

interface RunResult {
  name: string;
  success: boolean;
  items_count?: number;
  duration_ms?: number;
  message?: string;
}

interface SyncLogEntry {
  time: string;
  endpoint: string;
  category: string;
  status: string;
  items_count: number;
  duration_ms: number;
  completed_at: string | null;
}

// ── Config ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; icon: string }> = {
  tsetmc:    { label: "بورس",      icon: "📈" },
  ime:       { label: "کالا",      icon: "🛢️" },
  commodity: { label: "کامودیتی",  icon: "🌍" },
  crypto:    { label: "کریپتو",    icon: "₿"  },
  gold:      { label: "طلا و ارز", icon: "🥇" },
  codal:     { label: "کدال",      icon: "🏢" },
};

function getCategoryInfo(cat: string): { label: string; icon: string } {
  return CATEGORY_CONFIG[cat] || { label: cat, icon: "📦" };
}

function formatCron(cron: string): string {
  const n = Number(cron);
  if (Number.isInteger(n)) {
    if (n < 60) return `هر ${n} ثانیه`;
    if (n < 3600) return `هر ${n / 60} دقیقه`;
    return `هر ${n / 3600} ساعت`;
  }
  // Standard cron like "0 18 * * *"
  const parts = cron.split(" ");
  if (parts.length === 5) {
    if (cron === "0 9 * * *") return "روزانه ۹:۰۰";
    if (cron === "0 18 * * *") return "روزانه ۱۸:۰۰";
    return cron;
  }
  return cron;
}

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < -60) return `در ${Math.abs(Math.floor(diffSec / 60))} دقیقه آینده`;
    if (diffSec < 0) return "همین الان";
    if (diffSec < 60) return `${diffSec} ثانیه پیش`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} دقیقه پیش`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} ساعت پیش`;
    return `${Math.floor(diffHr / 24)} روز پیش`;
  } catch {
    return "—";
  }
}

function formatTime(isoStr: string | null): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

// ── Toast ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: "success" | "error"; onClose: () => void }) {
  const ref = useRef(onClose);
  ref.current = onClose;
  useEffect(() => {
    const t = setTimeout(() => ref.current(), 4000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium border ${
      type === "success"
        ? "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30"
        : "bg-accent-rose/15 text-accent-rose border-accent-rose/30"
    }`} style={{ animation: "slideUp 0.3s ease-out" }}>
      <span className="material-icons text-lg">{type === "success" ? "check_circle" : "error"}</span>
      <span>{message}</span>
      <button onClick={onClose} className="mr-3 opacity-60 hover:opacity-100"><span className="material-icons">close</span></button>
      <style>{`@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}`}</style>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function SchedulerStatusPage() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [toggling, setToggling] = useState<Record<string, boolean>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("48h");

  // ── Time range helpers ──
  const timeRangeHours = timeRange === "24h" ? 24 : timeRange === "48h" ? 48 : timeRange === "7d" ? 168 : timeRange === "30d" ? 720 : 48;
  const timeRangeLabel = { "24h": "۲۴ ساعت", "48h": "۴۸ ساعت", "7d": "۷ روز", "30d": "۳۰ روز" }[timeRange] || "۴۸ ساعت";

  // ── Fetch sync history for chart ──
  const { data: syncHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["brsapi-scheduler-history", timeRange],
    queryFn: async (): Promise<SyncLogEntry[]> => {
      const res = await apiGet<{ success: boolean; data: SyncLogEntry[] }>(`/brsapi/sync-history?hours=${timeRangeHours}&limit=300`);
      return res?.data ?? [];
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  // ── Build chart data ──
  const chartData = syncHistory
    ? (() => {
        const buckets: Record<string, { time: string; success: number; error: number }> = {};
        for (const entry of syncHistory) {
          if (!entry.time) continue;
          const d = new Date(entry.time);
          const hourKey = d.toISOString().slice(0, 13) + ":00";
          if (!buckets[hourKey]) buckets[hourKey] = { time: hourKey, success: 0, error: 0 };
          if (entry.status === "success") buckets[hourKey].success++;
          else buckets[hourKey].error++;
        }
        return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
      })()
    : [];

  // ── Fetch scheduler jobs ──
  const { data: schedulerData, isLoading, isError } = useQuery({
    queryKey: ["brsapi-scheduler"],
    queryFn: async (): Promise<SchedulerResponse> => {
      const res = await apiGet<{ success: boolean; data: SchedulerResponse }>("/jobs/scheduler");
      return res?.data ?? { jobs: [], total: 0, enabled: 0, disabled: 0 };
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}min`;
  }

  // ── Toggle job ──
  const handleToggle = useCallback(async (jobName: string) => {
    setToggling(p => ({ ...p, [jobName]: true }));
    try {
      const res = await apiPost<{ success: boolean; data: ToggleResult }>(`/jobs/scheduler/${jobName}/toggle`);
      if (res?.success && res.data) {
        setToast({
          message: `${res.data.enabled ? "✅ فعال" : "⏸️ غیرفعال"} شد: ${res.data.name}`,
          type: "success",
        });
        queryClient.invalidateQueries({ queryKey: ["brsapi-scheduler"] });
      } else {
        setToast({ message: `❌ خطا: ${res?.data?.message || "نامشخص"}`, type: "error" });
      }
    } catch (err) {
      setToast({ message: `❌ ${String(err)}`, type: "error" });
    } finally {
      setToggling(p => ({ ...p, [jobName]: false }));
    }
  }, [queryClient]);

  // ── Run Now ──
  const handleRunNow = useCallback(async (jobName: string) => {
    setRunning(p => ({ ...p, [jobName]: true }));
    try {
      const res = await apiPost<{ success: boolean; data: RunResult }>(`/jobs/scheduler/${jobName}/run`);
      if (res?.success && res.data?.success) {
        setToast({
          message: `✅ ${jobName}: ${res.data.items_count ?? 0} آیتم در ${formatDuration(res.data.duration_ms ?? 0)}`,
          type: "success",
        });
      } else {
        setToast({
          message: `❌ ${jobName}: ${res?.data?.message || "خطا"}`,
          type: "error",
        });
      }
      queryClient.invalidateQueries({ queryKey: ["brsapi-scheduler"] });
    } catch (err) {
      setToast({ message: `❌ ${jobName}: ${String(err)}`, type: "error" });
    } finally {
      setRunning(p => ({ ...p, [jobName]: false }));
    }
  }, [queryClient]);

  // ── Filter & group jobs ──
  const jobs = schedulerData?.jobs ?? [];
  const filteredJobs = jobs.filter(j => {
    if (filterCategory !== "all" && j.category !== filterCategory) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      return j.name.toLowerCase().includes(q) || j.description.toLowerCase().includes(q);
    }
    return true;
  });

  // Sort: enabled first, then by name
  filteredJobs.sort((a, b) => {
    if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  // ── Categories for filter ──
  const categories = Array.from(new Set(jobs.map(j => j.category))).sort();
  if (categories.length === 0) categories.push("all");

  const total = schedulerData?.total ?? 0;
  const enabledCount = schedulerData?.enabled ?? 0;
  const disabledCount = schedulerData?.disabled ?? 0;

  return (
    <AppLayout title="⏱️ وضعیت زمان‌بندی (Scheduler)" subtitle="مدیریت و مشاهده jobهای همگام‌سازی خودکار BrsApi">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="glass-card p-3.5 text-center">
          <p className="text-2xl font-black text-surface-200">{total}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">کل Jobها</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${enabledCount > 0 ? "text-accent-emerald" : "text-surface-600"}`}>{enabledCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">فعال</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${disabledCount > 0 ? "text-surface-400" : "text-surface-600"}`}>{disabledCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">غیرفعال</p>
        </div>
      </div>

      {/* ── Freshness Chart with Time Range ── */}
      <div className="mb-5">
        <Card title={"📈 تاریخچه Sync (" + timeRangeLabel + ")"} actions={
          <div className="flex items-center gap-2">
            {["24h", "48h", "7d", "30d"].map(r => (
              <button key={r} onClick={() => setTimeRange(r)}
                className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-all ${
                  timeRange === r
                    ? "bg-primary-600/30 text-primary-300"
                    : "text-surface-500 hover:text-surface-300"
                }`}>
                {r === "24h" ? "۲۴h" : r === "48h" ? "۴۸h" : r === "7d" ? "۷d" : "۳۰d"}
              </button>
            ))}
          </div>
        }>
          {historyLoading ? (
            <Skeleton className="h-[200px] w-full rounded-xl" />
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-[180px] text-surface-500 text-sm">
              داده‌ای برای نمایش وجود ندارد
            </div>
          ) : (
            <AreaChartCard
              title=""
              data={chartData.map(d => ({ date: d.time.slice(11, 16), time: d.time.slice(11, 16), value: d.success, error: d.error }))}
              dataKey="success"
              height={260}
              yAxisFormatter={(v) => `${v}`}
              strokeColor="#10b981"
              gradientId="schedulerFreshnessGradient"
              showAverage
              showMinMax
              crosshair
              animate
              primaryLabel="موفق"
              yAxisLabel="تعداد عملیات"
              additionalSeries={[{
                dataKey: "error",
                strokeColor: "#FF5252",
                gradientId: "schedulerErrorGradient",
                label: "خطا",
                asBar: true,
                barFill: "#ef4444",
              }]}
            />
          )}
        </Card>
      </div>

      {/* ── Filters ── */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2 bg-surface-800/50 rounded-xl px-3 py-2 border border-surface-700/50 flex-1 min-w-[200px]">
          <span className="text-surface-500 text-sm">🔍</span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="جستجوی job..."
            className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="text-surface-500 hover:text-surface-300 text-xs">✕</button>
          )}
        </div>

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="bg-surface-800/50 text-sm text-surface-300 border border-surface-700/50 rounded-xl px-3 py-2 outline-none cursor-pointer"
        >
          <option value="all">📂 همه دسته‌ها</option>
          {categories.map(cat => {
            const ci = getCategoryInfo(cat);
            return <option key={cat} value={cat}>{ci.icon} {ci.label}</option>;
          })}
        </select>
      </div>

      {/* ── Jobs Table ── */}
      <Card title="📋 لیست Jobهای زمان‌بندی" actions={
        <span className="text-[10px] text-surface-600">
          {filteredJobs.length} از {jobs.length} job
        </span>
      }>
        {isLoading ? (
          <div className="space-y-3">{[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}</div>
        ) : isError ? (
          <p className="text-accent-rose text-sm text-center py-8">خطا در دریافت وضعیت scheduler</p>
        ) : filteredJobs.length === 0 ? (
          <p className="text-surface-500 text-sm text-center py-8">
            {searchQuery ? "هیچ jobی با این جستجو یافت نشد" : "هیچ jobی ثبت نشده است"}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-3 px-3">وضعیت</th>
                  <th className="pb-3 px-3">نام Job</th>
                  <th className="pb-3 px-3">دسته‌بندی</th>
                  <th className="pb-3 px-3">برنامه</th>
                  <th className="pb-3 px-3">Endpoint</th>
                  <th className="pb-3 px-3 text-center">اجرای بعدی</th>
                  <th className="pb-3 px-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => {
                  const isToggling = toggling[job.name] ?? false;
                  const isRunning = running[job.name] ?? false;
                  const ci = getCategoryInfo(job.category);
                  const statusDot = job.enabled
                    ? "bg-accent-emerald shadow-[0_0_6px_rgba(52,211,153,0.4)]"
                    : "bg-surface-600";
                  const rowBg = job.enabled ? "" : "opacity-60";

                  return (
                    <tr key={job.name} className={`border-b border-surface-800/30 transition-colors hover:bg-surface-800/20 ${rowBg}`}>
                      {/* Status indicator */}
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusDot}`} />
                          <span className={`text-[10px] font-bold ${job.enabled ? "text-accent-emerald" : "text-surface-500"}`}>
                            {job.enabled ? "فعال" : "غیرفعال"}
                          </span>
                        </div>
                      </td>

                      {/* Job name + description */}
                      <td className="py-3 px-3 max-w-[260px]">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold text-surface-200 font-mono text-xs">{job.name}</span>
                          <span className="text-[10px] text-surface-500 leading-tight line-clamp-2" title={job.description}>
                            {job.description}
                          </span>
                        </div>
                      </td>

                      {/* Category */}
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-surface-800 text-surface-400 text-[10px]">
                          {ci.icon}
                          {ci.label}
                        </span>
                      </td>

                      {/* Cron schedule */}
                      <td className="py-3 px-3">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-mono text-surface-300 text-[10px]">{formatCron(job.cron)}</span>
                          <span className="text-[9px] text-surface-600" dir="ltr">{job.cron}</span>
                        </div>
                      </td>

                      {/* Endpoint */}
                      <td className="py-3 px-3 max-w-[200px]">
                        <span className="text-[10px] text-surface-400 font-mono truncate block" title={job.endpoint}>
                          {job.endpoint}
                        </span>
                      </td>

                      {/* Next run */}
                      <td className="py-3 px-3 text-center">
                        {job.enabled && job.next_run_time ? (
                          <span className="text-[10px] text-surface-400" title={job.next_run_time}>
                            {formatTime(job.next_run_time)}
                            <br />
                            <span className="text-[9px] text-surface-600">{formatRelativeTime(job.next_run_time)}</span>
                          </span>
                        ) : (
                          <span className="text-[10px] text-surface-600">—</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-3">
                        <div className="flex items-center justify-center gap-2">
                          {/* Run Now button */}
                          <button
                            onClick={() => handleRunNow(job.name)}
                            disabled={isRunning}
                            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                              isRunning
                                ? "bg-primary-600/20 text-primary-300 cursor-wait"
                                : "bg-primary-600/10 text-primary-400 border border-primary-600/20 hover:bg-primary-600/20"
                            }`}
                            title="اجرای فوری"
                          >
                            <span className={`material-icons text-sm ${isRunning ? "animate-spin" : ""}`}>
                              {isRunning ? "sync" : "play_arrow"}
                            </span>
                            {isRunning ? "در حال اجرا..." : "Run Now"}
                          </button>

                          {/* Toggle button */}
                          <button
                            onClick={() => handleToggle(job.name)}
                            disabled={isToggling}
                            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                              isToggling
                                ? "bg-surface-800 text-surface-500 cursor-wait"
                                : job.enabled
                                  ? "bg-accent-rose/10 text-accent-rose border border-accent-rose/20 hover:bg-accent-rose/20"
                                  : "bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 hover:bg-accent-emerald/20"
                            }`}
                            title={job.enabled ? "غیرفعال‌سازی" : "فعال‌سازی"}
                          >
                            {isToggling ? (
                              <span className="material-icons text-sm animate-spin">sync</span>
                            ) : (
                              <span className="material-icons text-sm">{job.enabled ? "pause_circle" : "play_circle"}</span>
                            )}
                          </button>
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

      {/* ── Legend ── */}
      <div className="mt-4 flex items-center gap-4 text-[10px] text-surface-500 flex-wrap">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> فعال — job به صورت خودکار اجرا می‌شود</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-surface-600" /> غیرفعال — job اجرا نمی‌شود، نیاز به فعال‌سازی دستی</span>
      </div>
    </AppLayout>
  );
}
