"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface BacktestStrategy {
  name: string;
  type: string;
  class_name: string;
  params: Array<{ name: string; type: string; default: unknown }>;
}

interface MLModel {
  id: string;
  name: string;
  task: string;
  framework: string;
  tags: string[];
  versions: Array<{
    version: string;
    stage: string;
    metrics: Record<string, number>;
    created_at: string;
  }>;
  created_at: string;
}

interface DashboardResponse {
  metrics: {
    total_instruments: number;
    active_signals: number;
    total_volume: number;
    total_db_records: number;
    total_users: number;
    active_users: number;
    weekly_active_users: number;
    total_trades: number;
    total_news: number;
    today_records: number;
  };
  user_stats: {
    total_users: number;
    active_users: number;
    weekly_active: number;
  };
  daily_records: Record<string, number>;
  job_stats: {
    total_runs: number;
    successful: number;
    failed: number;
    running: number;
    avg_duration: number;
  };
  recent_jobs: Array<{
    id: string;
    job_type: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number;
    error_message: string | null;
  }>;
  table_rows: Array<{ table: string; rows: number }>;
  ml_models: MLModel[];
  strategies: BacktestStrategy[];
  system_status: string;
}

interface BrsapiSection {
  id: string;
  name: string;
  name_en: string;
  icon: string;
  category: string;
  record_count: number;
  last_sync: {
    status: string | null;
    items_count: number;
    duration_ms: number;
    completed_at: string | null;
    error_message: string | null;
  } | null;
}

// ── Helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatDuration(sec: number): string {
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s.toFixed(0)}s`;
}

function formatTimeOnly(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "completed": return "bg-accent-emerald/15 text-accent-emerald";
    case "failed": return "bg-accent-rose/15 text-accent-rose";
    case "running": return "bg-accent-amber/15 text-accent-amber";
    case "pending": return "bg-surface-700 text-surface-400";
    default: return "bg-surface-800 text-surface-500";
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed": return "موفق";
    case "failed": return "خطا";
    case "running": return "در حال اجرا";
    case "pending": return "در صف";
    default: return status;
  }
}

// ── Component ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { data: dash } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: async () => {
      const res = await apiGet<DashboardResponse>("/dashboard");
      return res as DashboardResponse;
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
  });

  const { data: sections } = useQuery({
    queryKey: ["brsapi-sections"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: BrsapiSection[] }>("/brsapi/manage/sections");
      return res.data || [];
    },
    refetchInterval: 600_000,
    staleTime: 300_000,
  });

  const m = dash?.metrics;
  const jobs = dash?.job_stats;
  const recentJobs = dash?.recent_jobs || [];
  const mlModels = dash?.ml_models || [];
  const backtestStrategies = dash?.strategies || [];

  const totalRecords = sections?.reduce((sum, s) => sum + s.record_count, 0) || 0;
  const syncedSections = sections?.filter((s) => s.last_sync?.status === "success").length || 0;
  const failedSections = sections?.filter((s) => s.last_sync?.status === "error").length || 0;

  // Group sections by category
  const categories: Record<string, BrsapiSection[]> = {};
  for (const s of sections || []) {
    if (!categories[s.category]) categories[s.category] = [];
    categories[s.category].push(s);
  }

  const CATEGORY_LABELS: Record<string, { label: string; icon: string }> = {
    tsetmc: { label: "بورس (TSETMC)", icon: "📊" },
    ime: { label: "بورس کالا (IME)", icon: "🛢️" },
    commodity: { label: "کالاهای جهانی", icon: "🌍" },
    cryptocurrency: { label: "ارز دیجیتال", icon: "₿" },
    codal: { label: "کدال", icon: "🏢" },
  };

  const dailyEntries = dash?.daily_records ? Object.entries(dash.daily_records).filter(([, v]) => v > 0) : [];

  return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت سیستم، دیتابیس و همگام‌سازی">
      {/* ── Metrics Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-primary-400">storage</span>
            <span className="text-xs text-surface-500">کل رکوردها</span>
          </div>
          <div className="text-2xl font-bold gradient-text">
            {m?.total_db_records !== undefined ? formatNumber(m.total_db_records) : <Skeleton className="h-8 w-24" />}
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-accent-emerald">people</span>
            <span className="text-xs text-surface-500">کاربران</span>
          </div>
          <div className="text-2xl font-bold text-surface-200">
            {m?.total_users !== undefined ? (
              <>
                {formatNumber(m.total_users)}
                <span className="text-sm text-surface-500 mr-1">
                  ({formatNumber(m.active_users)} فعال)
                </span>
              </>
            ) : <Skeleton className="h-8 w-20" />}
          </div>
          {m?.weekly_active_users !== undefined && m.weekly_active_users > 0 && (
            <p className="text-[10px] text-surface-600 mt-0.5">
              {formatNumber(m.weekly_active_users)} کاربر هفتگی
            </p>
          )}
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-accent-amber">today</span>
            <span className="text-xs text-surface-500">امروز</span>
          </div>
          <div className="text-2xl font-bold text-surface-200">
            {m?.today_records !== undefined ? (
              <>
                {formatNumber(m.today_records)}
                <span className="text-sm text-surface-500 mr-1">رکورد</span>
              </>
            ) : <Skeleton className="h-8 w-16" />}
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className={`material-icons ${(jobs?.failed || 0) > 0 ? "text-accent-rose" : "text-surface-500"}`}>
              {(jobs?.failed || 0) > 0 ? "warning" : "check_circle"}
            </span>
            <span className="text-xs text-surface-500">وضعیت سیستم</span>
          </div>
          <div className={`text-lg font-bold ${
            dash?.system_status === "healthy" ? "text-accent-emerald" :
            dash?.system_status === "warning" ? "text-accent-amber" :
            "text-accent-rose"
          }`}>
            {dash?.system_status === "healthy" ? "✅ سالم" :
             dash?.system_status === "warning" ? "⚠️ هشدار" :
             dash?.system_status === "degraded" ? "🔴 مختل" : <Skeleton className="h-8 w-16" />}
          </div>
        </div>
      </div>

      {/* ── Job Stats + Daily Activity Row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Job Stats */}
        <div className="glass-card p-4">
          <h3 className="text-sm font-bold text-surface-200 mb-3">⚙️ وضعیت Job‌ها (۷ روز)</h3>
          {jobs ? (
            <div className="grid grid-cols-5 gap-3 text-center">
              <div>
                <p className="text-xl font-bold text-surface-200">{formatNumber(jobs.total_runs)}</p>
                <p className="text-[10px] text-surface-500">کل</p>
              </div>
              <div>
                <p className="text-xl font-bold text-accent-emerald">{formatNumber(jobs.successful)}</p>
                <p className="text-[10px] text-surface-500">موفق</p>
              </div>
              <div>
                <p className={`text-xl font-bold ${jobs.failed > 0 ? "text-accent-rose" : "text-surface-400"}`}>
                  {formatNumber(jobs.failed)}
                </p>
                <p className="text-[10px] text-surface-500">خطا</p>
              </div>
              <div>
                <p className="text-xl font-bold text-accent-amber">{formatNumber(jobs.running)}</p>
                <p className="text-[10px] text-surface-500">در حال اجرا</p>
              </div>
              <div>
                <p className="text-xl font-bold text-primary-400">{jobs.avg_duration > 0 ? `${jobs.avg_duration.toFixed(1)}s` : "—"}</p>
                <p className="text-[10px] text-surface-500">میانگین</p>
              </div>
            </div>
          ) : (
            <Skeleton className="h-14 w-full" />
          )}
        </div>

        {/* Daily Activity */}
        <div className="glass-card p-4">
          <h3 className="text-sm font-bold text-surface-200 mb-3">📊 فعالیت امروز</h3>
          {m?.today_records !== undefined ? (
            dailyEntries.length > 0 ? (
              <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                {dailyEntries.map(([key, val]) => (
                  <div key={key} className="flex items-center gap-1.5">
                    <span className="text-xs font-mono text-surface-200 font-bold">
                      {formatNumber(val)}
                    </span>
                    <span className="text-[10px] text-surface-500">
                      {key.replace("_today", "").replace("_", " ")}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-surface-600">هیچ رکوردی امروز ثبت نشده</p>
            )
          ) : (
            <Skeleton className="h-8 w-full" />
          )}
        </div>
      </div>

      {/* ── Recent Jobs ── */}
      {recentJobs.length > 0 && (
        <div className="glass-card p-4 mb-6">
          <h3 className="text-sm font-bold text-surface-200 mb-3">🔄 آخرین Job‌ها</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="text-right py-2 px-2">نوع</th>
                  <th className="text-right py-2 px-2">وضعیت</th>
                  <th className="text-right py-2 px-2">مدت</th>
                  <th className="text-right py-2 px-2">زمان</th>
                  <th className="text-right py-2 px-2">خطا</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.slice(0, 10).map((job) => (
                  <tr key={job.id} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                    <td className="py-2 px-2 font-mono text-surface-300">{job.job_type}</td>
                    <td className="py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadgeClass(job.status)}`}>
                        {statusLabel(job.status)}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-surface-400">{job.duration_seconds > 0 ? formatDuration(job.duration_seconds) : "—"}</td>
                    <td className="py-2 px-2 text-surface-500">{formatTimeOnly(job.completed_at || job.started_at)}</td>
                    <td className="py-2 px-2 text-accent-rose max-w-[120px] truncate" title={job.error_message || ""}>
                      {job.error_message || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Database Tables by Category ── */}
      <h2 className="text-lg font-bold text-surface-200 mb-4">📋 وضعیت دیتابیس</h2>
      {!sections ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-40 w-full" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {Object.entries(categories).map(([cat, catSections]) => {
            const cfg = CATEGORY_LABELS[cat] || { label: cat, icon: "📦" };
            const total = catSections.reduce((s, sec) => s + sec.record_count, 0);
            return (
              <div key={cat} className="glass-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span>{cfg.icon}</span>
                    <h3 className="font-bold text-surface-200 text-sm">{cfg.label}</h3>
                  </div>
                  <span className="text-xs text-surface-400 bg-surface-800 px-2 py-0.5 rounded-full">
                    {formatNumber(total)} رکورد
                  </span>
                </div>
                <div className="space-y-1">
                  {catSections.map((sec) => (
                    <div key={sec.id} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface-800/50 transition-colors">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                          sec.last_sync?.status === "success" ? "bg-accent-emerald" :
                          sec.last_sync?.status === "error" ? "bg-accent-rose" :
                          "bg-surface-600"
                        }`} />
                        <span className="text-xs text-surface-300 truncate">{sec.name}</span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-xs font-mono text-surface-500">
                          {formatNumber(sec.record_count)}
                        </span>
                        {sec.last_sync?.status === "success" && (
                          <span className="text-[10px] text-surface-600">
                            {(sec.last_sync.duration_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                        {sec.last_sync?.status === "error" && (
                          <span className="text-[10px] text-accent-rose" title={sec.last_sync.error_message || ""}>
                            خطا
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Quick Actions ── */}
      <h2 className="text-lg font-bold text-surface-200 mb-4">⚡ اقدامات سریع</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Link href="/brsapi" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📡</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">مدیریت داده</p>
          <p className="text-xs text-surface-500 mt-0.5">دریافت و همگام‌سازی داده‌های BrsApi</p>
        </Link>
        <Link href="/quotes/import" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📥</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">ورود قیمت</p>
          <p className="text-xs text-surface-500 mt-0.5">بارگذاری CSV قیمت‌های روزانه</p>
        </Link>
        <Link href="/news" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📰</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">اخبار بازار</p>
          <p className="text-xs text-surface-500 mt-0.5">مشاهده آخرین اخبار و رویدادها</p>
        </Link>
        <Link href="/settings" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">⚙️</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">تنظیمات</p>
          <p className="text-xs text-surface-500 mt-0.5">تنظیمات کاربری و سیستم</p>
        </Link>
      </div>

      {/* ── ML Models Section ── */}
      {/* ── Backtesting Strategies Section ── */}
      {backtestStrategies.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-bold text-surface-200 mb-4">📊 استراتژی‌های بک‌تست</h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            {backtestStrategies.map((strategy, si) => (
              <div key={`${strategy.name}-${si}`} className="glass-card p-3 hover:bg-surface-800/60 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-bold text-surface-100 text-sm">{strategy.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-purple/15 text-accent-purple">
                    {strategy.type}
                  </span>
                </div>
                <p className="text-[10px] text-surface-500 font-mono">{strategy.class_name}</p>
                {strategy.params.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {strategy.params.map((p: { name: string; type: string; default: unknown }, pi) => (
                      <span key={`${p.name}-${pi}`} className="text-[9px] px-1.5 py-0.5 bg-surface-800 text-surface-400 rounded-full">
                        {p.name}: {p.default != null ? String(p.default) : "-"}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── ML Models Section ── */}
      {mlModels.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-bold text-surface-200 mb-4">🧠 مدل‌های یادگیری ماشین</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {mlModels.map((model) => {
              const latestVersion = model.versions?.[model.versions.length - 1];
              const latestMetrics = latestVersion?.metrics || {};
              const accuracy = latestMetrics.accuracy != null ? (latestMetrics.accuracy * 100).toFixed(1) : null;
              const stageColors: Record<string, string> = {
                production: "bg-accent-emerald/15 text-accent-emerald",
                staging: "bg-accent-amber/15 text-accent-amber",
                development: "bg-surface-600/30 text-surface-400",
              };
              return (
                <div key={model.id} className="glass-card p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-surface-100 text-sm">{model.name}</span>
                        <span className="text-[10px] font-mono bg-surface-800 px-1.5 py-0.5 rounded text-surface-500">{model.id}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-surface-500">
                        <span>📋 {model.task}</span>
                        <span>🔧 {model.framework}</span>
                      </div>
                    </div>
                    <div className="flex gap-1 flex-wrap shrink-0">
                      {model.tags?.map((t: string) => (
                        <span key={t} className="text-[9px] px-1.5 py-0.5 rounded-full bg-primary-600/10 text-primary-300">{t}</span>
                      ))}
                      {latestVersion && (
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${stageColors[latestVersion.stage] || stageColors.development}`}>
                          {latestVersion.stage}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    {accuracy && (
                      <div className="flex items-center gap-1">
                        <span className="text-surface-500">دقت:</span>
                        <span className={`font-mono font-bold ${
                          parseFloat(accuracy) >= 85 ? "text-accent-emerald" :
                          parseFloat(accuracy) >= 75 ? "text-accent-amber" : "text-accent-rose"
                        }`}>{accuracy}%</span>
                      </div>
                    )}
                    {latestVersion && (
                      <>
                        <div className="flex items-center gap-1">
                          <span className="text-surface-500">ورژن:</span>
                          <span className="font-mono text-surface-300">{latestVersion.version}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-surface-500">ورژن‌ها:</span>
                          <span className="font-mono text-surface-300">{model.versions.length}</span>
                        </div>
                      </>
                    )}
                    {!latestVersion && (
                      <span className="text-surface-600 text-[10px]">بدون ورژن</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── System Info ── */}
      <div className="glass-card p-4">
        <h3 className="font-bold text-surface-200 text-sm mb-3">ℹ️ اطلاعات سیستم</h3>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          <div>
            <span className="text-surface-500">دیتابیس:</span>
            <span className="text-surface-300 mr-1 font-mono">PostgreSQL</span>
          </div>
          <div>
            <span className="text-surface-500">API:</span>
            <span className="text-surface-300 mr-1 font-mono">FastAPI + Python</span>
          </div>
          <div>
            <span className="text-surface-500">فرانت‌اند:</span>
            <span className="text-surface-300 mr-1 font-mono">Next.js + React</span>
          </div>
          <div>
            <span className="text-surface-500">جدول‌های BrsApi:</span>
            <span className="text-surface-300 mr-1 font-mono">{sections?.length || "—"}</span>
          </div>
          <div>
            <span className="text-surface-500">جدول‌های دیتابیس:</span>
            <span className="text-surface-300 mr-1 font-mono">{dash?.table_rows?.length || "—"}</span>
          </div>
          <div>
            <span className="text-surface-500">وضعیت:</span>
            <span className={`mr-1 font-semibold ${
              dash?.system_status === "healthy" ? "text-accent-emerald" :
              dash?.system_status === "warning" ? "text-accent-amber" :
              "text-accent-rose"
            }`}>
              {dash?.system_status === "healthy" ? "✅ همه چیز سالم" :
               dash?.system_status === "warning" ? "⚠️ نیاز به توجه" :
               dash?.system_status === "degraded" ? "🔴 نیاز به بررسی" : "—"}
            </span>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
