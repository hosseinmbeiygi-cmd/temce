"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface JobItem {
  id: string;
  job_type: string;
  status: string;
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number;
  error_message: string | null;
  triggered_by: string;
  created_at: string | null;
}

interface JobsResponse {
  items: JobItem[];
  total: number;
  limit: number;
  offset: number;
  stats: {
    total: number;
    success: number;
    failed: number;
    running: number;
    pending: number;
  };
  job_types: string[];
}

// ── Constants ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; badge: string }> = {
  success: { label: "موفق", color: "text-accent-emerald", bg: "bg-accent-emerald/10", badge: "bg-accent-emerald/20 text-accent-emerald" },
  failed: { label: "خطا", color: "text-accent-rose", bg: "bg-accent-rose/10", badge: "bg-accent-rose/20 text-accent-rose" },
  running: { label: "در حال اجرا", color: "text-accent-blue", bg: "bg-accent-blue/10", badge: "bg-accent-blue/20 text-accent-blue" },
  pending: { label: "در انتظار", color: "text-accent-amber", bg: "bg-accent-amber/10", badge: "bg-accent-amber/20 text-accent-amber" },
  unknown: { label: "نامشخص", color: "text-surface-400", bg: "bg-surface-800/30", badge: "bg-surface-700/50 text-surface-400" },
};

const ALL_STATUSES = "همه وضعیت‌ها";
const ALL_TYPES = "همه jobها";

const REFRESH_INTERVALS = [
  { value: 5_000, label: "۵ ثانیه" },
  { value: 10_000, label: "۱۰ ثانیه" },
  { value: 30_000, label: "۳۰ ثانیه" },
  { value: 60_000, label: "۱ دقیقه" },
  { value: 0, label: "خاموش" },
] as const;

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatDuration(secs: number): string {
  if (secs < 1) return "<۱s";
  if (secs < 60) return `${Math.round(secs)}s`;
  if (secs < 3600) {
    const m = Math.floor(secs / 60);
    const s = Math.round(secs % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatDateTimeShort(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("fa-IR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

function formatDateTimeFull(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("fa-IR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const [statusFilter, setStatusFilter] = useState<string>(ALL_STATUSES);
  const [typeFilter, setTypeFilter] = useState<string>(ALL_TYPES);
  const [refreshInterval, setRefreshInterval] = useState<number>(10_000);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = new URLSearchParams();
  params.set("limit", String(pageSize));
  params.set("offset", String((page - 1) * pageSize));
  if (statusFilter !== ALL_STATUSES) params.set("status", statusFilter);
  if (typeFilter !== ALL_TYPES) params.set("job_type", typeFilter);

  const { data, isLoading, isError, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["jobs", statusFilter, typeFilter, page],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: JobsResponse }>(
        `/jobs?${params.toString()}`
      );
      return res.data;
    },
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
  });

  const items = data?.items || [];
  const stats = data?.stats || { total: 0, success: 0, failed: 0, running: 0, pending: 0 };
  const jobTypes = data?.job_types || [];
  const totalPages = Math.max(1, Math.ceil((data?.total || 0) / pageSize));

  const statCards = [
    { label: "کل (۷ روز)", value: stats.total, color: "text-surface-100" },
    { label: "موفق", value: stats.success, color: "text-accent-emerald" },
    { label: "خطا", value: stats.failed, color: "text-accent-rose" },
    { label: "در حال اجرا", value: stats.running, color: "text-accent-blue", pulse: stats.running > 0 },
    { label: "در انتظار", value: stats.pending, color: "text-accent-amber" },
  ];

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "";

  return (
    <AppLayout title="⚙️ مانیتورینگ Job‌ها" subtitle="ردیابی و نظارت بر وظایف پس‌زمینه">
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ── Header: Stats + Controls ── */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          {/* Stat cards */}
          <div className="flex flex-wrap gap-2">
            {statCards.map((s) => (
              <div key={s.label} className="glass-card px-3 py-2 text-center min-w-[80px]">
                <p className={`text-lg font-bold ${s.color} ${s.pulse ? "animate-pulse" : ""}`}>
                  {s.value}
                </p>
                <p className="text-[9px] text-surface-500 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Refresh info */}
          <div className="flex items-center gap-2 text-[10px] text-surface-500 shrink-0">
            {lastUpdated && <span>آخرین بروزرسانی: {lastUpdated}</span>}
          </div>
        </div>

        {/* ── Filters ── */}
        <div className="flex flex-wrap gap-3 items-center">
          {/* Status filter */}
          <div className="flex gap-1">
            {[ALL_STATUSES, "success", "failed", "running", "pending"].map((s) => {
              const cfg = STATUS_CONFIG[s] || STATUS_CONFIG.unknown;
              const active = statusFilter === s;
              return (
                <button
                  key={s}
                  onClick={() => { setStatusFilter(s); setPage(1); }}
                  className={`px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                    active
                      ? `${cfg.bg} ${cfg.color} border border-current`
                      : "bg-surface-800/50 text-surface-500 hover:text-surface-300 border border-transparent"
                  }`}
                >
                  {s === ALL_STATUSES ? "🔽 همه" : cfg.label}
                </button>
              );
            })}
          </div>

          {/* Job type filter */}
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            className="bg-surface-800 border border-surface-700 rounded-lg px-2.5 py-1.5 text-[10px] text-surface-300 outline-none focus:border-primary-500"
          >
            <option value={ALL_TYPES}>همه jobها ({jobTypes.length})</option>
            {jobTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <div className="flex-1" />

          {/* Refresh interval */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-surface-500">🔄</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-[10px] text-surface-300 outline-none focus:border-primary-500"
            >
              {REFRESH_INTERVALS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <button
            onClick={() => refetch()}
            className="px-2.5 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-lg text-[10px] transition-colors"
          >
            تازه‌سازی دستی
          </button>
        </div>

        {/* ── Table ── */}
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : isError ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-surface-400 text-sm">خطا در دریافت Job‌ها</p>
            <button onClick={() => refetch()} className="mt-3 px-4 py-2 bg-primary-600 rounded-lg text-sm text-white">
              تلاش مجدد
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-surface-500 text-sm">هیچ Jobی یافت نشد</p>
            <p className="text-[10px] text-surface-600 mt-1">فیلترها را تغییر دهید یا منتظر اجرای Jobها باشید</p>
          </div>
        ) : (
          <>
            {/* Scrollable table wrapper */}
            <div className="overflow-x-auto rounded-xl border border-surface-700/30">
              <table className="w-full text-[10px] border-collapse">
                <thead>
                  <tr className="bg-surface-800/80 text-surface-500">
                    <th className="text-right px-3 py-2 font-medium">نوع Job</th>
                    <th className="text-right px-3 py-2 font-medium">وضعیت</th>
                    <th className="text-right px-3 py-2 font-medium">پیشرفت</th>
                    <th className="text-right px-3 py-2 font-medium">شروع</th>
                    <th className="text-right px-3 py-2 font-medium">مدت</th>
                    <th className="text-right px-3 py-2 font-medium">محرک</th>
                    <th className="text-right px-3 py-2 font-medium">خطا</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((job, idx) => {
                    const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.unknown;
                    const even = idx % 2 === 0;
                    return (
                      <tr key={job.id} className={`${even ? "bg-surface-900/20" : "bg-surface-900/40"} hover:bg-surface-800/60 transition-colors border-t border-surface-800/30`}>
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-surface-200">{job.job_type}</p>
                          <p className="text-[8px] text-surface-600 font-mono mt-0.5">{job.id.slice(0, 12)}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-medium ${cfg.badge}`}>
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          {job.status === "running" ? (
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden max-w-[80px]">
                                <div
                                  className="h-full bg-accent-blue rounded-full transition-all"
                                  style={{ width: `${Math.min(job.progress_pct, 100)}%` }}
                                />
                              </div>
                              <span className="text-[9px] text-surface-400 font-mono">{Math.round(job.progress_pct)}%</span>
                            </div>
                          ) : (
                            <span className="text-surface-500">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-surface-400 font-mono" title={formatDateTimeFull(job.started_at)}>
                          {formatDateTimeShort(job.started_at)}
                        </td>
                        <td className="px-3 py-2.5">
                          {job.duration_seconds > 0 ? (
                            <span className="font-mono text-surface-300">{formatDuration(job.duration_seconds)}</span>
                          ) : (
                            <span className="text-surface-600">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="text-surface-400">{job.triggered_by || "—"}</span>
                        </td>
                        <td className="px-3 py-2.5 max-w-[200px]">
                          {job.error_message ? (
                            <span className="text-accent-rose/80 truncate block" title={job.error_message}>
                              {job.error_message.slice(0, 80)}
                            </span>
                          ) : (
                            <span className="text-surface-600">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ── Pagination ── */}
            <div className="flex items-center justify-between">
              <p className="text-[10px] text-surface-500">
                نمایش {items.length} از {data?.total || 0} Job
                {refreshInterval > 0 && " • بروزرسانی خودکار فعال"}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-[10px] transition-colors"
                >
                  ◀ قبلی
                </button>
                <span className="px-2 py-1.5 text-[10px] text-surface-500">
                  {page} از {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-[10px] transition-colors"
                >
                  بعدی ▶
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── Info Footer ── */}
        <div className="glass-card p-3 text-[10px] text-surface-500 space-y-1">
          <div className="flex flex-wrap gap-4">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> موفق</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-rose" /> خطا</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-blue animate-pulse" /> در حال اجرا</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> در انتظار</span>
          </div>
          <p>داده‌های Job‌ها از جدول job_runs دیتابیس خوانده می‌شود. بروزرسانی خودکار: {refreshInterval > 0 ? "هر " + (refreshInterval / 1000) + " ثانیه" : "خاموش"}</p>
        </div>
      </div>
    </AppLayout>
  );
}
