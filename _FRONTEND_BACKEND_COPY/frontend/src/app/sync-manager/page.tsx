"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import JobControlRow from "@/components/sync/JobControlRow";
import { formatCron, formatTime, type SchedulerJobInfo } from "@/lib/job-format";
import { apiGet, apiPost } from "@/lib/api";
import { applyCustomThresholds } from "@/lib/sync-settings";
import { useSyncSettings } from "@/hooks/useSyncSettings";
import { useBackgroundBackfill } from "@/hooks/useBackgroundBackfill";
import type { BackfillState } from "@/hooks/useBackgroundBackfill";

// ── Dynamic chart ──
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 200 }} />,
});

// ── Types ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface TableSyncInfo {
  last_fetched: string | null;
  record_count: number;
  age_minutes: number;
  status: "ok" | "stale" | "outdated" | "missing" | "unknown" | "error";
  max_age_minutes: number;
  error?: string;
}

type SyncStatusMap = Record<string, TableSyncInfo>;

interface SyncLogEntry {
  time: string;
  endpoint: string;
  category: string;
  status: string;
  items_count: number;
  duration_ms: number;
  completed_at: string | null;
}

interface SchedulerResponse {
  jobs: SchedulerJobInfo[];
  total: number;
  enabled: number;
  disabled: number;
}

interface ConnTestResult {
  reachable: boolean;
  configured: boolean;
  key: string;
  message: string;
  http_status?: number | null;
  elapsed_ms?: number;
  symbols_count?: number;
}

// ── Config ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

const TABLE_CONFIG: Record<string, { label: string; icon: string; order: number }> = {
  symbols:    { label: "نمادها (بورس)",       icon: "📊", order: 1 },
  commodities:{ label: "کامودیتی‌ها",          icon: "🌍", order: 2 },
  gold_coin:  { label: "طلا و سکه",            icon: "🥇", order: 3 },
  currency:   { label: "نرخ ارز",              icon: "💵", order: 4 },
  crypto:     { label: "ارز دیجیتال",           icon: "₿",  order: 5 },
  index:      { label: "شاخص‌ها",              icon: "📈", order: 6 },
  ime_futures:{ label: "آتی کالا",              icon: "🛢️", order: 7 },
  ime_options:{ label: "اختیار کالا",           icon: "📋", order: 8 },
  options:    { label: "آپشن‌ها",               icon: "🎯", order: 9 },
  codal:      { label: "کدال",                 icon: "🏢", order: 10 },
};

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  ok:       { label: "به‌روز",      color: "text-accent-emerald", bg: "bg-accent-emerald/15" },
  stale:    { label: "کمی قدیمی",   color: "text-accent-amber",   bg: "bg-accent-amber/15" },
  outdated: { label: "قدیمی",       color: "text-accent-rose",    bg: "bg-accent-rose/15" },
  missing:  { label: "بدون داده",   color: "text-surface-500",    bg: "bg-surface-800" },
  unknown:  { label: "نامشخص",      color: "text-surface-400",    bg: "bg-surface-800" },
  error:    { label: "خطا",          color: "text-accent-rose",    bg: "bg-accent-rose/15" },
};

const CATEGORY_CONFIG: Record<string, { label: string; icon: string }> = {
  tsetmc:    { label: "بورس",      icon: "📈" },
  ime:       { label: "کالا",      icon: "🛢️" },
  commodity: { label: "کامودیتی",  icon: "🌍" },
  crypto:    { label: "کریپتو",    icon: "₿"  },
  gold:      { label: "طلا و ارز", icon: "🥇" },
  codal:     { label: "کدال",      icon: "🏢" },
};

const SECTION_ID_MAP: Record<string, string> = {
  symbols:     "all-symbols",
  commodities: "commodity",
  gold_coin:   "gold-coin",
  currency:    "currency",
  crypto:      "crypto",
  index:       "index-tse",
  ime_futures: "ime-futures",
  ime_options: "ime-options",
  options:     "option",
  codal:       "codal",
};

// The four quota-hungry full-market backfill jobs get special treatment in
// the Jobs tab: pinned to the top of the table, highlighted rows and a
// "⭐ ویژه" badge (their runs route through the background backfill APIs).
const SPECIAL_BACKFILL_JOBS: readonly string[] = [
  "brsapi_candlesticks_all",
  "brsapi_shareholders_all",
  "brsapi_history_price_all",
  "brsapi_history_real_legal_all",
];

const BACKFILL_STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  running:   { label: "در حال اجرا", color: "text-primary-300",      bg: "bg-primary-600/20" },
  done:      { label: "کامل شد",     color: "text-accent-emerald",   bg: "bg-accent-emerald/15" },
  cancelled: { label: "لغو شد",      color: "text-accent-amber",     bg: "bg-accent-amber/15" },
  error:     { label: "خطا",         color: "text-accent-rose",      bg: "bg-accent-rose/15" },
  idle:      { label: "آماده",       color: "text-surface-400",      bg: "bg-surface-800" },
};

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return `${diffSec} ثانیه پیش`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} دقیقه پیش`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} ساعت پیش`;
    return `${Math.floor(diffHr / 24)} روز پیش`;
  } catch { return "—"; }
}

function formatNumber(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

// ── Toast ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: "success" | "error" | "warning"; onClose: () => void }) {
  const ref = useRef(onClose);
  useEffect(() => {
    ref.current = onClose;
  }, [onClose]);
  useEffect(() => {
    const t = setTimeout(() => ref.current(), 4000);
    return () => clearTimeout(t);
  }, []);

  const styles = {
    success: "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30",
    error: "bg-accent-rose/15 text-accent-rose border-accent-rose/30",
    warning: "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
  };

  return (
    <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-2 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium border ${styles[type]}`}
      style={{ animation: "slideUp 0.3s ease-out" }}>
      <span className="material-icons text-lg">{type === "success" ? "check_circle" : type === "warning" ? "warning_amber" : "error"}</span>
      <span>{message}</span>
      <button onClick={onClose} className="mr-3 opacity-60 hover:opacity-100"><span className="material-icons">close</span></button>
      <style>{`@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}`}</style>
    </div>
  );
}

// ── Status Dot ─────────────────────────────────────────────────────────────────────────────────────────────────────────

function StatusDot({ status, size = "md" }: { status: string; size?: "sm" | "md" }) {
  const cs = STATUS_META[status];
  const sz = size === "sm" ? "w-1.5 h-1.5" : "w-3 h-3";
  return <span className={`${sz} rounded-full shrink-0 ${cs?.bg || "bg-surface-600"}`} />;
}

// ── Backfill Progress Card ────────────────────────────────────────────────────────────────────────────────────────────

function BackfillProgressCard({ title, icon, unitLabel, backfill, onCancel }: {
  title: string;
  icon: string;
  unitLabel: string;
  backfill: BackfillState;
  onCancel: () => void;
}) {
  const pct = backfill.total_symbols > 0
    ? Math.min(100, Math.round((backfill.processed / backfill.total_symbols) * 100))
    : backfill.status === "running" ? 5 : 100;

  return (
    <Card title={`${icon} ${title} — ${BACKFILL_STATUS_META[backfill.status]?.label || backfill.status}`} actions={
      backfill.status === "running" ? (
        <button onClick={onCancel}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-accent-rose/10 text-accent-rose border border-accent-rose/25 hover:bg-accent-rose/20 transition-all">
          <span className="material-icons text-sm">stop_circle</span>
          توقف
        </button>
      ) : (
        <span className="text-[10px] text-surface-600">
          {backfill.finished_at ? `پایان: ${formatRelativeTime(backfill.finished_at)}` : ""}
        </span>
      )
    }>
      <div className="mb-3">
        <div className="flex items-center justify-between text-[10px] text-surface-500 mb-1.5 gap-2">
          <span className="truncate">
            {backfill.current_symbol
              ? <span>نماد فعلی: <span className="font-mono text-indigo-300">{backfill.current_symbol}</span></span>
              : backfill.message || "..."}
          </span>
          <span className="font-mono shrink-0">{backfill.processed}/{backfill.total_symbols || "—"} نماد ({pct}%)</span>
        </div>
        <div className="h-2 rounded-full bg-surface-800 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${pct}%`,
              background: backfill.status === "running"
                ? "linear-gradient(90deg,#4f46e5,#818cf8)"
                : backfill.status === "done" ? "#10b981" : backfill.status === "error" ? "#f43f5e" : "#f59e0b",
            }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
        <div className="bg-surface-800/50 rounded-xl p-2.5">
          <p className="text-lg font-black text-indigo-300 font-mono">{formatNumber(backfill.items)}</p>
          <p className="text-[9px] text-surface-500 mt-0.5">{unitLabel}</p>
        </div>
        <div className="bg-surface-800/50 rounded-xl p-2.5">
          <p className="text-lg font-black text-accent-emerald font-mono">{formatNumber(backfill.ok)}</p>
          <p className="text-[9px] text-surface-500 mt-0.5">درخواست موفق</p>
        </div>
        <div className="bg-surface-800/50 rounded-xl p-2.5">
          <p className={`text-lg font-black font-mono ${backfill.fail > 0 ? "text-accent-rose" : "text-surface-600"}`}>{formatNumber(backfill.fail)}</p>
          <p className="text-[9px] text-surface-500 mt-0.5">خطا</p>
        </div>
        <div className="bg-surface-800/50 rounded-xl p-2.5">
          <p className="text-lg font-black text-surface-200 font-mono">{backfill.total_symbols ? formatNumber(backfill.total_symbols) : "—"}</p>
          <p className="text-[9px] text-surface-500 mt-0.5">نماد برنامه‌ریزی‌شده</p>
        </div>
      </div>

      {backfill.message && backfill.status === "running" && (
        <p className="mt-3 text-[10px] text-surface-400 text-center">{backfill.message}</p>
      )}
      {backfill.error && (
        <p className="mt-3 text-[10px] text-accent-rose bg-accent-rose/10 border border-accent-rose/20 rounded-lg p-2">⚠️ {backfill.error}</p>
      )}
    </Card>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function SyncManagerPage() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "warning" } | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "tables" | "jobs">("dashboard");
  const [isSyncingAll, setIsSyncingAll] = useState(false);
  const [timeRange, setTimeRange] = useState<string>("48h");

  // ── Load custom freshness thresholds (SSR-safe) ──
  const [customSettings, setCustomSettings] = useSyncSettings();

  // ── Fetch sync status ──
  const { data: syncStatus, isLoading: statusLoading } = useQuery({
    queryKey: ["sync-manager-status"],
    queryFn: async (): Promise<SyncStatusMap> => {
      const res = await apiGet<{ success: boolean; data: SyncStatusMap }>("/brsapi/sync-status");
      return res?.data ?? {};
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ── Fetch sync history ──
  const timeRangeHours = timeRange === "24h" ? 24 : timeRange === "48h" ? 48 : timeRange === "7d" ? 168 : timeRange === "30d" ? 720 : 48;
  const timeRangeLabel = { "24h": "۲۴ ساعت", "48h": "۴۸ ساعت", "7d": "۷ روز", "30d": "۳۰ روز" }[timeRange] || "۴۸ ساعت";
  const { data: syncHistory } = useQuery({
    queryKey: ["sync-manager-history", timeRange],
    queryFn: async (): Promise<SyncLogEntry[]> => {
      const res = await apiGet<{ success: boolean; data: SyncLogEntry[] }>(`/brsapi/sync-history?hours=${timeRangeHours}&limit=300`);
      return res?.data ?? [];
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  // ── Fetch scheduler jobs ──
  const { data: schedulerData, isLoading: schedulerLoading } = useQuery({
    queryKey: ["sync-manager-scheduler"],
    queryFn: async (): Promise<SchedulerResponse> => {
      const res = await apiGet<{ success: boolean; data: SchedulerResponse }>("/jobs/scheduler");
      return res?.data ?? { jobs: [], total: 0, enabled: 0, disabled: 0 };
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // ── Apply custom freshness thresholds ──
  const effectiveStatus = syncStatus ? applyCustomThresholds(syncStatus, customSettings) : undefined;

  // ── Process sync status ──
  const entries = effectiveStatus
    ? Object.entries(effectiveStatus)
        .filter(([, info]) => info.record_count > 0 || info.status !== "missing")
        .sort(([aKey], [bKey]) => (TABLE_CONFIG[aKey]?.order ?? 99) - (TABLE_CONFIG[bKey]?.order ?? 99))
    : [];

  const okCount = entries.filter(([, i]) => i.status === "ok").length;
  const staleCount = entries.filter(([, i]) => i.status === "stale").length;
  const outdatedCount = entries.filter(([, i]) => i.status === "outdated").length;
  const missingCount = entries.filter(([, i]) => i.status === "missing").length;
  const totalCount = entries.length;
  const healthScore = totalCount > 0 ? Math.round((okCount / totalCount) * 100) : 0;
  const healthColor = healthScore >= 80 ? "text-accent-emerald" : healthScore >= 50 ? "text-accent-amber" : "text-accent-rose";

  // ── Process scheduler ──
  const schedulerJobs = schedulerData?.jobs ?? [];
  const enabledJobs = schedulerData?.enabled ?? 0;
  const disabledJobs = schedulerData?.disabled ?? 0;
  const candleJob = schedulerJobs.find(j => j.name === "brsapi_candlesticks_all");
  const shareholderJob = schedulerJobs.find(j => j.name === "brsapi_shareholders_all");
  const historyPriceJob = schedulerJobs.find(j => j.name === "brsapi_history_price_all");
  const historyRealLegalJob = schedulerJobs.find(j => j.name === "brsapi_history_real_legal_all");

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

  // ── Handlers ──

  const handleSyncAll = useCallback(async () => {
    setIsSyncingAll(true);
    setToast({ message: "🔄 شروع sync همه بخش‌ها...", type: "warning" });
    const sectionKeys = Object.keys(SECTION_ID_MAP);
    let successCount = 0;
    let failCount = 0;
    for (let i = 0; i < sectionKeys.length; i++) {
      const key = sectionKeys[i];
      const sectionId = SECTION_ID_MAP[key];
      const label = TABLE_CONFIG[key]?.label || key;
      try {
        const res = await apiPost<{ success: boolean; data: { items_count: number; duration_ms: number } }>(`/brsapi/manage/sync/${sectionId}`);
        if (res?.success) {
          successCount++;
        } else {
          failCount++;
        }
      } catch {
        failCount++;
      }
      setToast({
        message: `🔄 sync بخش‌ها: ${i + 1}/${sectionKeys.length} (✅ ${successCount} موفق, ❌ ${failCount} خطا)`,
        type: failCount > 0 && successCount === 0 ? "error" : "warning",
      });
    }
    queryClient.invalidateQueries({ queryKey: ["sync-manager-status"] });
    queryClient.invalidateQueries({ queryKey: ["sync-manager-history"] });
    setIsSyncingAll(false);
    if (failCount === 0) {
      setToast({ message: `✅ sync همه ${successCount} بخش با موفقیت انجام شد`, type: "success" });
    } else {
      setToast({ message: `⚠️ sync کامل شد: ${successCount} موفق، ${failCount} خطا`, type: "warning" });
    }
  }, [queryClient]);

  const handleSyncNow = useCallback(async (key: string) => {
    const sectionId = SECTION_ID_MAP[key];
    if (!sectionId) { setToast({ message: `بخش '${key}' پشتیبانی نمی‌شود`, type: "error" }); return; }
    setToast({ message: `🔄 در حال sync ${TABLE_CONFIG[key]?.label || key}...`, type: "warning" });
    try {
      const res = await apiPost<{ success: boolean; data: { items_count: number; duration_ms: number } }>(`/brsapi/manage/sync/${sectionId}`);
      if (res?.success && res.data) {
        setToast({ message: `✅ ${TABLE_CONFIG[key]?.label || key}: ${res.data.items_count} رکورد در ${formatDuration(res.data.duration_ms)}`, type: "success" });
      } else {
        setToast({ message: `❌ ${TABLE_CONFIG[key]?.label || key}: خطا`, type: "error" });
      }
      queryClient.invalidateQueries({ queryKey: ["sync-manager-status"] });
      queryClient.invalidateQueries({ queryKey: ["sync-manager-history"] });
    } catch (err) {
      setToast({ message: `❌ ${TABLE_CONFIG[key]?.label || key}: ${String(err)}`, type: "error" });
    }
  }, [queryClient]);

  const handleToggleJob = useCallback(async (jobName: string) => {
    try {
      const res = await apiPost<{ success: boolean; data: { enabled: boolean; message: string } }>(`/jobs/scheduler/${jobName}/toggle`);
      if (res?.success) {
        setToast({ message: `${res.data.enabled ? "✅ فعال" : "⏸️ غیرفعال"} شد: ${jobName}`, type: "success" });
        queryClient.invalidateQueries({ queryKey: ["sync-manager-scheduler"] });
      }
    } catch (err) {
      setToast({ message: `❌ ${jobName}: ${String(err)}`, type: "error" });
    }
  }, [queryClient]);

  // ── Manual full-market backfills (admin) — candles + shareholders + history ──
  const candleBackfill = useBackgroundBackfill(
    "/brsapi/manage/sync-all-candlesticks",
    "/brsapi/manage/sync-all-candlesticks/status",
    "/brsapi/manage/sync-all-candlesticks/cancel",
  );
  const shareholderBackfill = useBackgroundBackfill(
    "/brsapi/manage/sync-all-shareholders",
    "/brsapi/manage/sync-all-shareholders/status",
    "/brsapi/manage/sync-all-shareholders/cancel",
  );
  const historyPriceBackfill = useBackgroundBackfill(
    "/brsapi/manage/sync-all-history-price",
    "/brsapi/manage/sync-all-history-price/status",
    "/brsapi/manage/sync-all-history-price/cancel",
  );
  const historyRealLegalBackfill = useBackgroundBackfill(
    "/brsapi/manage/sync-all-history-real-legal",
    "/brsapi/manage/sync-all-history-real-legal/status",
    "/brsapi/manage/sync-all-history-real-legal/cancel",
  );
  const [isTestingConn, setIsTestingConn] = useState(false);
  const [connTest, setConnTest] = useState<ConnTestResult | null>(null);

  // Destructure stable hook functions so exhaustive-deps stays clean.
  const startCandleBackfill = candleBackfill.startBackfill;
  const cancelCandleBackfill = candleBackfill.cancelBackfill;
  const startShareholderBackfill = shareholderBackfill.startBackfill;
  const cancelShareholderBackfill = shareholderBackfill.cancelBackfill;
  const startHistoryPriceBackfill = historyPriceBackfill.startBackfill;
  const cancelHistoryPriceBackfill = historyPriceBackfill.cancelBackfill;
  const startHistoryRealLegalBackfill = historyRealLegalBackfill.startBackfill;
  const cancelHistoryRealLegalBackfill = historyRealLegalBackfill.cancelBackfill;

  const handleStartCandleBackfill = useCallback(async () => {
    setToast({ message: "🕯️ در حال شروع بکفیل کندل همه نمادها...", type: "warning" });
    const res = await startCandleBackfill();
    if (res === undefined) {
      setToast({ message: "❌ شروع بکفیل: خطا در برقراری ارتباط با سرور", type: "error" });
    } else if (res.started) {
      setToast({ message: res.message || "بکفیل شروع شد", type: "success" });
      // Jump to the dashboard so the live progress card is immediately visible
      // (the job can be started from the Jobs tab banner / table row too).
      setActiveTab("dashboard");
    } else {
      setToast({ message: res.message || "شروع بکفیل ناموفق بود", type: "warning" });
    }
  }, [startCandleBackfill]);

  const handleCancelCandleBackfill = useCallback(async () => {
    const msg = await cancelCandleBackfill();
    setToast({ message: msg || "درخواست لغو ارسال شد", type: "warning" });
  }, [cancelCandleBackfill]);

  const handleStartShareholderBackfill = useCallback(async () => {
    setToast({ message: "🏛️ در حال شروع بکفیل سهامداران همه نمادها...", type: "warning" });
    const res = await startShareholderBackfill();
    if (res === undefined) {
      setToast({ message: "❌ شروع بکفیل: خطا در برقراری ارتباط با سرور", type: "error" });
    } else if (res.started) {
      setToast({ message: res.message || "بکفیل شروع شد", type: "success" });
    } else {
      setToast({ message: res.message || "شروع بکفیل ناموفق بود", type: "warning" });
    }
  }, [startShareholderBackfill]);

  const handleCancelShareholderBackfill = useCallback(async () => {
    const msg = await cancelShareholderBackfill();
    setToast({ message: msg || "درخواست لغو ارسال شد", type: "warning" });
  }, [cancelShareholderBackfill]);

  const handleStartHistoryPriceBackfill = useCallback(async () => {
    setToast({ message: "📜 در حال شروع بکفیل تاریخچه قیمت همه نمادها...", type: "warning" });
    const res = await startHistoryPriceBackfill();
    if (res === undefined) {
      setToast({ message: "❌ شروع بکفیل: خطا در برقراری ارتباط با سرور", type: "error" });
    } else if (res.started) {
      setToast({ message: res.message || "بکفیل شروع شد", type: "success" });
    } else {
      setToast({ message: res.message || "شروع بکفیل ناموفق بود", type: "warning" });
    }
  }, [startHistoryPriceBackfill]);

  const handleCancelHistoryPriceBackfill = useCallback(async () => {
    const msg = await cancelHistoryPriceBackfill();
    setToast({ message: msg || "درخواست لغو ارسال شد", type: "warning" });
  }, [cancelHistoryPriceBackfill]);

  const handleStartHistoryRealLegalBackfill = useCallback(async () => {
    setToast({ message: "👥 در حال شروع بکفیل حقیقی/حقوقی همه نمادها...", type: "warning" });
    const res = await startHistoryRealLegalBackfill();
    if (res === undefined) {
      setToast({ message: "❌ شروع بکفیل: خطا در برقراری ارتباط با سرور", type: "error" });
    } else if (res.started) {
      setToast({ message: res.message || "بکفیل شروع شد", type: "success" });
    } else {
      setToast({ message: res.message || "شروع بکفیل ناموفق بود", type: "warning" });
    }
  }, [startHistoryRealLegalBackfill]);

  const handleCancelHistoryRealLegalBackfill = useCallback(async () => {
    const msg = await cancelHistoryRealLegalBackfill();
    setToast({ message: msg || "درخواست لغو ارسال شد", type: "warning" });
  }, [cancelHistoryRealLegalBackfill]);

  const handleTestConnection = useCallback(async () => {
    setIsTestingConn(true);
    setConnTest(null);
    try {
      const res = await apiPost<{ success: boolean; data: ConnTestResult }>("/brsapi/manage/test-connection");
      const data = res?.data;
      if (data) {
        setConnTest(data);
        setToast({
          message: data.message || (data.reachable ? "اتصال برقرار است" : "اتصال برقرار نیست"),
          type: data.reachable ? "success" : "error",
        });
      } else {
        setConnTest({ reachable: false, configured: false, key: "", message: "پاسخی از سرور دریافت نشد" });
        setToast({ message: "پاسخی از سرور دریافت نشد", type: "error" });
      }
    } catch (err) {
      setConnTest({ reachable: false, configured: false, key: "", message: String(err) });
      setToast({ message: `❌ تست اتصال: ${String(err)}`, type: "error" });
    } finally {
      setIsTestingConn(false);
    }
  }, []);

  const handleRunJob = useCallback(async (jobName: string) => {
    // The full-market candlestick job takes hours (rate-limited to 2 req/10s),
    // so its run is routed through the background backfill endpoint with live
    // progress — never block the HTTP request for the whole chunk.
    if (jobName === "brsapi_candlesticks_all") {
      await handleStartCandleBackfill();
      return;
    }
    if (jobName === "brsapi_shareholders_all") {
      await handleStartShareholderBackfill();
      return;
    }
    if (jobName === "brsapi_history_price_all") {
      await handleStartHistoryPriceBackfill();
      return;
    }
    if (jobName === "brsapi_history_real_legal_all") {
      await handleStartHistoryRealLegalBackfill();
      return;
    }
    setToast({ message: `🔄 در حال اجرا: ${jobName}...`, type: "warning" });
    try {
      const res = await apiPost<{ success: boolean; data: { success: boolean; items_count?: number; duration_ms?: number; message?: string } }>(`/jobs/scheduler/${jobName}/run`);
      if (res?.success && res.data?.success) {
        setToast({ message: `✅ ${jobName}: ${res.data.items_count ?? 0} آیتم در ${formatDuration(res.data.duration_ms ?? 0)}`, type: "success" });
      } else {
        setToast({ message: `❌ ${jobName}: ${res?.data?.message || "خطا"}`, type: "error" });
      }
      queryClient.invalidateQueries({ queryKey: ["sync-manager-scheduler"] });
    } catch (err) {
      setToast({ message: `❌ ${jobName}: ${String(err)}`, type: "error" });
    }
  }, [queryClient, handleStartCandleBackfill, handleStartShareholderBackfill, handleStartHistoryPriceBackfill, handleStartHistoryRealLegalBackfill]);

  // Recent events
  const recentEvents = (syncHistory ?? []).slice(0, 15);

  return (
    <AppLayout title="📡 مدیریت همگام‌سازی" subtitle="داشبورد یکپارچه وضعیت sync، freshness و زمان‌بندی">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── Top-level summary cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${healthColor}`}>{healthScore}%</p>
          <p className="text-[10px] text-surface-500 mt-0.5">سلامت داده‌ها</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className="text-2xl font-black text-accent-emerald">{okCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">به‌روز</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${staleCount > 0 ? "text-accent-amber" : "text-surface-600"}`}>{staleCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">کمی قدیمی</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${enabledJobs > 0 ? "text-accent-emerald" : "text-surface-600"}`}>{enabledJobs}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">Scheduler فعال</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${disabledJobs > 0 ? "text-surface-400" : "text-surface-600"}`}>{disabledJobs}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">Scheduler غیرفعال</p>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex items-center gap-1 mb-5 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 w-fit">
        {[
          { key: "dashboard" as const, label: "📊 داشبورد" },
          { key: "tables" as const, label: "🗃️ جداول داده" },
          { key: "jobs" as const, label: "⏱️ Jobهای زمان‌بندی" },
        ].map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
              activeTab === tab.key
                ? "bg-primary-600/30 text-primary-300 shadow-sm"
                : "text-surface-400 hover:text-surface-200"
            }`}>
            {tab.label}
          </button>
        )        )}
      </div>

      {/* Backfill progress cards — visible on ALL tabs */}
      {candleBackfill.backfill.status !== "idle" && (
        <div className="mb-5">
          <BackfillProgressCard
            title="بکفیل کندل بازار"
            icon="🕯️"
            unitLabel="کندل دریافت‌شده"
            backfill={candleBackfill.backfill}
            onCancel={handleCancelCandleBackfill}
          />
        </div>
      )}
      {shareholderBackfill.backfill.status !== "idle" && (
        <div className="mb-5">
          <BackfillProgressCard
            title="بکفیل سهامداران بازار"
            icon="🏛️"
            unitLabel="رکورد سهامدار"
            backfill={shareholderBackfill.backfill}
            onCancel={handleCancelShareholderBackfill}
          />
        </div>
      )}
      {historyPriceBackfill.backfill.status !== "idle" && (
        <div className="mb-5">
          <BackfillProgressCard
            title="بکفیل تاریخچه قیمت بازار"
            icon="📜"
            unitLabel="رکورد قیمت تاریخی"
            backfill={historyPriceBackfill.backfill}
            onCancel={handleCancelHistoryPriceBackfill}
          />
        </div>
      )}
      {historyRealLegalBackfill.backfill.status !== "idle" && (
        <div className="mb-5">
          <BackfillProgressCard
            title="بکفیل حقیقی/حقوقی بازار"
            icon="👥"
            unitLabel="رکورد حقیقی/حقوقی"
            backfill={historyRealLegalBackfill.backfill}
            onCancel={handleCancelHistoryRealLegalBackfill}
          />
        </div>
      )}

      {/* ════════════════════════════════════════════════ */}
      {/* TAB 1: DASHBOARD                                */}
      {/* ════════════════════════════════════════════════ */}
      {activeTab === "dashboard" && (
        <div className="space-y-5">
          {/* Freshness chart */}
          <Card title={"📈 تاریخچه Freshness (" + timeRangeLabel + ")"} actions={
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
            {chartData.length === 0 ? (
              <div className="flex items-center justify-center h-[180px] text-surface-500 text-sm">داده‌ای برای نمایش وجود ندارد</div>
            ) : (
              <>
                <AreaChartCard
                  title=""
                  data={chartData.map(d => ({ date: d.time.slice(11, 16), time: d.time.slice(11, 16), value: d.success, error: d.error }))}
                  dataKey="success"
                  height={260}
                  yAxisFormatter={(v) => `${v}`}
                  strokeColor="#10b981"
                  gradientId="freshnessGradient"
                  showAverage
                  showMinMax
                  crosshair
                  animate
                  primaryLabel="موفق"
                  yAxisLabel="تعداد عملیات"
                  additionalSeries={[{
                    dataKey: "error",
                    strokeColor: "#FF5252",
                    gradientId: "errorGradient",
                    label: "خطا",
                    asBar: true,
                    barFill: "#ef4444",
                  }]}
                />
                {/* Chart legend */}
                <div className="flex items-center justify-center gap-4 mt-2 text-[10px] text-surface-500">
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: "#10b981" }} />
                    سبز = موفق
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: "#ef4444" }} />
                    قرمز = خطا
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-6 h-0.5 rounded-full" style={{ backgroundColor: "rgba(251, 191, 36, 0.5)", borderTop: "2px dashed rgba(251, 191, 36, 0.5)" }} />
                    خط چین = میانگین
                  </span>
                </div>
              </>
            )}
          </Card>

          {/* Quick actions */}
          <Card title="⚡ اقدامات سریع">
            <div className="flex flex-wrap gap-2">
              <button onClick={() => handleRunJob("brsapi_all_symbols")}
                className="px-4 py-2 bg-primary-600/10 border border-primary-600/20 rounded-xl text-xs font-bold text-primary-400 hover:bg-primary-600/20 transition-all">
                🔄 Sync همه نمادها
              </button>
              <button onClick={() => handleRunJob("brsapi_gold_currency")}
                className="px-4 py-2 bg-accent-amber/10 border border-accent-amber/20 rounded-xl text-xs font-bold text-accent-amber hover:bg-accent-amber/20 transition-all">
                🥇 Sync طلا و ارز
              </button>
              <button onClick={() => handleRunJob("brsapi_commodities")}
                className="px-4 py-2 bg-accent-emerald/10 border border-accent-emerald/20 rounded-xl text-xs font-bold text-accent-emerald hover:bg-accent-emerald/20 transition-all">
                🌍 Sync کامودیتی‌ها
              </button>
              <button onClick={() => handleRunJob("brsapi_codal")}
                className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-400 hover:text-surface-200 transition-all">
                🏢 Sync کدال
              </button>
            </div>

            {/* Manual full-market backfills + API key test */}
            <div className="w-full border-t border-surface-800/60 pt-3 mt-3">
              <p className="text-[10px] font-bold text-surface-500 mb-2">⬇️ دانلود کامل بازار — کندل، سهامداران و تاریخچه</p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleStartCandleBackfill}
                  disabled={candleBackfill.backfill.status === "running"}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                    candleBackfill.backfill.status === "running"
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 animate-pulse"
                      : "bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/25 hover:border-indigo-500/50"
                  }`}>
                  <span className="material-icons text-sm align-middle ml-1">{candleBackfill.backfill.status === "running" ? "hourglass_top" : "download"}</span>
                  {candleBackfill.backfill.status === "running" ? "در حال دانلود..." : "دانلود کندل همه نمادها (هر ۳ نوع)"}
                </button>
                <button
                  onClick={handleStartShareholderBackfill}
                  disabled={shareholderBackfill.backfill.status === "running"}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                    shareholderBackfill.backfill.status === "running"
                      ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 animate-pulse"
                      : "bg-emerald-600/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-600/25 hover:border-emerald-500/50"
                  }`}>
                  <span className="material-icons text-sm align-middle ml-1">{shareholderBackfill.backfill.status === "running" ? "hourglass_top" : "download"}</span>
                  {shareholderBackfill.backfill.status === "running" ? "در حال دانلود..." : "دانلود سهامداران همه نمادها"}
                </button>
                <button
                  onClick={handleStartHistoryPriceBackfill}
                  disabled={historyPriceBackfill.backfill.status === "running"}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                    historyPriceBackfill.backfill.status === "running"
                      ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 animate-pulse"
                      : "bg-cyan-600/15 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-600/25 hover:border-cyan-500/50"
                  }`}>
                  <span className="material-icons text-sm align-middle ml-1">{historyPriceBackfill.backfill.status === "running" ? "hourglass_top" : "download"}</span>
                  {historyPriceBackfill.backfill.status === "running" ? "در حال دانلود..." : "دانلود تاریخچه قیمت همه نمادها"}
                </button>
                <button
                  onClick={handleStartHistoryRealLegalBackfill}
                  disabled={historyRealLegalBackfill.backfill.status === "running"}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                    historyRealLegalBackfill.backfill.status === "running"
                      ? "bg-amber-600/20 text-amber-300 border border-amber-500/40 animate-pulse"
                      : "bg-amber-600/15 text-amber-300 border border-amber-500/30 hover:bg-amber-600/25 hover:border-amber-500/50"
                  }`}>
                  <span className="material-icons text-sm align-middle ml-1">{historyRealLegalBackfill.backfill.status === "running" ? "hourglass_top" : "download"}</span>
                  {historyRealLegalBackfill.backfill.status === "running" ? "در حال دانلود..." : "دانلود حقیقی/حقوقی همه نمادها"}
                </button>
                <button
                  onClick={handleTestConnection}
                  disabled={isTestingConn}
                  className="px-4 py-2 bg-accent-emerald/10 border border-accent-emerald/25 rounded-xl text-xs font-bold text-accent-emerald hover:bg-accent-emerald/20 disabled:opacity-50 transition-all">
                  {isTestingConn ? "⏳ در حال تست..." : "🔑 تست کلید و اتصال API"}
                </button>
              </div>
              <p className="text-[9px] text-surface-600 mt-2 leading-relaxed">
                دانلود کامل با محدودیت رسمی API (۲ درخواست/۱۰ ثانیه) برای کل بازار چند ساعت طول می‌کشد — پیشرفت هر دانلود در همین صفحه نمایش داده می‌شود و می‌توانید آن را متوقف کنید.
              </p>

              {/* Daily full-market job controls — shared JobControlRow */}
              <JobControlRow
                icon="⏱️"
                label="جاب روزانه کندل"
                jobName="brsapi_candlesticks_all"
                job={candleJob}
                running={candleBackfill.backfill.status === "running"}
                onRun={handleRunJob}
                onToggle={handleToggleJob}
                scheduleLabel="اجرای روزانه ۱۳:۰۰"
                className="mt-3"
              />
              <JobControlRow
                icon="🏛️"
                label="جاب روزانه سهامداران"
                jobName="brsapi_shareholders_all"
                job={shareholderJob}
                running={shareholderBackfill.backfill.status === "running"}
                onRun={handleRunJob}
                onToggle={handleToggleJob}
                scheduleLabel="اجرای روزانه ۱۳:۳۰"
                className="mt-2"
              />
              <JobControlRow
                icon="📜"
                label="جاب روزانه تاریخچه قیمت"
                jobName="brsapi_history_price_all"
                job={historyPriceJob}
                running={historyPriceBackfill.backfill.status === "running"}
                onRun={handleRunJob}
                onToggle={handleToggleJob}
                scheduleLabel="اجرای روزانه ۱۴:۰۰"
                className="mt-2"
              />
              <JobControlRow
                icon="👥"
                label="جاب روزانه حقیقی/حقوقی"
                jobName="brsapi_history_real_legal_all"
                job={historyRealLegalJob}
                running={historyRealLegalBackfill.backfill.status === "running"}
                onRun={handleRunJob}
                onToggle={handleToggleJob}
                scheduleLabel="اجرای روزانه ۱۴:۳۰"
                className="mt-2"
              />

              {/* Connection test result */}
              {connTest && (
                <div className={`mt-3 rounded-xl border p-3 text-[11px] ${connTest.reachable ? "bg-accent-emerald/10 border-accent-emerald/25" : "bg-accent-rose/10 border-accent-rose/25"}`}>
                  <div className="flex items-center gap-2 font-bold">
                    <span className={`w-2 h-2 rounded-full ${connTest.reachable ? "bg-accent-emerald" : "bg-accent-rose"}`} />
                    {connTest.reachable ? "اتصال برقرار است" : "اتصال برقرار نیست"}
                  </div>
                  <div className="mt-1.5 space-y-1 text-surface-400">
                    <p>🔑 کلید: <span className="font-mono text-surface-200" dir="ltr">{connTest.key || "—"}</span>
                      <span className={`mr-1 ${connTest.configured ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {connTest.configured ? "(پیکربندی شده)" : "(تنظیم نشده)"}
                      </span>
                    </p>
                    {connTest.http_status != null && (
                      <p>کد وضعیت: <span className="font-mono text-surface-200">{connTest.http_status}</span></p>
                    )}
                    {connTest.elapsed_ms != null && (
                      <p>زمان پاسخ: <span className="font-mono text-surface-200">{connTest.elapsed_ms.toFixed(0)}ms</span></p>
                    )}
                    {connTest.symbols_count != null && (
                      <p>نمادهای دریافتی: <span className="font-mono text-surface-200">{formatNumber(connTest.symbols_count)}</span></p>
                    )}
                    <p className="text-surface-300">{connTest.message}</p>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Recent events */}
          <Card title="🔄 آخرین رویدادهای Sync" actions={
            <span className="text-[10px] text-surface-600">{recentEvents.length} رویداد</span>
          }>
            {recentEvents.length === 0 ? (
              <p className="text-surface-500 text-sm text-center py-6">رویدادی ثبت نشده</p>
            ) : (
              <div className="space-y-1 max-h-[300px] overflow-y-auto">
                {recentEvents.map((ev, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-surface-800/20 transition-colors">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${ev.status === "success" ? "bg-accent-emerald" : "bg-accent-rose"}`} />
                      <span className="text-[10px] text-surface-400 font-mono truncate max-w-[180px]">{ev.endpoint}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 text-[9px]">
                      <span className="text-surface-600">{ev.items_count} آیتم</span>
                      <span className="text-surface-600">{formatDuration(ev.duration_ms)}</span>
                      <span className="text-surface-500">{formatRelativeTime(ev.time)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ════════════════════════════════════════════════ */}
      {/* TAB 2: TABLES (Data Freshness)                 */}
      {/* ════════════════════════════════════════════════ */}
      {activeTab === "tables" && (
        <>
          {/* Sync All button */}
          <div className="flex items-center justify-between mb-3">
            <div />
            <button
              onClick={handleSyncAll}
              disabled={isSyncingAll}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                isSyncingAll
                  ? "bg-primary-600/20 text-primary-300 cursor-wait animate-pulse"
                  : "bg-primary-600/15 text-primary-400 border border-primary-600/30 hover:bg-primary-600/25 hover:border-primary-500/50"
              }`}
            >
              <span className={`material-icons text-sm ${isSyncingAll ? "animate-spin" : ""}`}>
                {isSyncingAll ? "sync" : "sync"}
              </span>
              {isSyncingAll ? "در حال sync همه بخش‌ها..." : "🔄 Sync All — همه بخش‌ها"}
            </button>
          </div>

        <Card title="🗃️ وضعیت جداول داده" actions={
          <div className="flex items-center gap-2 text-[10px]">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> به‌روز</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> کمی قدیمی</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-rose" /> قدیمی</span>
          </div>
        }>
          {statusLoading ? (
            <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}</div>
          ) : entries.length === 0 ? (
            <p className="text-surface-500 text-sm text-center py-8">هیچ داده‌ای یافت نشد</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-3 px-3">بخش</th>
                    <th className="pb-3 px-3 text-center">وضعیت</th>
                    <th className="pb-3 px-3 text-center">رکوردها</th>
                    <th className="pb-3 px-3 text-center">آخرین بروزرسانی</th>
                    <th className="pb-3 px-3 text-center">سن</th>
                    <th className="pb-3 px-3 text-center">مهلت</th>
                    <th className="pb-3 px-3 text-center">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(([key, info]) => {
                    const cfg = TABLE_CONFIG[key] || { label: key, icon: "📦", order: 99 };
                    const meta = STATUS_META[info.status] || STATUS_META.unknown;
                    return (
                      <tr key={key} className="border-b border-surface-800/30 hover:bg-surface-800/20 transition-colors">
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className="text-base">{cfg.icon}</span>
                            <span className="font-semibold text-surface-200">{cfg.label}</span>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${meta.bg} ${meta.color}`}>
                            <StatusDot status={info.status} size="sm" />
                            {meta.label}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center font-mono text-surface-300">{formatNumber(info.record_count)}</td>
                        <td className="py-3 px-3 text-center text-surface-400">
                          {info.last_fetched ? <span title={info.last_fetched}>{formatTime(info.last_fetched)}</span> : "—"}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className={`font-mono ${info.status === "ok" ? "text-accent-emerald" : info.status === "stale" ? "text-accent-amber" : info.status === "outdated" ? "text-accent-rose" : "text-surface-500"}`}>
                            {info.age_minutes != null ? `${info.age_minutes.toFixed(0)} دقیقه` : "—"}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center text-surface-500 font-mono">{info.max_age_minutes} دقیقه</td>
                        <td className="py-3 px-3 text-center">
                          <button onClick={() => handleSyncNow(key)}
                            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
                              info.status === "outdated"
                                ? "bg-accent-rose/15 text-accent-rose border-accent-rose/30 hover:bg-accent-rose/25 animate-pulse shadow-[0_0_8px_rgba(244,63,94,0.25)]"
                                : info.status === "stale"
                                  ? "bg-accent-amber/15 text-accent-amber border-accent-amber/30 hover:bg-accent-amber/25"
                                  : "bg-surface-800 text-surface-400 hover:bg-primary-600/20 hover:text-primary-300 border-surface-700 hover:border-primary-500/30"
                            }`}>
                            <span className="material-icons text-sm">sync</span>
                            {info.status === "outdated" ? "⚠️ Sync" : info.status === "stale" ? "🟡 Sync" : "Sync Now"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        </>
      )}

      {/* ════════════════════════════════════════════════ */}
      {/* TAB 3: JOBS (Scheduler)                        */}
      {/* ════════════════════════════════════════════════ */}
      {activeTab === "jobs" && (
        <>
          {/* ⭐ Quick access — highlighted daily candlestick job control */}
          <JobControlRow
            icon="🕯️"
            label="جاب روزانه کندل"
            jobName="brsapi_candlesticks_all"
            job={candleJob}
            running={candleBackfill.backfill.status === "running"}
            onRun={handleRunJob}
            onToggle={handleToggleJob}
            scheduleLabel="اجرای روزانه ۱۳:۰۰"
            description="اجرای روزانه بعد از بستن بازار — همه نمادها، هر ۳ نوع کندل"
            highlight
          >
            {/* Live progress when the background backfill is running */}
            {candleBackfill.backfill.status === "running" && (
              <div className="w-full mt-3">
                <div className="flex items-center justify-between text-[9px] text-surface-500 mb-1">
                  <span className="font-mono text-indigo-300/90">{candleBackfill.backfill.current_symbol || "در حال آماده‌سازی..."}</span>
                  <span>
                    {candleBackfill.backfill.processed}/{candleBackfill.backfill.total_symbols || "?"} نماد ·
                    موفق {candleBackfill.backfill.ok} · خطا {candleBackfill.backfill.fail} · {(candleBackfill.backfill.items ?? 0).toLocaleString("fa-IR")} کندل
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-surface-700/60 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-l from-indigo-400 to-primary-500 transition-all duration-500"
                    style={{
                      width: `${
                        candleBackfill.backfill.total_symbols > 0
                          ? Math.min(100, Math.round((candleBackfill.backfill.processed / candleBackfill.backfill.total_symbols) * 100))
                          : 4
                      }%`,
                    }}
                  />
                </div>
                {candleBackfill.backfill.message && (
                  <p className="text-[9px] text-surface-500 mt-1.5 leading-relaxed">{candleBackfill.backfill.message}</p>
                )}
              </div>
            )}
            {candleBackfill.backfill.status !== "idle" && candleBackfill.backfill.status !== "running" && candleBackfill.backfill.message && (
              <p className="text-[9px] text-surface-500 mt-2">{candleBackfill.backfill.message}</p>
            )}
          </JobControlRow>

        <Card title="⏱️ Jobهای زمان‌بندی" actions={
          <span className="text-[10px] text-surface-600">{enabledJobs} فعال / {disabledJobs} غیرفعال</span>
        }>
          {schedulerLoading ? (
            <div className="space-y-3">{[1,2,3,4].map(i => <Skeleton key={i} className="h-14 w-full rounded-lg" />)}</div>
          ) : schedulerJobs.length === 0 ? (
            <p className="text-surface-500 text-sm text-center py-8">هیچ jobی ثبت نشده</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-3 px-3">وضعیت</th>
                    <th className="pb-3 px-3">نام</th>
                    <th className="pb-3 px-3">دسته</th>
                    <th className="pb-3 px-3">برنامه</th>
                    <th className="pb-3 px-3 text-center">اجرای بعدی</th>
                    <th className="pb-3 px-3 text-center">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {schedulerJobs
                    .sort((a, b) => {
                      // Pin the special full-market backfill jobs to the top so
                      // they stay visible without scrolling.
                      const sa = SPECIAL_BACKFILL_JOBS.includes(a.name) ? 1 : 0;
                      const sb = SPECIAL_BACKFILL_JOBS.includes(b.name) ? 1 : 0;
                      if (sa !== sb) return sb - sa;
                      if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
                      return a.name.localeCompare(b.name);
                    })
                    .map(job => {
                      const ci = CATEGORY_CONFIG[job.category] || { label: job.category, icon: "📦" };
                      return (
                        <tr key={job.name} className={`border-b transition-colors ${
                          SPECIAL_BACKFILL_JOBS.includes(job.name)
                            ? "border-indigo-500/25 bg-indigo-600/[0.06] hover:bg-indigo-600/[0.12]"
                            : "border-surface-800/30 hover:bg-surface-800/20"
                        } ${job.enabled ? "" : "opacity-60"}`}>
                          <td className="py-3 px-3">
                            <span className={`w-2.5 h-2.5 rounded-full inline-block shrink-0 ${job.enabled ? "bg-accent-emerald shadow-[0_0_6px_rgba(52,211,153,0.4)]" : "bg-surface-600"}`} />
                          </td>
                          <td className="py-3 px-3 max-w-[220px]">
                            <div className="flex flex-col gap-0.5">
                              <span className="flex items-center gap-1.5">
                                <span className="font-semibold text-surface-200 font-mono text-[11px]">{job.name}</span>
                                {SPECIAL_BACKFILL_JOBS.includes(job.name) && (
                                  <span className="px-1.5 py-0.5 rounded-md bg-indigo-500/15 text-indigo-300 border border-indigo-500/25 text-[8px] font-bold leading-none">⭐ ویژه</span>
                                )}
                              </span>
                              <span className="text-[9px] text-surface-500 leading-tight line-clamp-1">{job.description}</span>
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-surface-800 text-surface-400 text-[10px]">
                              {ci.icon}{ci.label}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className="font-mono text-surface-300 text-[10px]">{formatCron(job.cron)}</span>
                          </td>
                          <td className="py-3 px-3 text-center">
                            {job.enabled && job.next_run_time ? (
                              <span className="text-[10px] text-surface-400">{formatTime(job.next_run_time)}</span>
                            ) : <span className="text-surface-600">—</span>}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center justify-center gap-1.5">
                              <button onClick={() => handleRunJob(job.name)}
                                className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-medium bg-primary-600/10 text-primary-400 border border-primary-600/20 hover:bg-primary-600/20 transition-all"
                                title="اجرای فوری">
                                <span className="material-icons text-sm">play_arrow</span>
                              </button>
                              <button onClick={() => handleToggleJob(job.name)}
                                className={`inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
                                  job.enabled
                                    ? "bg-accent-rose/10 text-accent-rose border-accent-rose/20 hover:bg-accent-rose/20"
                                    : "bg-accent-emerald/10 text-accent-emerald border-accent-emerald/20 hover:bg-accent-emerald/20"
                                }`}
                                title={job.enabled ? "غیرفعال" : "فعال"}>
                                <span className="material-icons text-sm">{job.enabled ? "pause_circle" : "play_circle"}</span>
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
        </>
      )}
    </AppLayout>
  );
}
