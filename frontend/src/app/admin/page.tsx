"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import {
  loadSyncSettings, saveSyncSettings, resetSyncSettings,
  DEFAULT_SYNC_SETTINGS, ALL_SECTION_KEYS, type SyncSettingsMap,
} from "@/lib/sync-settings";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false, loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl h-[200px]" />,
});

// ── Types ─────────────────────────────────────────────────────────────────────

interface TableSyncInfo { last_fetched: string | null; record_count: number; age_minutes: number; status: "ok"|"stale"|"outdated"|"missing"|"unknown"|"error"; max_age_minutes: number; error?: string; }
interface SyncLogEntry { time: string; endpoint: string; category: string; status: string; items_count: number; duration_ms: number; completed_at: string | null; }
interface SchedulerJob { name: string; enabled: boolean; cron: string; description: string; endpoint: string; category: string; next_run_time: string | null; }
interface SchedulerResponse { jobs: SchedulerJob[]; total: number; enabled: number; disabled: number; }
interface ImportJob { id: string; job_type: string; status: string; started_at: string | null; completed_at: string | null; duration_seconds: number; error_message: string | null; }
interface ImportResult { total_files?: number; total_rows?: number; imported?: number; updated?: number; errors?: string[]; per_file?: Record<string, { symbol: string; rows: number; imported: number; updated: number }>; }
interface TemplateInfo { label: string; endpoint: string; method: string; accept: string; max_size_mb: number; columns: Array<{ column: string; type: string; required: boolean; desc: string }>; sample_endpoint: string | null; note?: string; }
interface ImportTemplates { instruments: TemplateInfo; quotes: TemplateInfo; codal: TemplateInfo; }
interface TableInfo { name: string; row_count: number; }
interface ColumnInfo { name: string; type: string; }
interface TableData { table: string; columns: ColumnInfo[]; rows: Record<string, unknown>[]; total: number; page: number; page_size: number; total_pages: number; }
interface SearchResult { table: string; total: number; columns: ColumnInfo[]; rows: Record<string, unknown>[]; }
interface DashboardResponse {
  metrics: { total_instruments: number; active_signals: number; total_volume: number; total_db_records: number; total_users: number; active_users: number; weekly_active_users: number; total_trades: number; total_news: number; today_records: number };
  job_stats: { total_runs: number; successful: number; failed: number; running: number; avg_duration: number };
  recent_jobs: Array<{ id: string; job_type: string; status: string; started_at: string | null; completed_at: string | null; duration_seconds: number; error_message: string | null }>;
  table_rows: Array<{ table: string; rows: number }>;
  ml_models: Array<{ id: string; name: string; task: string; framework: string; tags: string[]; versions: Array<{ version: string; stage: string; metrics: Record<string, number> }> }>;
  strategies: Array<{ name: string; type: string; class_name: string; params: Array<{ name: string; type: string; default: unknown }> }>;
  system_status: string; daily_records: Record<string, number>;
  user_stats: { total_users: number; active_users: number; weekly_active: number };
}

// ── Config ────────────────────────────────────────────────────────────────────

type TabKey = "overview"|"sync"|"freshness"|"scheduler"|"import"|"tables";
const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "overview", label: "نمای کلی", icon: "📊" },
  { key: "sync", label: "همگام‌سازی", icon: "🔄" },
  { key: "freshness", label: "تنظیمات", icon: "⚙️" },
  { key: "scheduler", label: "زمان‌بندی", icon: "⏱️" },
  { key: "import", label: "ورود داده", icon: "📥" },
  { key: "tables", label: "مرور جداول", icon: "🗃️" },
];

const TABLE_CONFIG: Record<string, { label: string; icon: string; order: number }> = {
  symbols: { label: "نمادها (بورس)", icon: "📊", order: 1 }, commodities: { label: "کامودیتی‌ها", icon: "🌍", order: 2 },
  gold_coin: { label: "طلا و سکه", icon: "🥇", order: 3 }, currency: { label: "نرخ ارز", icon: "💵", order: 4 },
  crypto: { label: "ارز دیجیتال", icon: "₿", order: 5 }, index: { label: "شاخص‌ها", icon: "📈", order: 6 },
  ime_futures: { label: "آتی کالا", icon: "🛢️", order: 7 }, ime_options: { label: "اختیار کالا", icon: "📋", order: 8 },
  options: { label: "آپشن‌ها", icon: "🎯", order: 9 }, codal: { label: "کدال", icon: "🏢", order: 10 },
};

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  ok: { label: "به‌روز", color: "text-accent-emerald", bg: "bg-accent-emerald/15" },
  stale: { label: "کمی قدیمی", color: "text-accent-amber", bg: "bg-accent-amber/15" },
  outdated: { label: "قدیمی", color: "text-accent-rose", bg: "bg-accent-rose/15" },
  missing: { label: "بدون داده", color: "text-surface-500", bg: "bg-surface-800" },
  unknown: { label: "نامشخص", color: "text-surface-400", bg: "bg-surface-800" },
  error: { label: "خطا", color: "text-accent-rose", bg: "bg-accent-rose/15" },
};

const CATEGORY_CONFIG: Record<string, { label: string; icon: string }> = {
  tsetmc: { label: "بورس", icon: "📈" }, ime: { label: "کالا", icon: "🛢️" },
  commodity: { label: "کامودیتی", icon: "🌍" }, crypto: { label: "کریپتو", icon: "₿" },
  gold: { label: "طلا و ارز", icon: "🥇" }, codal: { label: "کدال", icon: "🏢" },
};

const SECTION_ID_MAP: Record<string, string> = {
  symbols: "all-symbols", commodities: "commodity", gold_coin: "gold-coin",
  currency: "currency", crypto: "crypto", index: "index-tse",
  ime_futures: "ime-futures", ime_options: "ime-options", options: "option", codal: "codal",
};

const IMPORT_TABS = [{ key: "instruments", label: "📋 نمادها", accept: ".csv,.json,.xlsx" }, { key: "quotes", label: "📊 قیمت‌ها", accept: ".csv" }, { key: "codal", label: "🏢 کدال", accept: ".xlsx,.csv" }] as const;

const PRESET_VALUES = [1, 2, 5, 10, 15, 30, 60, 120, 240, 480];
const VALUE_LABELS: Record<number, string> = { 1: "۱ دقیقه", 2: "۲ دقیقه", 5: "۵ دقیقه", 10: "۱۰ دقیقه", 15: "۱۵ دقیقه", 30: "۳۰ دقیقه", 60: "۱ ساعت", 120: "۲ ساعت", 240: "۴ ساعت", 480: "۸ ساعت" };

const SEARCHABLE_TABLES = ["instruments","quotes","trades","signals","recommendations","indicators","news_articles","codal_reports","alerts","backtest_trades","portfolio_positions","orderbooks"];
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number) => n.toLocaleString("fa-IR");
const fmtDur = (ms: number) => ms < 1000 ? `${ms.toFixed(0)}ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)}s` : `${(ms / 60000).toFixed(1)}min`;
const fmtDurSec = (s: number) => s < 1 ? `${(s * 1000).toFixed(0)}ms` : s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
const fmtCron = (c: string) => { const n = Number(c); if (Number.isInteger(n)) { if (n < 60) return `هر ${n} ثانیه`; if (n < 3600) return `هر ${n / 60} دقیقه`; return `هر ${n / 3600} ساعت`; } if (c === "0 9 * * *") return "روزانه ۹:۰۰"; if (c === "0 18 * * *") return "روزانه ۱۸:۰۰"; return c; };
const fmtRel = (iso: string | null) => { if (!iso) return "—"; try { const d = Math.floor((Date.now() - new Date(iso).getTime()) / 1000); if (d < 60) return `${d} ثانیه پیش`; if (d < 3600) return `${Math.floor(d / 60)} دقیقه پیش`; if (d < 86400) return `${Math.floor(d / 3600)} ساعت پیش`; return `${Math.floor(d / 86400)} روز پیش`; } catch { return "—"; } };
const fmtTime = (iso: string | null) => { if (!iso) return "—"; try { return new Date(iso).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" }); } catch { return "—"; } };
const statusBadge = (s: string) => s === "completed" ? "bg-accent-emerald/15 text-accent-emerald" : s === "failed" ? "bg-accent-rose/15 text-accent-rose" : s === "running" ? "bg-accent-amber/15 text-accent-amber" : "bg-surface-700 text-surface-400";
const statusLbl = (s: string) => s === "completed" ? "موفق" : s === "failed" ? "خطا" : s === "running" ? "در حال اجرا" : s;
const nearestPreset = (v: number) => PRESET_VALUES.reduce((p, c) => Math.abs(c - v) < Math.abs(p - v) ? c : p);

// ── Toast ─────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: "success" | "error" | "warning"; onClose: () => void }) {
  const ref = useRef(onClose);
  useEffect(() => { ref.current = onClose; }, [onClose]);
  useEffect(() => { const t = setTimeout(() => ref.current(), 4000); return () => clearTimeout(t); }, []);
  const styles = { success: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30", error: "bg-accent-rose/15 text-accent-rose border-accent-rose/30", warning: "bg-accent-amber/15 text-accent-amber border-accent-amber/30" };
  return (<div className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium border ${styles[type]}`} style={{ animation: "slideUp 0.3s ease-out" }}><span>{message}</span><button onClick={onClose} className="mr-3 opacity-60 hover:opacity-100">✕</button><style>{`@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}`}</style></div>);
}

// ── MAIN PAGE ─────────────────────────────────────────────────────────────────

export default function AdminUnifiedPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>("overview");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "warning" } | null>(null);

  // ══════════════════════════════════════════════════════════════════════════════
  // SHARED QUERIES
  // ══════════════════════════════════════════════════════════════════════════════

  const { data: dash } = useQuery({ queryKey: ["admin-dash"], queryFn: async () => apiGet<DashboardResponse>("/dashboard"), refetchInterval: 300_000, staleTime: 120_000 });

  const { data: syncStatus, isLoading: statusLoading } = useQuery({ queryKey: ["admin-sync-status"], queryFn: async (): Promise<Record<string, TableSyncInfo>> => { const r = await apiGet<{ success: boolean; data: Record<string, TableSyncInfo> }>("/brsapi/sync-status"); return r?.data ?? {}; }, refetchInterval: 60_000, staleTime: 30_000 });

  const { data: schedulerData } = useQuery({ queryKey: ["admin-scheduler"], queryFn: async (): Promise<SchedulerResponse> => { const r = await apiGet<{ success: boolean; data: SchedulerResponse }>("/jobs/scheduler"); return r?.data ?? { jobs: [], total: 0, enabled: 0, disabled: 0 }; }, refetchInterval: 30_000, staleTime: 15_000 });

  // Freshness settings
  const [freshnessSettings, setFreshnessSettings] = useState<SyncSettingsMap>(() => loadSyncSettings());
  useEffect(() => { const h = () => setFreshnessSettings(loadSyncSettings()); window.addEventListener("storage", h); return () => window.removeEventListener("storage", h); }, []);

  const effectiveStatus = useMemo(() => {
    if (!syncStatus) return undefined;
    const result: Record<string, TableSyncInfo> = {};
    for (const [key, info] of Object.entries(syncStatus)) {
      const custom = freshnessSettings[key]; const over = { ...info };
      if (custom && custom.maxAgeMinutes > 0) {
        over.max_age_minutes = custom.maxAgeMinutes;
        if (info.status !== "missing" && info.status !== "error" && info.status !== "unknown" && info.age_minutes != null) {
          over.status = info.age_minutes <= custom.maxAgeMinutes ? "ok" : info.age_minutes <= custom.maxAgeMinutes * 3 ? "stale" : "outdated";
        }
      }
      result[key] = over;
    }
    return result;
  }, [syncStatus, freshnessSettings]);

  // ══════════════════════════════════════════════════════════════════════════════
  // SHARED HELPERS
  // ══════════════════════════════════════════════════════════════════════════════

  const overviewEntries = useMemo(() => {
    if (!effectiveStatus) return [];
    return Object.entries(effectiveStatus).filter(([, i]) => i.record_count > 0 || i.status !== "missing").sort(([a], [b]) => (TABLE_CONFIG[a]?.order ?? 99) - (TABLE_CONFIG[b]?.order ?? 99));
  }, [effectiveStatus]);

  const okCount = overviewEntries.filter(([, i]) => i.status === "ok").length;
  const staleCount = overviewEntries.filter(([, i]) => i.status === "stale").length;
  const outdatedCount = overviewEntries.filter(([, i]) => i.status === "outdated").length;
  const healthScore = overviewEntries.length > 0 ? Math.round((okCount / overviewEntries.length) * 100) : 0;
  const healthColor = healthScore >= 80 ? "text-accent-emerald" : healthScore >= 50 ? "text-accent-amber" : "text-accent-rose";

  const m = dash?.metrics; const jobs = dash?.job_stats; const recentJobs = dash?.recent_jobs || [];
  const dailyEntries = dash?.daily_records ? Object.entries(dash.daily_records).filter(([, v]) => v > 0) : [];
  const schedJobs = schedulerData?.jobs ?? [];

  const handleRunJob = useCallback(async (name: string) => {
    setToast({ message: `🔄 اجرا: ${name}...`, type: "warning" });
    try { const r = await apiPost<{ success: boolean; data: { success: boolean; items_count?: number; duration_ms?: number; message?: string } }>(`/jobs/scheduler/${name}/run`); if (r?.success && r.data?.success) setToast({ message: `✅ ${name}: ${r.data.items_count ?? 0} آیتم در ${fmtDur(r.data.duration_ms ?? 0)}`, type: "success" }); else setToast({ message: `❌ ${r?.data?.message || "خطا"}`, type: "error" }); qc.invalidateQueries({ queryKey: ["admin-scheduler"] }); } catch { setToast({ message: `❌ خطا`, type: "error" }); }
  }, [qc]);

  const handleToggleJob = useCallback(async (name: string) => {
    try { const r = await apiPost<{ success: boolean; data: { enabled: boolean } }>(`/jobs/scheduler/${name}/toggle`); if (r?.success) { setToast({ message: `${r.data.enabled ? "✅ فعال" : "⏸️ غیرفعال"}: ${name}`, type: "success" }); qc.invalidateQueries({ queryKey: ["admin-scheduler"] }); } } catch { setToast({ message: `❌ خطا`, type: "error" }); }
  }, [qc]);

  const handleSyncNow = useCallback(async (key: string) => {
    const id = SECTION_ID_MAP[key]; if (!id) return;
    setToast({ message: `🔄 sync ${TABLE_CONFIG[key]?.label || key}...`, type: "warning" });
    try { const r = await apiPost<{ success: boolean; data: { items_count: number; duration_ms: number } }>(`/brsapi/manage/sync/${id}`); if (r?.success && r.data) setToast({ message: `✅ ${TABLE_CONFIG[key]?.label}: ${r.data.items_count} رکورد در ${fmtDur(r.data.duration_ms)}`, type: "success" }); else setToast({ message: `❌ خطا`, type: "error" }); qc.invalidateQueries({ queryKey: ["admin-sync-status"] }); } catch { setToast({ message: `❌ خطا`, type: "error" }); }
  }, [qc]);

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: OVERVIEW — from /admin + /sync-manager dashboard
  // ══════════════════════════════════════════════════════════════════════════════

  if (tab === "overview") return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
        <div className="glass-card p-3 text-center"><p className={`text-xl font-black ${healthColor}`}>{healthScore}%</p><p className="text-[9px] text-surface-500">سلامت داده</p></div>
        <div className="glass-card p-3 text-center"><p className="text-xl font-black text-accent-emerald">{okCount}</p><p className="text-[9px] text-surface-500">به‌روز</p></div>
        <div className="glass-card p-3 text-center"><p className={`text-xl font-black ${staleCount > 0 ? "text-accent-amber" : "text-surface-600"}`}>{staleCount}</p><p className="text-[9px] text-surface-500">کمی قدیمی</p></div>
        <div className="glass-card p-3 text-center"><p className="text-xl font-black text-primary-400">{schedulerData?.enabled ?? 0}</p><p className="text-[9px] text-surface-500">Scheduler فعال</p></div>
        <div className="glass-card p-3 text-center"><p className="text-xl font-black text-surface-200">{m?.total_db_records !== undefined ? fmt(m.total_db_records) : "—"}</p><p className="text-[9px] text-surface-500">کل رکوردها</p></div>
        <div className="glass-card p-3 text-center"><p className={`text-xl font-bold ${dash?.system_status === "healthy" ? "text-accent-emerald" : dash?.system_status === "warning" ? "text-accent-amber" : "text-accent-rose"}`}>{dash?.system_status === "healthy" ? "سالم" : dash?.system_status === "warning" ? "هشدار" : "—"}</p><p className="text-[9px] text-surface-500">وضعیت</p></div>
      </div>
      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {TABS.map(t => (<button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${tab === t.key ? "bg-primary-600/30 text-primary-300 shadow-sm" : "text-surface-400 hover:text-surface-200"}`}>{t.icon} {t.label}</button>))}
      </div>
      {/* Job Stats + Daily */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card title="وضعیت Job‌ها (۷ روز)">{jobs ? (<div className="grid grid-cols-5 gap-3 text-center">
          <div><p className="text-lg font-bold text-surface-200">{fmt(jobs.total_runs)}</p><p className="text-[9px] text-surface-500">کل</p></div>
          <div><p className="text-lg font-bold text-accent-emerald">{fmt(jobs.successful)}</p><p className="text-[9px] text-surface-500">موفق</p></div>
          <div><p className={`text-lg font-bold ${jobs.failed > 0 ? "text-accent-rose" : "text-surface-400"}`}>{fmt(jobs.failed)}</p><p className="text-[9px] text-surface-500">خطا</p></div>
          <div><p className="text-lg font-bold text-accent-amber">{fmt(jobs.running)}</p><p className="text-[9px] text-surface-500">در حال اجرا</p></div>
          <div><p className="text-lg font-bold text-primary-400">{jobs.avg_duration > 0 ? `${jobs.avg_duration.toFixed(1)}s` : "—"}</p><p className="text-[9px] text-surface-500">میانگین</p></div>
        </div>) : <Skeleton className="h-14 w-full" />}</Card>
        <Card title="فعالیت امروز">{dailyEntries.length > 0 ? (<div className="flex flex-wrap gap-x-4 gap-y-1.5">{dailyEntries.map(([k, v]) => (<div key={k} className="flex items-center gap-1.5"><span className="text-xs font-mono text-surface-200 font-bold">{fmt(v)}</span><span className="text-[9px] text-surface-500">{k.replace("_today", "").replace("_", " ")}</span></div>))}</div>) : <p className="text-xs text-surface-600">هیچ رکوردی امروز ثبت نشده</p>}</Card>
      </div>
      {/* Recent Jobs */}
      {recentJobs.length > 0 && (<Card title="آخرین Job‌ها"><div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-surface-500 border-b border-surface-700"><th className="text-right py-2 px-2">نوع</th><th className="text-right py-2 px-2">وضعیت</th><th className="text-right py-2 px-2">مدت</th><th className="text-right py-2 px-2">زمان</th><th className="text-right py-2 px-2">خطا</th></tr></thead><tbody>{recentJobs.slice(0, 8).map(job => (<tr key={job.id} className="border-b border-surface-800/50 hover:bg-surface-800/30"><td className="py-2 px-2 font-mono text-surface-300">{job.job_type}</td><td className="py-2 px-2"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(job.status)}`}>{statusLbl(job.status)}</span></td><td className="py-2 px-2 text-surface-400">{job.duration_seconds > 0 ? fmtDurSec(job.duration_seconds) : "—"}</td><td className="py-2 px-2 text-surface-500">{fmtTime(job.completed_at || job.started_at)}</td><td className="py-2 px-2 text-accent-rose max-w-[120px] truncate" title={job.error_message || ""}>{job.error_message || "—"}</td></tr>))}</tbody></table></div></Card>)}
      {/* Data Freshness */}
      <Card title="وضعیت جداول"><div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-surface-500 border-b border-surface-700"><th className="pb-2 text-right">بخش</th><th className="pb-2 text-center">وضعیت</th><th className="pb-2 text-center">رکوردها</th><th className="pb-2 text-center">سن</th><th className="pb-2 text-center">عملیات</th></tr></thead><tbody>{overviewEntries.slice(0, 10).map(([key, info]) => { const cfg = TABLE_CONFIG[key] || { label: key, icon: "📦" }; const meta = STATUS_META[info.status] || STATUS_META.unknown; return (<tr key={key} className="border-b border-surface-800/30 hover:bg-surface-800/20"><td className="py-2 px-2"><div className="flex items-center gap-2"><span>{cfg.icon}</span><span className="font-semibold text-surface-200">{cfg.label}</span></div></td><td className="py-2 px-2 text-center"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.color}`}>{meta.label}</span></td><td className="py-2 px-2 text-center font-mono text-surface-300">{fmt(info.record_count)}</td><td className="py-2 px-2 text-center"><span className={`font-mono ${info.status === "ok" ? "text-accent-emerald" : info.status === "stale" ? "text-accent-amber" : info.status === "outdated" ? "text-accent-rose" : "text-surface-500"}`}>{info.age_minutes != null ? `${info.age_minutes.toFixed(0)} دقیقه` : "—"}</span></td><td className="py-2 px-2 text-center"><button onClick={() => handleSyncNow(key)} className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-all ${info.status === "outdated" ? "bg-accent-rose/15 text-accent-rose border-accent-rose/30 animate-pulse" : info.status === "stale" ? "bg-accent-amber/15 text-accent-amber border-accent-amber/30" : "bg-surface-800 text-surface-400 hover:text-primary-300 border-surface-700"}`}>Sync</button></td></tr>); })}</tbody></table></div></Card>
      {/* Quick Actions */}
      <Card title="اقدامات سریع"><div className="flex flex-wrap gap-2">
        <button onClick={() => handleRunJob("brsapi_all_symbols")} className="px-4 py-2 bg-primary-600/10 border border-primary-600/20 rounded-xl text-xs font-bold text-primary-400 hover:bg-primary-600/20 transition-all">🔄 Sync همه نمادها</button>
        <button onClick={() => handleRunJob("brsapi_gold_currency")} className="px-4 py-2 bg-accent-amber/10 border border-accent-amber/20 rounded-xl text-xs font-bold text-accent-amber hover:bg-accent-amber/20 transition-all">🥇 Sync طلا و ارز</button>
        <button onClick={() => handleRunJob("brsapi_commodities")} className="px-4 py-2 bg-accent-emerald/10 border border-accent-emerald/20 rounded-xl text-xs font-bold text-accent-emerald hover:bg-accent-emerald/20 transition-all">🌍 Sync کامودیتی‌ها</button>
        <button onClick={() => handleRunJob("brsapi_codal")} className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-400 hover:text-surface-200 transition-all">🏢 Sync کدال</button>
        <Link href="/brsapi" className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-400 hover:text-surface-200 transition-all">📡 مدیریت داده</Link>
        <Link href="/settings" className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-400 hover:text-surface-200 transition-all">⚙️ تنظیمات</Link>
      </div></Card>
      {/* ML Models */}
      {dash?.ml_models && dash.ml_models.length > 0 && (<Card title="مدل‌های یادگیری ماشین"><div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{dash.ml_models.map(model => { const lv = model.versions?.[model.versions.length - 1]; const acc = lv?.metrics?.accuracy != null ? (lv.metrics.accuracy * 100).toFixed(1) : null; return (<div key={model.id} className="p-3 rounded-xl bg-surface-800/30 border border-surface-700/30"><div className="flex items-center gap-2 mb-1"><span className="font-bold text-surface-200 text-sm">{model.name}</span><span className="text-[10px] font-mono text-surface-500">{model.id}</span></div><div className="flex items-center gap-2 text-[10px] text-surface-500"><span>📋 {model.task}</span><span>🔧 {model.framework}</span></div>{acc && <p className="text-xs mt-1">دقت: <span className={`font-mono font-bold ${parseFloat(acc) >= 85 ? "text-accent-emerald" : parseFloat(acc) >= 75 ? "text-accent-amber" : "text-accent-rose"}`}>{acc}%</span></p>}</div>); })}</div></Card>)}
      {/* Strategies */}
      {dash?.strategies && dash.strategies.length > 0 && (<Card title="استراتژی‌های بک‌تست"><div className="grid grid-cols-1 lg:grid-cols-3 gap-3">{dash.strategies.map((s, i) => (<div key={`${s.name}-${i}`} className="p-3 rounded-xl bg-surface-800/30 border border-surface-700/30"><div className="flex items-center gap-2 mb-1"><span className="font-bold text-surface-200 text-sm">{s.name}</span><span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-purple/15 text-accent-purple">{s.type}</span></div><p className="text-[10px] text-surface-500 font-mono">{s.class_name}</p></div>))}</div></Card>)}
      {/* System Info */}
      <Card title="اطلاعات سیستم"><div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
        <div><span className="text-surface-500">دیتابیس:</span><span className="text-surface-300 mr-1 font-mono">PostgreSQL</span></div>
        <div><span className="text-surface-500">API:</span><span className="text-surface-300 mr-1 font-mono">FastAPI + Python</span></div>
        <div><span className="text-surface-500">فرانت‌اند:</span><span className="text-surface-300 mr-1 font-mono">Next.js + React</span></div>
        <div><span className="text-surface-500">کاربران:</span><span className="text-surface-300 mr-1 font-mono">{m?.total_users ?? "—"} ({m?.active_users ?? 0} فعال)</span></div>
        <div><span className="text-surface-500">جدول‌ها:</span><span className="text-surface-300 mr-1 font-mono">{overviewEntries.length}</span></div>
        <div><span className="text-surface-500">وضعیت:</span><span className={`mr-1 font-semibold ${dash?.system_status === "healthy" ? "text-accent-emerald" : "text-accent-rose"}`}>{dash?.system_status === "healthy" ? "✅ سالم" : "—"}</span></div>
      </div></Card>
    </AppLayout>
  );

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: SYNC — from /sync + /sync-manager sync tab
  // ══════════════════════════════════════════════════════════════════════════════

  if (tab === "sync") return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <Tabs tab={tab} setTab={setTab} />
      <SyncChart />
      <div className="flex justify-end mb-3"><SyncAllButton /></div>
      <Card title="وضعیت بخش‌ها" actions={<div className="flex items-center gap-3 text-[10px]"><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> به‌روز</span><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> کمی قدیمی</span><span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-rose" /> قدیمی</span></div>}>
        {statusLoading ? <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-14 w-full rounded-lg" />)}</div> : (
          <div className="overflow-x-auto"><table className="w-full text-right text-xs"><thead><tr className="text-surface-500 border-b border-surface-700">
            <th className="pb-3 px-3">بخش</th><th className="pb-3 px-3 text-center">وضعیت</th><th className="pb-3 px-3 text-center">رکوردها</th><th className="pb-3 px-3 text-center">آخرین بروزرسانی</th><th className="pb-3 px-3 text-center">سن</th><th className="pb-3 px-3 text-center">مهلت</th><th className="pb-3 px-3 text-center">عملیات</th>
          </tr></thead><tbody>{overviewEntries.map(([key, info]) => { const cfg = TABLE_CONFIG[key] || { label: key, icon: "📦" }; const meta = STATUS_META[info.status] || STATUS_META.unknown; return (
            <tr key={key} className="border-b border-surface-800/30 hover:bg-surface-800/20">
              <td className="py-3 px-3"><div className="flex items-center gap-2"><span className="text-base">{cfg.icon}</span><span className="font-semibold text-surface-200">{cfg.label}</span></div></td>
              <td className="py-3 px-3 text-center"><span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${meta.bg} ${meta.color}`}>{meta.label}</span></td>
              <td className="py-3 px-3 text-center font-mono text-surface-300">{fmt(info.record_count)}</td>
              <td className="py-3 px-3 text-center text-surface-400">{info.last_fetched ? fmtTime(info.last_fetched) : "—"}</td>
              <td className="py-3 px-3 text-center"><span className={`font-mono ${info.status === "ok" ? "text-accent-emerald" : info.status === "stale" ? "text-accent-amber" : info.status === "outdated" ? "text-accent-rose" : "text-surface-500"}`}>{info.age_minutes != null ? `${info.age_minutes.toFixed(0)} دقیقه` : "—"}</span></td>
              <td className="py-3 px-3 text-center text-surface-500 font-mono">{info.max_age_minutes} دقیقه</td>
              <td className="py-3 px-3 text-center"><button onClick={() => handleSyncNow(key)} className={`px-2.5 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${info.status === "outdated" ? "bg-accent-rose/15 text-accent-rose border-accent-rose/30 animate-pulse" : info.status === "stale" ? "bg-accent-amber/15 text-accent-amber border-accent-amber/30" : "bg-surface-800 text-surface-400 hover:text-primary-300 border-surface-700"}`}>Sync</button></td>
            </tr>); })}</tbody></table></div>
        )}
      </Card>
      <SyncEvents />
    </AppLayout>
  );

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: FRESHNESS — from /sync-settings
  // ══════════════════════════════════════════════════════════════════════════════

  if (tab === "freshness") return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <Tabs tab={tab} setTab={setTab} />
      <FreshnessTab settings={freshnessSettings} setSettings={setFreshnessSettings} />
    </AppLayout>
  );

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: SCHEDULER — from /scheduler
  // ══════════════════════════════════════════════════════════════════════════════

  if (tab === "scheduler") return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <Tabs tab={tab} setTab={setTab} />
      <SchedulerTab jobs={schedJobs} enabled={schedulerData?.enabled ?? 0} disabled={schedulerData?.disabled ?? 0} />
    </AppLayout>
  );

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: IMPORT — from /data-import
  // ══════════════════════════════════════════════════════════════════════════════

  if (tab === "import") return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <Tabs tab={tab} setTab={setTab} />
      <ImportTab />
    </AppLayout>
  );

  // ══════════════════════════════════════════════════════════════════════════════
  // TAB: TABLES — from /tables
  // ══════════════════════════════════════════════════════════════════════════════

  return (
    <AppLayout title="🛡️ پنل مدیریت" subtitle="مدیریت یکپارچه سیستم، داده‌ها و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <Tabs tab={tab} setTab={setTab} />
      <TablesTab />
    </AppLayout>
  );
}

// ════════════════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ════════════════════════════════════════════════════════════════════════════════

function Tabs({ tab, setTab }: { tab: TabKey; setTab: (t: TabKey) => void }) {
  return (<div className="flex gap-1 mb-5 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
    {TABS.map(t => (<button key={t.key} onClick={() => setTab(t.key)} className={`px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${tab === t.key ? "bg-primary-600/30 text-primary-300 shadow-sm" : "text-surface-400 hover:text-surface-200"}`}>{t.icon} {t.label}</button>))}
  </div>);
}

function SyncAllButton() {
  const qc = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "warning" } | null>(null);
  const handle = useCallback(async () => {
    setSyncing(true); let ok = 0, fail = 0; const keys = Object.keys(SECTION_ID_MAP);
    for (let i = 0; i < keys.length; i++) { const id = SECTION_ID_MAP[keys[i]]; try { const r = await apiPost<{ success: boolean }>(`/brsapi/manage/sync/${id}`); if (r?.success) ok++; else fail++; } catch { fail++; } }
    qc.invalidateQueries({ queryKey: ["admin-sync-status"] }); setSyncing(false);
  }, [qc]);
  return (<><button onClick={handle} disabled={syncing} className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold ${syncing ? "bg-primary-600/20 text-primary-300 animate-pulse" : "bg-primary-600/15 text-primary-400 border border-primary-600/30 hover:bg-primary-600/25"}`}><span className={`material-icons text-sm ${syncing ? "animate-spin" : ""}`}>sync</span>{syncing ? "در حال sync..." : "🔄 Sync All — همه بخش‌ها"}</button></>);
}

function SyncChart() {
  const [tr, setTr] = useState("48h");
  const hrs = tr === "24h" ? 24 : tr === "48h" ? 48 : tr === "7d" ? 168 : 720;
  const { data: hist, isLoading } = useQuery({ queryKey: ["admin-sync-hist", tr], queryFn: async (): Promise<SyncLogEntry[]> => { const r = await apiGet<{ success: boolean; data: SyncLogEntry[] }>(`/brsapi/sync-history?hours=${hrs}&limit=300`); return r?.data ?? []; }, refetchInterval: 120_000 });
  const chartData = useMemo(() => { if (!hist) return []; const b: Record<string, { time: string; success: number; error: number }> = {}; for (const e of hist) { if (!e.time) continue; const k = new Date(e.time).toISOString().slice(0, 13) + ":00"; if (!b[k]) b[k] = { time: k, success: 0, error: 0 }; if (e.status === "success") b[k].success++; else b[k].error++; } return Object.values(b).sort((a, c) => a.time.localeCompare(c.time)); }, [hist]);
  const tl = { "24h": "۲۴h", "48h": "۴۸h", "7d": "۷d", "30d": "۳۰d" }[tr];
  return (<Card title={`تاریخچه Freshness (${tl})`} actions={<div className="flex gap-1">{["24h","48h","7d","30d"].map(r => (<button key={r} onClick={() => setTr(r)} className={`text-[10px] px-2 py-1 rounded-lg font-bold ${tr === r ? "bg-primary-600/30 text-primary-300" : "text-surface-500 hover:text-surface-300"}`}>{tl}</button>))}</div>}>
    {isLoading ? <Skeleton className="h-[200px] w-full rounded-xl" /> : chartData.length === 0 ? <div className="flex items-center justify-center h-[180px] text-surface-500 text-sm">داده‌ای موجود نیست</div> : (
      <AreaChartCard title="" data={chartData.map(d => ({ date: d.time.slice(11, 16), time: d.time.slice(11, 16), value: d.success, error: d.error }))} dataKey="success" height={240} strokeColor="#10b981" gradientId="freshGrad" showAverage showMinMax crosshair animate primaryLabel="موفق" yAxisLabel="تعداد" additionalSeries={[{ dataKey: "error", strokeColor: "#FF5252", gradientId: "errGrad", label: "خطا", asBar: true, barFill: "#ef4444" }]} />
    )}
  </Card>);
}

function SyncEvents() {
  const { data: hist, isLoading } = useQuery({ queryKey: ["admin-sync-events"], queryFn: async (): Promise<SyncLogEntry[]> => { const r = await apiGet<{ success: boolean; data: SyncLogEntry[] }>(`/brsapi/sync-history?hours=48&limit=20`); return r?.data ?? []; }, refetchInterval: 120_000 });
  return (<Card title="آخرین رویدادهای Sync" actions={<span className="text-[10px] text-surface-600">{hist?.length ?? 0} رویداد</span>}>
    {isLoading ? <Skeleton className="h-40 w-full" /> : hist && hist.length > 0 ? (<div className="space-y-1 max-h-[300px] overflow-y-auto">{hist.map((ev, i) => (<div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-surface-800/20"><div className="flex items-center gap-2.5 min-w-0"><span className={`w-2 h-2 rounded-full shrink-0 ${ev.status === "success" ? "bg-accent-emerald" : "bg-accent-rose"}`} /><span className="text-[10px] text-surface-400 font-mono truncate max-w-[180px]">{ev.endpoint}</span></div><div className="flex items-center gap-2 shrink-0 text-[9px]"><span className="text-surface-600">{ev.items_count} آیتم</span><span className="text-surface-600">{fmtDur(ev.duration_ms)}</span><span className="text-surface-500">{fmtRel(ev.time)}</span></div></div>))}</div>) : <p className="text-surface-500 text-sm text-center py-6">رویدادی ثبت نشده</p>}
  </Card>);
}

function FreshnessTab({ settings, setSettings }: { settings: SyncSettingsMap; setSettings: (s: SyncSettingsMap) => void }) {
  const [saved, setSaved] = useState(false); const [resetConfirm, setResetConfirm] = useState(false);
  const handleSave = useCallback(() => { saveSyncSettings(settings); setSaved(true); setTimeout(() => setSaved(false), 2500); }, [settings]);
  const handleReset = useCallback(() => { resetSyncSettings(); setSettings({ ...DEFAULT_SYNC_SETTINGS }); setResetConfirm(false); setSaved(true); setTimeout(() => setSaved(false), 2500); }, [setSettings]);
  const hasChanges = ALL_SECTION_KEYS.some(k => settings[k]?.maxAgeMinutes !== DEFAULT_SYNC_SETTINGS[k]?.maxAgeMinutes);
  return (<div className="max-w-2xl mx-auto space-y-4">
    <div className="p-3 rounded-xl bg-primary-600/10 border border-primary-500/20 text-[11px] text-surface-400 leading-relaxed"><span className="font-bold text-primary-300">💡 راهنما:</span> آستانه زمانی هر بخش را تنظیم کنید. تغییرات فقط در مرورگر شما اعمال می‌شوند (localStorage).</div>
    <Card title="تنظیمات Freshness">
      <div className="flex items-center gap-3 px-3 pb-2 mb-1 border-b border-surface-700/30 text-[10px] text-surface-500"><span className="w-40">بخش</span><span className="flex-1 text-center">آستانه</span><span className="w-20 text-center">مقدار</span></div>
      <div className="space-y-0.5">{ALL_SECTION_KEYS.map(key => { const s = settings[key] || DEFAULT_SYNC_SETTINGS[key]; const idx = PRESET_VALUES.indexOf(nearestPreset(s.maxAgeMinutes)); return (
        <div key={key} className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-surface-800/40">
          <div className="flex items-center gap-2 w-40 shrink-0"><span className="text-lg">{s.icon}</span><span className="text-xs font-medium text-surface-300">{s.label}</span></div>
          <input type="range" min={0} max={PRESET_VALUES.length - 1} value={idx >= 0 ? idx : 3} onChange={e => { const i = parseInt(e.target.value); setSettings({ ...settings, [key]: { ...settings[key], maxAgeMinutes: PRESET_VALUES[i] } }); }} className="flex-1 h-1.5 rounded-full appearance-none cursor-pointer bg-surface-700 accent-primary-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary-500" />
          <span className="w-20 text-center text-[11px] font-mono text-surface-400 shrink-0">{VALUE_LABELS[nearestPreset(s.maxAgeMinutes)] || `${s.maxAgeMinutes} دقیقه`}</span>
        </div>); })}</div>
    </Card>
    <div className="flex items-center gap-3">
      <button onClick={handleSave} className="px-5 py-2.5 rounded-xl text-xs font-bold bg-primary-600 text-white hover:bg-primary-500">{saved ? "✓ ذخیره شد" : "💾 ذخیره"}</button>
      {hasChanges && <span className="text-[10px] text-accent-amber">⚠️ تغییرات ذخیره نشده</span>}
      <div className="flex-1" />
      {resetConfirm ? (<div className="flex items-center gap-2"><button onClick={handleReset} className="px-3 py-2 rounded-lg text-[10px] font-bold bg-accent-rose/15 text-accent-rose">بله، ریست</button><button onClick={() => setResetConfirm(false)} className="px-3 py-2 rounded-lg text-[10px] bg-surface-800 text-surface-400">انصراف</button></div>) : <button onClick={() => setResetConfirm(true)} className="text-[10px] text-surface-500 hover:text-accent-rose">🔄 بازگشت به پیش‌فرض</button>}
    </div>
  </div>);
}

function SchedulerTab({ jobs, enabled, disabled }: { jobs: SchedulerJob[]; enabled: number; disabled: number }) {
  const qc = useQueryClient();
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [search, setSearch] = useState(""); const [cat, setCat] = useState("all");
  const filtered = useMemo(() => jobs.filter(j => { if (cat !== "all" && j.category !== cat) return false; if (search.trim()) { const q = search.toLowerCase(); return j.name.toLowerCase().includes(q) || j.description.toLowerCase().includes(q); } return true; }).sort((a, b) => a.enabled === b.enabled ? a.name.localeCompare(b.name) : a.enabled ? -1 : 1), [jobs, search, cat]);
  const categories = useMemo(() => Array.from(new Set(jobs.map(j => j.category))).sort(), [jobs]);
  const handleRun = useCallback(async (name: string) => { setToast({ message: `🔄 ${name}...`, type: "success" }); try { const r = await apiPost<{ success: boolean }>(`/jobs/scheduler/${name}/run`); if (r?.success) { setToast({ message: `✅ ${name}`, type: "success" }); qc.invalidateQueries({ queryKey: ["admin-scheduler"] }); } } catch {} }, [qc]);
  const handleToggle = useCallback(async (name: string) => { try { const r = await apiPost<{ success: boolean }>(`/jobs/scheduler/${name}/toggle`); if (r?.success) { setToast({ message: `✅ ${name}`, type: "success" }); qc.invalidateQueries({ queryKey: ["admin-scheduler"] }); } } catch {} }, [qc]);
  return (<div className="space-y-4">
    {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-2 bg-surface-800/50 rounded-xl px-3 py-2 border border-surface-700/50 flex-1 min-w-[200px]"><span className="text-surface-500">🔍</span><input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="جستجو..." className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0" /></div>
      <select value={cat} onChange={e => setCat(e.target.value)} className="bg-surface-800/50 text-sm text-surface-300 border border-surface-700/50 rounded-xl px-3 py-2 outline-none"><option value="all">📂 همه</option>{categories.map(c => { const ci = CATEGORY_CONFIG[c] || { label: c, icon: "📦" }; return <option key={c} value={c}>{ci.icon} {ci.label}</option>; })}</select>
    </div>
    <Card title="Jobهای زمان‌بندی" actions={<span className="text-[10px] text-surface-600">{enabled} فعال / {disabled} غیرفعال</span>}>
      <div className="overflow-x-auto"><table className="w-full text-right text-xs"><thead><tr className="text-surface-500 border-b border-surface-700">
        <th className="pb-3 px-3">وضعیت</th><th className="pb-3 px-3">نام</th><th className="pb-3 px-3">دسته</th><th className="pb-3 px-3">برنامه</th><th className="pb-3 px-3 text-center">اجرای بعدی</th><th className="pb-3 px-3 text-center">عملیات</th>
      </tr></thead><tbody>{filtered.map(job => { const ci = CATEGORY_CONFIG[job.category] || { label: job.category, icon: "📦" }; return (
        <tr key={job.name} className={`border-b border-surface-800/30 hover:bg-surface-800/20 ${job.enabled ? "" : "opacity-60"}`}>
          <td className="py-3 px-3"><span className={`w-2.5 h-2.5 rounded-full inline-block ${job.enabled ? "bg-accent-emerald" : "bg-surface-600"}`} /></td>
          <td className="py-3 px-3 max-w-[220px]"><div className="flex flex-col gap-0.5"><span className="font-semibold text-surface-200 font-mono text-[11px]">{job.name}</span><span className="text-[9px] text-surface-500 line-clamp-1">{job.description}</span></div></td>
          <td className="py-3 px-3"><span className="px-2 py-0.5 rounded-lg bg-surface-800 text-surface-400 text-[10px]">{ci.icon} {ci.label}</span></td>
          <td className="py-3 px-3"><span className="font-mono text-surface-300 text-[10px]">{fmtCron(job.cron)}</span></td>
          <td className="py-3 px-3 text-center">{job.enabled && job.next_run_time ? <span className="text-[10px] text-surface-400">{fmtTime(job.next_run_time)}</span> : <span className="text-surface-600">—</span>}</td>
          <td className="py-3 px-3"><div className="flex items-center justify-center gap-1.5"><button onClick={() => handleRun(job.name)} className="px-2 py-1.5 rounded-lg text-[10px] bg-primary-600/10 text-primary-400 border border-primary-600/20 hover:bg-primary-600/20">▶</button><button onClick={() => handleToggle(job.name)} className={`px-2 py-1.5 rounded-lg text-[10px] border ${job.enabled ? "bg-accent-rose/10 text-accent-rose border-accent-rose/20" : "bg-accent-emerald/10 text-accent-emerald border-accent-emerald/20"}`}>{job.enabled ? "⏸" : "▶"}</button></div></td>
        </tr>); })}</tbody></table></div>
    </Card>
  </div>);
}

function ImportTab() {
  const [activeTab, setActiveTab] = useState<string>("instruments");
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const { data: templates } = useQuery({ queryKey: ["import-templates"], queryFn: async () => { const r = await apiGet<{ success: boolean; data: ImportTemplates }>("/data-import/templates"); return r.data; }, staleTime: 300_000 });
  const { data: history } = useQuery({ queryKey: ["import-history"], queryFn: async () => { const r = await apiGet<{ success: boolean; data: { items: ImportJob[] } }>("/data-import/history"); return r.data?.items || []; }, refetchInterval: 30_000 });
  const tmpl = templates?.[activeTab as keyof ImportTemplates];
  const doUpload = useCallback(async (f: File[]) => {
    const ep = activeTab === "instruments" ? "/instruments/import" : activeTab === "quotes" ? "/quotes/import-bulk" : "/codal/import-bulk";
    const form = new FormData(); if (activeTab === "instruments") form.append("file", f[0]); else f.forEach(x => form.append("files", x));
    try { const r = await fetch(`${API_BASE}${ep}`, { method: "POST", body: form }); const d = await r.json(); setResult({ total_files: d?.data?.total_files ?? 0, total_rows: d?.data?.total_rows ?? 0, imported: d?.data?.imported ?? 0, updated: d?.data?.updated ?? 0, errors: d?.data?.errors ?? d?.data?.parse_errors ?? [], per_file: d?.data?.per_file }); setFiles([]); } catch { setResult({ errors: ["خطا در آپلود"] }); setFiles([]); }
  }, [activeTab]);
  return (<div className="space-y-4">
    <div className="flex gap-2 overflow-x-auto">{IMPORT_TABS.map(t => (<button key={t.key} onClick={() => setActiveTab(t.key)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${activeTab === t.key ? "bg-primary-600/20 text-primary-300 border border-primary-600/30" : "bg-surface-800/50 text-surface-400 border border-surface-700 hover:text-surface-200"}`}>{t.label}</button>))}</div>
    <div onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={e => { e.preventDefault(); setDragOver(false); setFiles(Array.from(e.dataTransfer.files)); }} onClick={() => ref.current?.click()} className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${dragOver ? "border-primary-400 bg-primary-600/10" : "border-surface-700 hover:border-surface-500 bg-surface-800/30"}`}>
      <input ref={ref} type="file" multiple accept={tmpl?.accept} onChange={e => { if (e.target.files) setFiles(Array.from(e.target.files)); }} className="hidden" />
      <div className="text-4xl mb-3">{dragOver ? "📥" : "📂"}</div>
      <p className="text-sm text-surface-300">{files.length > 0 ? `${files.length} فایل انتخاب شده` : "فایل را بکشید و رها کنید"}</p>
      <p className="text-xs text-surface-500 mt-1">{tmpl?.accept} • حداکثر {tmpl?.max_size_mb}MB</p>
      {tmpl?.note && <p className="text-xs text-accent-amber mt-2">{tmpl.note}</p>}
      {files.length > 0 && <div className="mt-3 space-y-1">{files.map((f, i) => <p key={i} className="text-xs text-surface-400 font-mono">{f.name} ({(f.size / 1024).toFixed(0)}KB)</p>)}</div>}
    </div>
    <div className="flex gap-3">
      <button onClick={() => files.length > 0 && doUpload(files)} disabled={files.length === 0} className="flex-1 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl text-sm font-semibold">📤 آپلود و Import</button>
      {tmpl?.sample_endpoint && <a href={`${API_BASE}${tmpl.sample_endpoint}`} className="px-4 py-2.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs">📄 نمونه CSV</a>}
    </div>
    {result && (<div className={`glass-card p-4 ${result.errors && result.errors.length > 0 ? "border-accent-rose/30" : "border-accent-emerald/30"}`}>
      <h4 className="text-sm font-bold text-surface-200 mb-3">نتایج Import</h4>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        {result.total_files !== undefined && <div><span className="text-xs text-surface-500">فایل‌ها</span><p className="text-lg font-bold text-surface-200">{fmt(result.total_files)}</p></div>}
        {result.imported !== undefined && <div><span className="text-xs text-surface-500">جدید</span><p className="text-lg font-bold text-accent-emerald">{fmt(result.imported)}</p></div>}
        {result.updated !== undefined && <div><span className="text-xs text-surface-500">بروزرسانی</span><p className="text-lg font-bold text-accent-amber">{fmt(result.updated)}</p></div>}
        {result.total_rows !== undefined && <div><span className="text-xs text-surface-500">ردیف‌ها</span><p className="text-lg font-bold text-surface-200">{fmt(result.total_rows)}</p></div>}
      </div>
      {result.errors && result.errors.length > 0 && <div><p className="text-xs text-accent-rose mb-1">خطاها ({result.errors.length}):</p><div className="max-h-24 overflow-y-auto">{result.errors.slice(0, 10).map((e, i) => <p key={i} className="text-[10px] text-accent-rose/80 font-mono">{e}</p>)}</div></div>}
      {result.per_file && Object.keys(result.per_file).length > 0 && <div className="mt-2 pt-2 border-t border-surface-700"><p className="text-[10px] text-surface-500 mb-1">جزئیات:</p>{Object.entries(result.per_file).map(([name, info]) => <p key={name} className="text-[10px] text-surface-400 font-mono">{name}: {info.imported} جدید, {info.updated} بروز</p>)}</div>}
    </div>)}
    {tmpl && tmpl.columns.length > 0 && (<div className="glass-card p-4"><h4 className="text-xs font-bold text-surface-400 mb-2">📋 ستون‌های قابل قبول</h4><div className="overflow-x-auto"><table className="w-full text-[10px]"><thead><tr className="text-surface-600 border-b border-surface-700"><th className="text-right py-1.5 px-2">ستون</th><th className="text-right py-1.5 px-2">نوع</th><th className="text-right py-1.5 px-2">اجباری</th><th className="text-right py-1.5 px-2">توضیح</th></tr></thead><tbody>{tmpl.columns.map(col => (<tr key={col.column} className="border-b border-surface-800/50"><td className="py-1.5 px-2 font-mono text-surface-300">{col.column}</td><td className="py-1.5 px-2 text-surface-500">{col.type}</td><td className="py-1.5 px-2"><span className={`px-1.5 py-0.5 rounded ${col.required ? "bg-accent-rose/15 text-accent-rose" : "bg-surface-800 text-surface-500"}`}>{col.required ? "بله" : "خیر"}</span></td><td className="py-1.5 px-2 text-surface-500">{col.desc}</td></tr>))}</tbody></table></div></div>)}
    {history && history.length > 0 && (<Card title="تاریخچه Import"><div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-surface-500 border-b border-surface-700"><th className="text-right py-2 px-2">نوع</th><th className="text-right py-2 px-2">وضعیت</th><th className="text-right py-2 px-2">مدت</th><th className="text-right py-2 px-2">زمان</th><th className="text-right py-2 px-2">خطا</th></tr></thead><tbody>{history.slice(0, 15).map((job: ImportJob) => (<tr key={job.id} className="border-b border-surface-800/50 hover:bg-surface-800/30"><td className="py-2 px-2 font-mono text-surface-300">{job.job_type}</td><td className="py-2 px-2"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadge(job.status)}`}>{statusLbl(job.status)}</span></td><td className="py-2 px-2 text-surface-400">{job.duration_seconds > 0 ? fmtDurSec(job.duration_seconds) : "—"}</td><td className="py-2 px-2 text-surface-500">{fmtTime(job.completed_at || job.started_at)}</td><td className="py-2 px-2 text-accent-rose max-w-[160px] truncate">{job.error_message || "—"}</td></tr>))}</tbody></table></div></Card>)}
  </div>);
}

function TablesTab() {
  const [sel, setSel] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [globalQ, setGlobalQ] = useState("");
  const [activeGlobalQ, setActiveGlobalQ] = useState("");
  const [page, setPage] = useState(1);
  const { data: tblResp, isLoading } = useQuery({ queryKey: ["tables-list"], queryFn: async () => apiGet<unknown>("/tables") });
  const tables: TableInfo[] = (tblResp && typeof tblResp === "object" && "data" in tblResp) ? ((tblResp as { data?: { tables?: TableInfo[] } }).data?.tables ?? []) : [];
  const { data: dResp, isLoading: dLoading } = useQuery({ queryKey: ["table-data", sel], queryFn: async () => apiGet<unknown>(`/tables/${sel}?page=1&page_size=50`), enabled: !!sel });
  const tblData: TableData | null = (dResp && typeof dResp === "object" && "data" in dResp) ? ((dResp as { data?: TableData }).data ?? null) : null;

  return (<div className="space-y-4">
    {/* Global Search */}
    <div className="glass-card p-4">
      <form onSubmit={e => { e.preventDefault(); if (globalQ.trim()) setActiveGlobalQ(globalQ.trim()); }} className="flex items-center gap-3">
        <span className="text-surface-500 text-lg">🔍</span>
        <input type="text" value={globalQ} onChange={e => setGlobalQ(e.target.value)} placeholder="نام نماد را تایپ کنید (مثال: فولاد، شپنا، وبملت)" className="flex-1 px-4 py-2.5 bg-surface-800 border border-surface-700 rounded-xl text-sm text-surface-200 focus:outline-none focus:border-primary-500" />
        <button type="submit" className="px-4 py-2.5 bg-primary-600 text-white rounded-xl text-sm font-bold">جستجو</button>
        {activeGlobalQ && <button type="button" onClick={() => { setActiveGlobalQ(""); setGlobalQ(""); }} className="px-4 py-2.5 bg-surface-800 text-surface-300 rounded-xl text-sm">پاک کردن</button>}
      </form>
      {activeGlobalQ && <div className="mt-2 text-xs text-surface-400">جستجوی: <span className="font-mono text-primary-300">{activeGlobalQ}</span></div>}
    </div>
    {/* Content */}
    {activeGlobalQ ? <GlobalSearchResults query={activeGlobalQ} /> : (
      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-64 shrink-0"><div className="glass-card p-4">
          <h3 className="font-bold text-sm text-surface-200 mb-3">جداول ({tables.length})</h3>
          <input type="text" value={filter} onChange={e => setFilter(e.target.value)} placeholder="فیلتر..." className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-surface-200 focus:outline-none focus:border-primary-500 mb-3" />
          <div className="space-y-1 max-h-[calc(100vh-320px)] overflow-y-auto">
            {(filter ? tables.filter(t => t.name.includes(filter)) : tables).map(t => (<button key={`${t.name}-${t.row_count}`} onClick={() => { setSel(t.name); setFilter(""); }} className={`w-full text-right px-3 py-2 rounded-lg text-xs font-mono transition-colors flex items-center justify-between ${sel === t.name ? "bg-primary-600/20 text-primary-300 border border-primary-600/30" : "text-surface-300 hover:bg-surface-800"}`}><span>{t.name}</span><span className="text-[10px] text-surface-500">{t.row_count.toLocaleString()}</span></button>))}
          </div>
        </div></div>
        {/* Main */}
        <div className="flex-1 min-w-0"><div className="glass-card p-4">
          {dLoading && !tblData ? <div className="space-y-3">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-11 w-full" />)}</div> : tblData ? (
            <div><div className="flex items-center justify-between mb-4"><h3 className="font-bold text-surface-200">{tblData.table}</h3><span className="text-xs text-surface-500 font-mono">{tblData.total.toLocaleString()} rows | Page {tblData.page}/{tblData.total_pages}</span></div>
              <div className="overflow-x-auto rounded-xl border border-surface-700/50"><table className="w-full text-right text-xs"><thead><tr className="bg-surface-800/80 border-b border-surface-700"><th className="py-2.5 px-3 text-surface-400 w-10">#</th>{tblData.columns.map((col, ci) => (<th key={`${col.name}-${ci}`} className="py-2.5 px-3 text-surface-400"><div>{col.name}</div><div className="text-[9px] text-surface-600 font-mono">{col.type}</div></th>))}</tr></thead>
                <tbody>{tblData.rows.map((row, i) => (<tr key={i} className="border-b border-surface-800/30 hover:bg-surface-800/20"><td className="py-2 px-3 text-surface-600 font-mono">{(tblData.page - 1) * tblData.page_size + i + 1}</td>{tblData.columns.map((col, ci) => { const val = row[col.name]; const sv = val == null ? "—" : typeof val === "object" ? JSON.stringify(val) : String(val); return <td key={`${col.name}-${ci}`} className="py-2 px-3 font-mono text-surface-200 max-w-[200px] truncate" title={sv.length > 50 ? sv : undefined}>{sv.length > 50 ? sv.slice(0, 50) + "..." : sv}</td>; })}</tr>))}</tbody></table></div>
              {tblData.total_pages > 1 && (<div className="flex justify-center gap-1 mt-4"><button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={tblData.page <= 1} className="px-3 py-1.5 rounded-lg bg-surface-800 text-surface-300 text-xs disabled:opacity-40">قبلی</button>{Array.from({ length: Math.min(5, tblData.total_pages) }, (_, i) => { const p = Math.max(1, Math.min(tblData.page - 2, tblData.total_pages - 4)) + i; if (p > tblData.total_pages) return null; return <button key={p} className={`px-3 py-1.5 rounded-lg text-xs ${p === tblData.page ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-300"}`}>{p}</button>; })}<button onClick={() => setPage(p => Math.min(tblData.total_pages, p + 1))} disabled={tblData.page >= tblData.total_pages} className="px-3 py-1.5 rounded-lg bg-surface-800 text-surface-300 text-xs disabled:opacity-40">بعدی</button></div>)}
            </div>
          ) : <div className="text-center py-20 text-surface-500"><div className="text-4xl mb-3">🗃️</div><p className="text-sm">یک جدول را از لیست انتخاب کنید</p></div>}
        </div></div>
      </div>
    )}
  </div>);
}

function GlobalSearchResults({ query }: { query: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const { data: resp, isLoading } = useQuery({ queryKey: ["global-search", query], queryFn: async () => {
    const ps = SEARCHABLE_TABLES.map(async tn => { try { const r = await apiGet<{ data?: { rows?: Record<string, unknown>[]; total?: number; columns?: ColumnInfo[] } }>(`/tables/${tn}?page=1&page_size=20&search=${encodeURIComponent(query)}`); const d = r?.data; if (d && Array.isArray(d.rows) && d.rows.length > 0) return { table: tn, total: d.total ?? 0, columns: d.columns ?? [], rows: d.rows } as SearchResult; } catch {} return null; });
    return (await Promise.all(ps)).filter(Boolean) as SearchResult[];
  }});
  const results = resp || [];
  if (isLoading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="glass-card p-4"><Skeleton className="h-7 w-36 mb-3" />{[1,2,3].map(j => <Skeleton key={j} className="h-9 w-full mb-1" />)}</div>)}</div>;
  if (results.length === 0) return <div className="text-center py-20 text-surface-500"><p className="text-lg mb-2">نتیجه‌ای برای «{query}» یافت نشد</p></div>;
  return (<div className="space-y-4">
    <div className="text-xs text-surface-400">{results.length} جدول — {results.reduce((s, r) => s + r.total, 0).toLocaleString()} ردیف یافت شد</div>
    {results.map(r => { const isOn = open === r.table; return (<div key={r.table} className="glass-card overflow-hidden">
      <button onClick={() => setOpen(isOn ? null : r.table)} className="w-full flex items-center justify-between p-4 text-surface-200">
        <div className="flex items-center gap-3"><span className="text-primary-400">📊</span><span className="font-mono font-bold">{r.table}</span><span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-600/15 text-primary-300">{r.total.toLocaleString()} ردیف</span></div>
        <span className="text-surface-500">{isOn ? "▲" : "▼"}</span>
      </button>
      {isOn && (<div className="border-t border-surface-700/50 p-3 overflow-x-auto"><table className="w-full text-right text-xs"><thead><tr className="border-b border-surface-700">{r.columns.map((col, ci) => <th key={`${col.name}-${ci}`} className="py-1.5 px-2 text-surface-400">{col.name}</th>)}</tr></thead><tbody>{r.rows.map((row, i) => (<tr key={i} className="border-b border-surface-800/30">{r.columns.map((col, ci) => { const val = row[col.name]; const sv = val == null ? "—" : typeof val === "object" ? JSON.stringify(val) : String(val); return <td key={`${col.name}-${ci}`} className="py-1.5 px-2 font-mono text-surface-200 max-w-[180px] truncate" title={sv}>{sv.length > 40 ? sv.slice(0, 40) + "..." : sv}</td>; })}</tr>))}</tbody></table>{r.total > 20 && <p className="text-center text-[10px] text-surface-500 mt-2">نمایش ۲۰ از {r.total.toLocaleString()} ردیف</p>}</div>)}
    </div>); })}
  </div>);
}
