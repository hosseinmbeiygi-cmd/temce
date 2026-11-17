"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  CloudDownload,
  Database,
  Download,
  RefreshCw,
  Search,
  Server,
  Table2,
  Zap,
  XCircle,
  Clock,
  GitBranch,
} from "lucide-react";

// ──────────────────────────────────────────────────────────────────────────────
//  Shared types
// ──────────────────────────────────────────────────────────────────────────────

type TabKey = "overview" | "sources" | "jobs" | "storage" | "diagnostics";

interface ApiSection {
  id: string;
  name: string;
  name_en: string;
  icon: string;
  category: string;
  has_date_range: boolean;
  record_count: number;
  last_sync: {
    status: string | null;
    items_count: number;
    duration_ms: number;
    completed_at: string | null;
    error_message: string | null;
  } | null;
}

interface OverviewData {
  timestamp: string;
  overall_status: "ok" | "warning" | "critical";
  jobs_24h: { total: number; success: number; failed: number; running: number };
  queue: { queue: number; dead_letter: number; dl_status: string; dl_threshold: number; enabled: boolean };
  storage: { total_tables: number; total_rows_estimate: number };
  recent_failures: { job_type: string; error: string | null; completed_at: string | null; duration_seconds: number }[];
  failure_rate_24h: number;
}

interface PipelineSource {
  id: string;
  name: string;
  name_en: string;
  source: string;
  job_name: string;
  schedule: string;
  tables: string[];
  category: string;
  status: string;
  pipeline_status: "ok" | "warning" | "failing" | "running" | "unknown";
  last_run: { status: string; completed_at: string | null; duration_seconds: number; error: string | null } | null;
}

interface SchedulerJob {
  name: string;
  enabled: boolean;
  description?: string;
  cron?: string;
  next_run_time?: string | null;
}

interface JobRun {
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

interface TableInfo {
  name: string;
  row_count: number;
  approximate: boolean;
}

interface FreshnessEntry {
  table: string;
  freshness_column: string;
  description: string;
  latest_ts: string | null;
  staleness_seconds: number | null;
  staleness_label: string;
}

interface QueueStats {
  queue_size: number;
  dead_letter_size: number;
  queue_enabled: boolean;
  stats_source: string;
  config: { queue: string; dead_letter: string; max_retries: number; poll_timeout_s: number };
}

interface DeadLetterSummary {
  total: number;
  job_name_distribution: Record<string, number>;
  error_categories: Record<string, number>;
  top_errors: { error: string; count: number }[];
  window: string;
}

// ──────────────────────────────────────────────────────────────────────────────
//  Helpers
// ──────────────────────────────────────────────────────────────────────────────

function fmtDurationMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtDurationSec(secs: number): string {
  if (secs < 1) return "<۱s";
  if (secs < 60) return `${Math.round(secs)}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
}

function fmtTime(iso: string | null, locale = "fa-IR"): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(locale, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function fmtRows(n: number, approx: boolean): string {
  const formatted = n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
    ? `${(n / 1_000).toFixed(1)}k`
    : n.toLocaleString("en-US");
  return approx ? `~${formatted}` : formatted;
}

const STATUS_COLOR: Record<string, string> = {
  ok: "text-accent-emerald",
  warning: "text-accent-amber",
  critical: "text-accent-rose",
  unknown: "text-surface-400",
  failing: "text-accent-rose",
  running: "text-accent-blue",
};

const STATUS_BG: Record<string, string> = {
  ok: "bg-accent-emerald/10 border-accent-emerald/20",
  warning: "bg-accent-amber/10 border-accent-amber/20",
  critical: "bg-accent-rose/10 border-accent-rose/20",
  unknown: "bg-surface-800/40 border-surface-700/30",
  failing: "bg-accent-rose/10 border-accent-rose/20",
  running: "bg-accent-blue/10 border-accent-blue/20",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-accent-emerald",
  warning: "bg-accent-amber",
  critical: "bg-accent-rose animate-pulse",
  unknown: "bg-surface-500",
  failing: "bg-accent-rose animate-pulse",
  running: "bg-accent-blue animate-pulse",
};

function StatusDot({ status }: { status: string }) {
  return <span className={`inline-block w-2 h-2 rounded-full ${STATUS_DOT[status] ?? "bg-surface-500"}`} />;
}

function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${STATUS_BG[status] ?? STATUS_BG.unknown}`}>
      <StatusDot status={status} />
      <span className={STATUS_COLOR[status] ?? STATUS_COLOR.unknown}>{label}</span>
    </span>
  );
}

const STATUS_LABELS: Record<string, string> = {
  ok: "سالم",
  warning: "هشدار",
  critical: "بحرانی",
  unknown: "نامشخص",
  failing: "خطا",
  running: "در حال اجرا",
  success: "موفق",
  failed: "خطا",
  pending: "در انتظار",
};

const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  tsetmc: { label: "بورس (TSETMC)", color: "border-r-accent-cyan" },
  ime: { label: "بورس کالا (IME)", color: "border-r-accent-amber" },
  commodity: { label: "کالاهای جهانی", color: "border-r-accent-emerald" },
  cryptocurrency: { label: "ارز دیجیتال", color: "border-r-accent-rose" },
  codal: { label: "کدال", color: "border-r-accent-purple" },
  funds: { label: "صندوق‌ها", color: "border-r-accent-indigo" },
  news: { label: "اخبار", color: "border-r-accent-sky" },
  gold_macro: { label: "ماکرو طلا", color: "border-r-accent-yellow" },
  macro: { label: "اقتصاد کلان", color: "border-r-accent-teal" },
  options: { label: "اختیار معامله", color: "border-r-accent-orange" },
  derived: { label: "داده مشتق‌شده", color: "border-r-surface-500" },
  ml: { label: "یادگیری ماشین", color: "border-r-accent-violet" },
  brsapi: { label: "BrsApi", color: "border-r-primary-400" },
};

// ──────────────────────────────────────────────────────────────────────────────
//  Tab nav
// ──────────────────────────────────────────────────────────────────────────────

const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "overview", label: "نمای کلی", icon: Activity },
  { key: "sources", label: "ورودی‌ها", icon: GitBranch },
  { key: "jobs", label: "کارها", icon: Zap },
  { key: "storage", label: "ذخیره‌سازی", icon: Database },
  { key: "diagnostics", label: "تشخیص", icon: AlertTriangle },
];

// ──────────────────────────────────────────────────────────────────────────────
//  Overview Tab
// ──────────────────────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["data-admin-overview"],
    queryFn: () => apiGet<{ success: boolean; data: OverviewData }>("/data-admin/overview").then((r) => r.data!),
    refetchInterval: 30_000,
  });

  if (isLoading) return <TabSkeleton />;
  if (error || !data) return <ErrorBox msg={String(error ?? "خطا در بارگذاری")} />;

  const d = data;
  const totalJobs = d.jobs_24h.total;
  const successRate = totalJobs > 0 ? Math.round((d.jobs_24h.success / totalJobs) * 100) : 100;

  return (
    <div className="space-y-6">
      {/* System status */}
      <div className={`p-4 rounded-xl border flex items-center gap-3 ${STATUS_BG[d.overall_status]}`}>
        {d.overall_status === "ok" ? (
          <CheckCircle className={`w-5 h-5 ${STATUS_COLOR[d.overall_status]}`} />
        ) : (
          <AlertTriangle className={`w-5 h-5 ${STATUS_COLOR[d.overall_status]}`} />
        )}
        <div>
          <p className={`font-semibold ${STATUS_COLOR[d.overall_status]}`}>
            وضعیت کلی: {STATUS_LABELS[d.overall_status] ?? d.overall_status}
          </p>
          <p className="text-xs text-surface-500 mt-0.5 font-mono" dir="ltr">
            {new Date(d.timestamp).toLocaleString("fa-IR")}
          </p>
        </div>
        <button onClick={() => refetch()} className="mr-auto p-1.5 rounded hover:bg-surface-800 transition-colors" title="بارگذاری مجدد">
          <RefreshCw className={`w-3.5 h-3.5 text-surface-400 ${isFetching ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard icon={<Zap className="w-4 h-4 text-accent-blue" />} label="کارها (۲۴ ساعت)" value={totalJobs.toString()} sub={`${successRate}٪ موفق`} subColor={successRate >= 90 ? "text-accent-emerald" : successRate >= 70 ? "text-accent-amber" : "text-accent-rose"} />
        <KpiCard icon={<XCircle className="w-4 h-4 text-accent-rose" />} label="خطاهای ۲۴h" value={d.jobs_24h.failed.toString()} sub={`${d.jobs_24h.running} در حال اجرا`} subColor="text-surface-400" />
        <KpiCard icon={<Server className="w-4 h-4 text-accent-amber" />} label="صف مرده (DLQ)" value={d.queue.dead_letter.toString()} sub={d.queue.dl_status === "ok" ? "سالم" : "نیاز به بررسی"} subColor={d.queue.dl_status === "ok" ? "text-accent-emerald" : "text-accent-rose"} />
        <KpiCard icon={<Database className="w-4 h-4 text-accent-emerald" />} label="جداول DB" value={d.storage.total_tables.toString()} sub={fmtRows(d.storage.total_rows_estimate, true) + " رکورد"} subColor="text-surface-400" />
      </div>

      {/* Queue health */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
          <Server className="w-4 h-4 text-accent-amber" />
          صف پردازش
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface-800/50 rounded-lg p-3">
            <div className="text-[10px] text-surface-500 mb-1">صف اصلی</div>
            <div className="text-xl font-bold font-mono text-surface-200">{d.queue.queue}</div>
            <div className="text-[10px] text-surface-500 mt-1">{d.queue.enabled ? "فعال" : "غیرفعال"}</div>
          </div>
          <div className={`rounded-lg p-3 ${d.queue.dead_letter > 0 ? "bg-accent-rose/10" : "bg-surface-800/50"}`}>
            <div className="text-[10px] text-surface-500 mb-1">صف مرده (DLQ)</div>
            <div className={`text-xl font-bold font-mono ${d.queue.dead_letter > 0 ? "text-accent-rose" : "text-surface-200"}`}>{d.queue.dead_letter}</div>
            <div className="text-[10px] text-surface-500 mt-1">آستانه هشدار: {d.queue.dl_threshold}</div>
          </div>
        </div>
      </div>

      {/* Recent failures */}
      {d.recent_failures.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
            <XCircle className="w-4 h-4 text-accent-rose" />
            آخرین خطاها (۲۴ ساعت)
          </h3>
          <div className="space-y-2">
            {d.recent_failures.map((f, i) => (
              <div key={i} className="bg-surface-800/60 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-accent-rose">{f.job_type}</span>
                  <span className="text-[10px] text-surface-500" dir="ltr">{fmtTime(f.completed_at)}</span>
                </div>
                {f.error && (
                  <p className="text-[11px] text-surface-400 font-mono break-all">{f.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {d.recent_failures.length === 0 && (
        <div className="glass-card p-4 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-accent-emerald flex-shrink-0" />
          <p className="text-sm text-surface-400">هیچ خطایی در ۲۴ ساعت گذشته ثبت نشده است</p>
        </div>
      )}
    </div>
  );
}

function KpiCard({ icon, label, value, sub, subColor }: { icon: React.ReactNode; label: string; value: string; sub: string; subColor: string }) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-[11px] text-surface-500">{label}</span>
      </div>
      <div className="text-2xl font-bold font-mono text-surface-200">{value}</div>
      <div className={`text-[11px] mt-1 ${subColor}`}>{sub}</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Sources Tab
// ──────────────────────────────────────────────────────────────────────────────

function SourcesTab() {
  const queryClient = useQueryClient();
  const [syncingSection, setSyncingSection] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [view, setView] = useState<"pipeline" | "brsapi">("pipeline");

  const { data: sections, isLoading: sectionsLoading } = useQuery({
    queryKey: ["brsapi-sections"],
    queryFn: () => apiGet<{ success: boolean; data: ApiSection[] }>("/brsapi/manage/sections").then((r) => r.data ?? []),
    refetchInterval: 30_000,
  });

  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["data-admin-sources"],
    queryFn: () => apiGet<{ success: boolean; data: { sources: PipelineSource[]; categories: string[] } }>("/data-admin/sources").then((r) => r.data!),
    refetchInterval: 60_000,
  });

  const syncMutation = useMutation({
    mutationFn: async ({ sectionId, dateStart, dateEnd, symbol }: { sectionId: string; dateStart: string; dateEnd: string; symbol?: string }) => {
      const params = new URLSearchParams();
      if (dateStart) params.set("date_start", dateStart);
      if (dateEnd) params.set("date_end", dateEnd);
      if (symbol) params.set("symbol", symbol);
      const qs = params.toString();
      const url = `/brsapi/manage/sync/${sectionId}${qs ? `?${qs}` : ""}`;
      const res = await fetch(`/api/v1${url}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
      const result = await res.json() as { success: boolean; data?: { success: boolean; error: string | null; items_count: number; duration_ms: number; skipped: boolean }; error?: string };
      if (!result.success || result.data?.success === false) {
        throw new Error(result.data?.error || result.error || "دریافت داده ناموفق بود");
      }
      return result;
    },
    onMutate: ({ sectionId }) => setSyncingSection(sectionId),
    onSettled: () => {
      setSyncingSection(null);
      queryClient.invalidateQueries({ queryKey: ["brsapi-sections"] });
    },
  });

  const categories = ["all", ...(sourcesData?.categories ?? [])];
  const filteredSources = sourcesData?.sources.filter(
    (s) => filterCategory === "all" || s.category === filterCategory
  );

  return (
    <div className="space-y-5">
      {/* View toggle */}
      <div className="flex gap-2">
        <button onClick={() => setView("pipeline")} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${view === "pipeline" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
          نقشه خط لوله
        </button>
        <button onClick={() => setView("brsapi")} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${view === "brsapi" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
          بخش‌های BrsApi
        </button>
      </div>

      {view === "pipeline" ? (
        <>
          {/* Category filter */}
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <button key={cat} onClick={() => setFilterCategory(cat)}
                className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all ${filterCategory === cat ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
                {cat === "all" ? "همه" : CATEGORY_CONFIG[cat]?.label ?? cat}
              </button>
            ))}
          </div>

          {sourcesLoading ? <TabSkeleton /> : (
            <div className="space-y-2">
              {filteredSources?.map((src) => (
                <PipelineSourceRow key={src.id} source={src} />
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {/* Sync error/success */}
          {syncMutation.isError && <ErrorBox msg={String(syncMutation.error)} />}
          {syncMutation.isSuccess && syncMutation.data?.data && (
            <div className="p-3 bg-accent-emerald/10 border border-accent-emerald/20 rounded-lg text-accent-emerald text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              {(syncMutation.data.data as { skipped?: boolean; items_count?: number; duration_ms?: number }).skipped
                ? "داده‌ها به‌تازگی همگام‌سازی شده‌اند"
                : `${(syncMutation.data.data as { items_count: number }).items_count} رکورد در ${fmtDurationMs((syncMutation.data.data as { duration_ms: number }).duration_ms)} ذخیره شد`
              }
            </div>
          )}

          {/* Category filter for BrsApi */}
          <div className="flex flex-wrap gap-2">
            {["all", "tsetmc", "ime", "commodity", "cryptocurrency", "codal"].map((cat) => (
              <button key={cat} onClick={() => setFilterCategory(cat)}
                className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all ${filterCategory === cat ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
                {cat === "all" ? "همه" : CATEGORY_CONFIG[cat]?.label ?? cat}
              </button>
            ))}
          </div>

          {sectionsLoading ? <TabSkeleton /> : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {sections
                ?.filter((s) => filterCategory === "all" || s.category === filterCategory)
                .map((section) => (
                  <BrsApiSectionCard
                    key={section.id}
                    section={section}
                    onSync={(id, ds, de, sym) => syncMutation.mutate({ sectionId: id, dateStart: ds, dateEnd: de, symbol: sym })}
                    isSyncing={syncingSection === section.id}
                  />
                ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PipelineSourceRow({ source }: { source: PipelineSource }) {
  const [expanded, setExpanded] = useState(false);
  const catCfg = CATEGORY_CONFIG[source.category] ?? { label: source.category, color: "border-r-surface-500" };

  return (
    <div className={`glass-card border-r-2 ${catCfg.color} overflow-hidden`}>
      <button className="w-full text-right px-4 py-3 flex items-center gap-3" onClick={() => setExpanded((x) => !x)}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-surface-200">{source.name}</span>
            <span className="text-[10px] text-surface-500 font-mono">{source.name_en}</span>
            <StatusBadge status={source.pipeline_status} label={STATUS_LABELS[source.pipeline_status] ?? source.pipeline_status} />
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-[10px] text-surface-500">منبع: {source.source}</span>
            <span className="text-[10px] text-surface-500">زمان‌بندی: {source.schedule}</span>
          </div>
        </div>
        {expanded ? <ChevronLeft className="w-4 h-4 text-surface-500 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-surface-500 flex-shrink-0" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-surface-700/50">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
            <InfoPair label="کار" value={source.job_name} mono />
            <InfoPair label="تریگر" value={source.schedule} />
            <InfoPair label="دسته" value={catCfg.label} />
            {source.tables.length > 0 && (
              <InfoPair label="جداول" value={source.tables.join(", ")} mono />
            )}
            {source.last_run && (
              <>
                <InfoPair label="آخرین اجرا" value={fmtTime(source.last_run.completed_at)} />
                <InfoPair label="مدت" value={fmtDurationSec(source.last_run.duration_seconds)} mono />
              </>
            )}
          </div>
          {source.last_run?.error && (
            <div className="mt-3 p-2 bg-accent-rose/10 rounded text-[11px] text-accent-rose font-mono break-all">
              {source.last_run.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InfoPair({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-surface-800/50 rounded-lg p-2">
      <div className="text-[10px] text-surface-500 mb-1">{label}</div>
      <div className={`text-xs text-surface-200 ${mono ? "font-mono" : ""}`}>{value || "—"}</div>
    </div>
  );
}

function BrsApiSectionCard({
  section, onSync, isSyncing,
}: {
  section: ApiSection;
  onSync: (id: string, ds: string, de: string, sym?: string) => void;
  isSyncing: boolean;
}) {
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [symbol, setSymbol] = useState("");
  const catCfg = CATEGORY_CONFIG[section.category] ?? { label: section.category, color: "border-r-surface-500" };
  const needsSymbol = section.id === "nav";
  const syncStatus = section.last_sync?.status ?? null;

  return (
    <div className={`glass-card overflow-hidden border-r-2 ${catCfg.color}`}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{section.icon}</span>
            <div>
              <h3 className="font-bold text-surface-200 text-sm">{section.name}</h3>
              <span className="text-[10px] text-surface-500 font-mono">{section.name_en}</span>
            </div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-400">{catCfg.label}</span>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="bg-surface-800/50 rounded-lg p-2">
            <div className="text-[10px] text-surface-500">تعداد رکوردها</div>
            <div className="text-sm font-bold font-mono text-surface-200">{section.record_count.toLocaleString("en-US")}</div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-2">
            <div className="text-[10px] text-surface-500">آخرین بروزرسانی</div>
            <div className="text-xs font-mono text-surface-400" dir="ltr">{fmtTime(section.last_sync?.completed_at ?? null)}</div>
          </div>
        </div>

        {section.last_sync && (
          <div className="flex items-center gap-2 mb-3 text-[10px]">
            <StatusDot status={syncStatus === "success" ? "ok" : "failing"} />
            <span className="text-surface-500">
              {syncStatus === "success"
                ? `${section.last_sync.items_count} رکورد در ${fmtDurationMs(section.last_sync.duration_ms)}`
                : `خطا: ${section.last_sync.error_message || "نامشخص"}`}
            </span>
          </div>
        )}

        {section.has_date_range && (
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div>
              <label className="text-[10px] text-surface-500 block mb-1">تاریخ شروع</label>
              <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)}
                className="w-full px-2 py-1.5 text-xs bg-surface-800 border border-surface-700 rounded text-surface-200" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500 block mb-1">تاریخ پایان</label>
              <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)}
                className="w-full px-2 py-1.5 text-xs bg-surface-800 border border-surface-700 rounded text-surface-200" />
            </div>
          </div>
        )}

        {needsSymbol && (
          <div className="mb-3">
            <label className="text-[10px] text-surface-500 block mb-1">نماد صندوق (الزامی)</label>
            <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value.trimStart())}
              placeholder="مثلاً ETF یا نماد صندوق" dir="rtl"
              className="w-full px-2 py-1.5 text-xs bg-surface-800 border border-surface-700 rounded text-surface-200" />
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={() => onSync(section.id, dateStart, dateEnd, symbol || undefined)}
            disabled={isSyncing || (needsSymbol && !symbol.trim())}
            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 text-xs font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all">
            {isSyncing
              ? <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> در حال دریافت...</>
              : <><CloudDownload className="w-3.5 h-3.5" /> دریافت و ذخیره</>}
          </button>
          <a href={`/api/v1/brsapi/manage/download/${section.id}?format=csv&limit=1000`} download={`brsapi_${section.id}.csv`}
            className="flex items-center gap-1 px-3 py-2 text-xs font-medium rounded-lg bg-surface-800 text-surface-300 hover:bg-surface-700 transition-all">
            <Download className="w-3.5 h-3.5" /> CSV
          </a>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Jobs Tab
// ──────────────────────────────────────────────────────────────────────────────

function JobsTab() {
  const [view, setView] = useState<"scheduler" | "history">("scheduler");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const { data: schedulerData, isLoading: schLoading } = useQuery({
    queryKey: ["scheduler-jobs"],
    queryFn: () => apiGet<{ success: boolean; data: { jobs: SchedulerJob[]; total: number; enabled: number; disabled: number } }>("/jobs/scheduler").then((r) => r.data!),
    refetchInterval: 15_000,
  });

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs-history", statusFilter, typeFilter, page],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (typeFilter !== "all") params.set("job_type", typeFilter);
      params.set("limit", PAGE_SIZE.toString());
      params.set("offset", (page * PAGE_SIZE).toString());
      return apiGet<{ success: boolean; data: { items: JobRun[]; total: number; stats: Record<string, number>; job_types: string[] } }>(`/jobs?${params}`).then((r) => r.data!);
    },
    enabled: view === "history",
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button onClick={() => setView("scheduler")} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${view === "scheduler" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
          زمان‌بندی‌ها
        </button>
        <button onClick={() => { setView("history"); }} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${view === "history" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
          تاریخچه اجرا
        </button>
      </div>

      {view === "scheduler" ? (
        <>
          {schLoading ? <TabSkeleton /> : schedulerData && (
            <>
              {/* Scheduler summary */}
              <div className="flex gap-3 flex-wrap">
                <StatChip label="کل کارها" value={schedulerData.total} />
                <StatChip label="فعال" value={schedulerData.enabled} color="text-accent-emerald" />
                <StatChip label="غیرفعال" value={schedulerData.disabled} color="text-surface-500" />
              </div>
              <div className="space-y-2">
                {schedulerData.jobs.map((job) => (
                  <SchedulerJobRow key={job.name} job={job} />
                ))}
              </div>
            </>
          )}
        </>
      ) : (
        <>
          {jobsData && (
            <div className="flex gap-3 flex-wrap">
              {["all", "success", "failed", "running", "pending"].map((s) => {
                const count = s === "all" ? jobsData.total : (jobsData.stats[s] ?? 0);
                const isActive = statusFilter === s;
                return (
                  <button key={s} onClick={() => { setStatusFilter(s); setPage(0); }}
                    className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all ${isActive ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
                    {STATUS_LABELS[s] ?? s} ({count})
                  </button>
                );
              })}
            </div>
          )}

          {jobsData && jobsData.job_types.length > 0 && (
            <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(0); }}
              className="px-3 py-1.5 text-xs bg-surface-800 border border-surface-700 rounded text-surface-200 max-w-xs">
              <option value="all">همه نوع‌ها</option>
              {jobsData.job_types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          )}

          {jobsLoading ? <TabSkeleton /> : jobsData && (
            <div className="space-y-2">
              {jobsData.items.map((job) => (
                <JobHistoryRow key={job.id} job={job} />
              ))}
              {jobsData.total > PAGE_SIZE && (
                <div className="flex items-center justify-between pt-2">
                  <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                    className="px-3 py-1.5 text-xs bg-surface-800 text-surface-400 rounded disabled:opacity-40 hover:bg-surface-700">
                    قبلی
                  </button>
                  <span className="text-xs text-surface-500">
                    صفحه {page + 1} از {Math.ceil(jobsData.total / PAGE_SIZE)} ({jobsData.total} کار)
                  </span>
                  <button onClick={() => setPage((p) => p + 1)} disabled={(page + 1) * PAGE_SIZE >= jobsData.total}
                    className="px-3 py-1.5 text-xs bg-surface-800 text-surface-400 rounded disabled:opacity-40 hover:bg-surface-700">
                    بعدی
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatChip({ label, value, color = "text-surface-200" }: { label: string; value: number; color?: string }) {
  return (
    <div className="glass-card px-3 py-2 flex items-center gap-2">
      <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
      <span className="text-[11px] text-surface-500">{label}</span>
    </div>
  );
}

function SchedulerJobRow({ job }: { job: SchedulerJob }) {
  return (
    <div className="glass-card px-4 py-3 flex items-center gap-3">
      <StatusDot status={job.enabled ? "ok" : "unknown"} />
      <div className="flex-1 min-w-0">
        <span className="text-xs font-mono text-surface-200">{job.name}</span>
        {job.description && <p className="text-[10px] text-surface-500 mt-0.5 truncate">{job.description}</p>}
      </div>
      <div className="flex items-center gap-3 text-[10px]">
        {job.next_run_time && (
          <span className="text-surface-500 font-mono" dir="ltr">{fmtTime(job.next_run_time)}</span>
        )}
        <span className={`px-2 py-0.5 rounded-full font-medium ${job.enabled ? "bg-accent-emerald/10 text-accent-emerald" : "bg-surface-800 text-surface-500"}`}>
          {job.enabled ? "فعال" : "غیرفعال"}
        </span>
      </div>
    </div>
  );
}

function JobHistoryRow({ job }: { job: JobRun }) {
  const [expanded, setExpanded] = useState(false);
  const st = job.status;
  return (
    <div className="glass-card overflow-hidden">
      <button className="w-full text-right px-4 py-3 flex items-center gap-3" onClick={() => setExpanded((x) => !x)}>
        <StatusDot status={st === "success" ? "ok" : st === "failed" ? "failing" : st === "running" ? "running" : "unknown"} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono text-surface-200">{job.job_type}</span>
            <StatusBadge status={st === "success" ? "ok" : st === "failed" ? "failing" : st === "running" ? "running" : "unknown"} label={STATUS_LABELS[st] ?? st} />
          </div>
          <div className="text-[10px] text-surface-500 mt-0.5 font-mono" dir="ltr">{fmtTime(job.created_at)}</div>
        </div>
        <span className="text-[11px] font-mono text-surface-500">{fmtDurationSec(job.duration_seconds)}</span>
        {expanded ? <ChevronLeft className="w-4 h-4 text-surface-500" /> : <ChevronRight className="w-4 h-4 text-surface-500" />}
      </button>
      {expanded && job.error_message && (
        <div className="px-4 pb-3 border-t border-surface-700/50">
          <p className="text-[11px] text-accent-rose font-mono mt-2 break-all">{job.error_message}</p>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Storage Tab
// ──────────────────────────────────────────────────────────────────────────────

function StorageTab() {
  const [search, setSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tablePage, setTablePage] = useState(1);
  const [tableSearch, setTableSearch] = useState("");

  const { data: tablesData, isLoading: tablesLoading } = useQuery({
    queryKey: ["db-tables"],
    queryFn: () => apiGet<{ success: boolean; data: { tables: TableInfo[] } }>("/tables").then((r) => r.data!),
    staleTime: 60_000,
  });

  const { data: freshnessData } = useQuery({
    queryKey: ["table-freshness"],
    queryFn: () => apiGet<{ success: boolean; data: { tables: FreshnessEntry[] } }>("/data-admin/table-freshness").then((r) => r.data!),
    staleTime: 120_000,
  });

  const { data: tableRowsData, isLoading: tableRowsLoading } = useQuery({
    queryKey: ["table-rows", selectedTable, tablePage, tableSearch],
    queryFn: () => {
      if (!selectedTable) return null;
      const params = new URLSearchParams({ page: tablePage.toString(), page_size: "30" });
      if (tableSearch) params.set("search", tableSearch);
      return apiGet<{ success: boolean; data: { table: string; columns: { name: string; type: string }[]; rows: Record<string, unknown>[]; total: number; total_pages: number } }>(`/tables/${selectedTable}?${params}`).then((r) => r.data!);
    },
    enabled: !!selectedTable,
  });

  const freshnessMap: Record<string, FreshnessEntry> = {};
  freshnessData?.tables.forEach((f) => { freshnessMap[f.table] = f; });

  const filteredTables = tablesData?.tables.filter(
    (t) => !search || t.name.toLowerCase().includes(search.toLowerCase())
  );

  if (tablesLoading) return <TabSkeleton />;

  return (
    <div className="space-y-4">
      {/* Summary */}
      {tablesData && (
        <div className="flex gap-3 flex-wrap">
          <StatChip label="کل جداول" value={tablesData.tables.length} />
          <StatChip label="با freshness" value={Object.keys(freshnessMap).length} color="text-accent-emerald" />
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو در نام جدول..."
          className="w-full pr-9 pl-3 py-2 text-xs bg-surface-800 border border-surface-700 rounded-lg text-surface-200 placeholder:text-surface-600" dir="ltr" />
      </div>

      <div className="grid gap-2">
        {filteredTables?.map((t) => {
          const fresh = freshnessMap[t.name];
          return (
            <button key={t.name} onClick={() => { setSelectedTable(t.name === selectedTable ? null : t.name); setTablePage(1); setTableSearch(""); }}
              className={`glass-card px-4 py-3 text-right w-full flex items-center gap-3 hover:bg-surface-800/60 transition-colors ${selectedTable === t.name ? "ring-1 ring-primary-500" : ""}`}>
              <Table2 className="w-4 h-4 text-surface-500 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-mono text-surface-200">{t.name}</span>
                  {fresh && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      (fresh.staleness_seconds ?? 999999) < 300 ? "bg-accent-emerald/10 text-accent-emerald" :
                      (fresh.staleness_seconds ?? 999999) < 86400 ? "bg-accent-amber/10 text-accent-amber" :
                      "bg-accent-rose/10 text-accent-rose"}`}>
                      {fresh.staleness_label}
                    </span>
                  )}
                </div>
                {fresh && <p className="text-[10px] text-surface-500 mt-0.5">{fresh.description}</p>}
              </div>
              <div className="text-right">
                <div className="text-sm font-bold font-mono text-surface-200">{fmtRows(t.row_count, t.approximate)}</div>
                <div className="text-[10px] text-surface-500">رکورد</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Table data preview */}
      {selectedTable && (
        <div className="glass-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-surface-300 font-mono">{selectedTable}</h3>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-surface-500" />
                <input value={tableSearch} onChange={(e) => { setTableSearch(e.target.value); setTablePage(1); }} placeholder="جستجو..."
                  className="pr-6 pl-2 py-1 text-[11px] bg-surface-800 border border-surface-700 rounded text-surface-200 w-40" dir="ltr" />
              </div>
              <button onClick={() => setSelectedTable(null)} className="p-1 hover:bg-surface-800 rounded text-surface-500 text-xs">✕</button>
            </div>
          </div>

          {tableRowsLoading ? (
            <div className="h-32 flex items-center justify-center">
              <span className="w-5 h-5 border-2 border-primary-400/30 border-t-primary-400 rounded-full animate-spin" />
            </div>
          ) : tableRowsData ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px] font-mono">
                  <thead>
                    <tr className="border-b border-surface-700">
                      {tableRowsData.columns.map((col) => (
                        <th key={col.name} className="text-left px-2 py-1.5 text-surface-400 whitespace-nowrap">
                          {col.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableRowsData.rows.map((row, i) => (
                      <tr key={i} className="border-b border-surface-800/60 hover:bg-surface-800/30">
                        {tableRowsData.columns.map((col) => (
                          <td key={col.name} className="px-2 py-1.5 text-surface-300 max-w-[200px] truncate">
                            {row[col.name] === null ? <span className="text-surface-600">null</span> : String(row[col.name])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {tableRowsData.total_pages > 1 && (
                <div className="flex items-center justify-between pt-1">
                  <button onClick={() => setTablePage((p) => Math.max(1, p - 1))} disabled={tablePage === 1}
                    className="p-1 rounded hover:bg-surface-800 disabled:opacity-40 text-surface-400">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                  <span className="text-[10px] text-surface-500">
                    صفحه {tablePage} از {tableRowsData.total_pages} ({tableRowsData.total} ردیف)
                  </span>
                  <button onClick={() => setTablePage((p) => p + 1)} disabled={tablePage >= tableRowsData.total_pages}
                    className="p-1 rounded hover:bg-surface-800 disabled:opacity-40 text-surface-400">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Diagnostics Tab
// ──────────────────────────────────────────────────────────────────────────────

function DiagnosticsTab() {
  const [dlWindow, setDlWindow] = useState<"all" | "24h" | "today" | "week">("24h");

  const { data: queueStats, isLoading: qsLoading } = useQuery({
    queryKey: ["queue-stats"],
    queryFn: () => apiGet<{ success: boolean; data: QueueStats }>("/jobs/queue/stats").then((r) => r.data!),
    refetchInterval: 20_000,
  });

  const { data: dlSummary, isLoading: dlLoading } = useQuery({
    queryKey: ["dl-summary", dlWindow],
    queryFn: () => apiGet<{ success: boolean; data: DeadLetterSummary }>(`/jobs/queue/summary?window=${dlWindow}`).then((r) => r.data!),
    refetchInterval: 30_000,
  });

  const { data: freshnessData, isLoading: freshLoading } = useQuery({
    queryKey: ["table-freshness-diag"],
    queryFn: () => apiGet<{ success: boolean; data: { tables: FreshnessEntry[] } }>("/data-admin/table-freshness").then((r) => r.data!),
    staleTime: 120_000,
  });

  const staleTables = freshnessData?.tables.filter(
    (t) => t.staleness_seconds !== null && t.staleness_seconds > 86400
  ) ?? [];

  return (
    <div className="space-y-5">
      {/* Queue stats */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
          <Server className="w-4 h-4 text-accent-amber" />
          آمار صف پردازش
        </h3>
        {qsLoading ? <div className="h-16"><TabSkeleton /></div> : queueStats && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <InfoPair label="صف اصلی" value={queueStats.queue_size.toString()} mono />
            <InfoPair label="صف مرده" value={queueStats.dead_letter_size.toString()} mono />
            <InfoPair label="وضعیت صف" value={queueStats.queue_enabled ? "فعال" : "غیرفعال"} />
            <InfoPair label="نام صف" value={queueStats.config.queue} mono />
            <InfoPair label="نام DLQ" value={queueStats.config.dead_letter} mono />
            <InfoPair label="حداکثر تلاش مجدد" value={queueStats.config.max_retries.toString()} mono />
          </div>
        )}
      </div>

      {/* Dead-letter summary */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-surface-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-accent-rose" />
            صف مرده (Dead-Letter)
          </h3>
          <div className="flex gap-1">
            {(["24h", "today", "week", "all"] as const).map((w) => (
              <button key={w} onClick={() => setDlWindow(w)}
                className={`px-2 py-1 text-[10px] rounded transition-all ${dlWindow === w ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400"}`}>
                {w === "24h" ? "۲۴ ساعت" : w === "today" ? "امروز" : w === "week" ? "هفته" : "همه"}
              </button>
            ))}
          </div>
        </div>

        {dlLoading ? <div className="h-16"><TabSkeleton /></div> : dlSummary && (
          <div className="space-y-3">
            <div className="text-2xl font-bold font-mono text-surface-200">{dlSummary.total} <span className="text-sm font-normal text-surface-500">پیام</span></div>

            {Object.keys(dlSummary.job_name_distribution).length > 0 && (
              <div>
                <p className="text-[11px] text-surface-500 mb-2">توزیع بر اساس نوع کار:</p>
                <div className="space-y-1.5">
                  {Object.entries(dlSummary.job_name_distribution)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 8)
                    .map(([name, count]) => (
                      <div key={name} className="flex items-center gap-2">
                        <div className="flex-1 bg-surface-800 rounded h-1.5 overflow-hidden">
                          <div className="bg-accent-rose h-full" style={{ width: `${Math.min(100, (count / (dlSummary.total || 1)) * 100)}%` }} />
                        </div>
                        <span className="text-[11px] font-mono text-surface-400 w-32 truncate">{name}</span>
                        <span className="text-[11px] font-mono text-accent-rose w-8 text-right">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {dlSummary.top_errors && dlSummary.top_errors.length > 0 && (
              <div>
                <p className="text-[11px] text-surface-500 mb-2">متداول‌ترین خطاها:</p>
                <div className="space-y-1.5">
                  {dlSummary.top_errors.slice(0, 5).map((e, i) => (
                    <div key={i} className="bg-surface-800/60 rounded p-2">
                      <div className="text-[10px] font-mono text-accent-rose break-all">{e.error}</div>
                      <div className="text-[10px] text-surface-500 mt-0.5">{e.count} بار</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dlSummary.total === 0 && (
              <div className="flex items-center gap-2 text-accent-emerald text-sm">
                <CheckCircle className="w-4 h-4" />
                صف مرده خالی است
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stale tables */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-accent-amber" />
          جداول قدیمی (بیش از ۲۴ ساعت)
        </h3>
        {freshLoading ? <div className="h-10"><TabSkeleton /></div> : (
          staleTables.length === 0 ? (
            <div className="flex items-center gap-2 text-accent-emerald text-sm">
              <CheckCircle className="w-4 h-4" />
              همه جداول تازه هستند
            </div>
          ) : (
            <div className="space-y-2">
              {staleTables.map((t) => (
                <div key={t.table} className="bg-surface-800/60 rounded-lg p-3 flex items-center justify-between gap-3">
                  <div>
                    <span className="text-xs font-mono text-surface-200">{t.table}</span>
                    <p className="text-[10px] text-surface-500 mt-0.5">{t.description}</p>
                  </div>
                  <span className="text-[11px] text-accent-amber font-mono">{t.staleness_label}</span>
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Shared components
// ──────────────────────────────────────────────────────────────────────────────

function TabSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="glass-card p-4">
          <Skeleton className="h-12 w-full" />
        </div>
      ))}
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="p-4 bg-accent-rose/10 border border-accent-rose/20 rounded-lg text-accent-rose text-sm">
      {msg}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
//  Main page
// ──────────────────────────────────────────────────────────────────────────────

export default function DataAdminPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  return (
    <AppLayout
      title="مرکز مدیریت داده"
      subtitle="نمای کلی ورودی‌ها، خطوط لوله، ذخیره‌سازی و سلامت داده‌ها"
    >
      {/* Tab navigation */}
      <div className="flex flex-wrap gap-1 mb-6 border-b border-surface-700/50 pb-3">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === key
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                : "text-surface-400 hover:text-surface-200 hover:bg-surface-800"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "sources" && <SourcesTab />}
      {activeTab === "jobs" && <JobsTab />}
      {activeTab === "storage" && <StorageTab />}
      {activeTab === "diagnostics" && <DiagnosticsTab />}
    </AppLayout>
  );
}
