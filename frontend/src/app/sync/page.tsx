"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import { applyCustomThresholds } from "@/lib/sync-settings";
import { useSyncSettings } from "@/hooks/useSyncSettings";

// ── Dynamic chart (prevent SSR issues with Recharts) ──
const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-surface-800/50 rounded-2xl" style={{ height: 260 }} />,
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

interface SyncResult {
  success: boolean;
  items_count: number;
  duration_ms: number;
  error?: string;
}

// ── Config ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

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
    const diffDays = Math.floor(diffHr / 24);
    return `${diffDays} روز پیش`;
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

function formatNumber(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

// ── Status Dot ─────────────────────────────────────────────────────────────────────────────────────────────────────────

function StatusDot({ status, size = "md" }: { status: string; size?: "sm" | "md" }) {
  const cs = STATUS_META[status];
  const sz = size === "sm" ? "w-1.5 h-1.5" : "w-3 h-3";
  return <span className={`${sz} rounded-full shrink-0 ${cs?.bg || "bg-surface-600"}`} />;
}

// ── Toast ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: "success" | "error"; onClose: () => void }) {
  const ref = useRef(onClose);
  useEffect(() => {
    ref.current = onClose;
  }, [onClose]);
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

export default function SyncStatusPage() {
  const queryClient = useQueryClient();
  const [syncingKeys, setSyncingKeys] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [timeRange, setTimeRange] = useState<string>("48h");
  const [isSyncingAll, setIsSyncingAll] = useState(false);

  // ── Load custom freshness thresholds (SSR-safe) ──
  const [customSettings, setCustomSettings] = useSyncSettings();

  // ── Fetch sync status ──
  const { data: syncStatus, isLoading: statusLoading, isError: statusError } = useQuery({
    queryKey: ["brsapi-sync-status"],
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
  const { data: syncHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["brsapi-sync-history", timeRange],
    queryFn: async (): Promise<SyncLogEntry[]> => {
      const res = await apiGet<{ success: boolean; data: SyncLogEntry[] }>(`/brsapi/sync-history?hours=${timeRangeHours}&limit=300`);
      return res?.data ?? [];
    },
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  // ── Handle Sync All ──
  const handleSyncAll = useCallback(async () => {
    setIsSyncingAll(true);
    setToast({ message: "🔄 شروع sync همه بخش‌ها...", type: "success" });
    const sectionKeys = Object.keys(SECTION_ID_MAP);
    let successCount = 0;
    let failCount = 0;
    for (let i = 0; i < sectionKeys.length; i++) {
      const key = sectionKeys[i];
      const sectionId = SECTION_ID_MAP[key];
      try {
        const res = await apiPost<{ success: boolean; data: SyncResult }>(`/brsapi/manage/sync/${sectionId}`);
        if (res?.success) successCount++;
        else failCount++;
      } catch {
        failCount++;
      }
      setToast({
        message: `🔄 sync بخش‌ها: ${i + 1}/${sectionKeys.length} (✅ ${successCount} موفق, ❌ ${failCount} خطا)`,
        type: failCount > 0 && successCount === 0 ? "error" : "success",
      });
    }
    queryClient.invalidateQueries({ queryKey: ["brsapi-sync-status"] });
    queryClient.invalidateQueries({ queryKey: ["brsapi-sync-history"] });
    setIsSyncingAll(false);
    if (failCount === 0) {
      setToast({ message: `✅ sync همه ${successCount} بخش با موفقیت انجام شد`, type: "success" });
    } else {
      setToast({ message: `⚠️ sync کامل شد: ${successCount} موفق، ${failCount} خطا`, type: "success" });
    }
  }, [queryClient]);

  // ── Handle Sync Now ──
  const handleSyncNow = useCallback(async (key: string) => {
    const sectionId = SECTION_ID_MAP[key];
    if (!sectionId) {
      setToast({ message: `بخش '${key}' پشتیبانی نمی‌شود`, type: "error" });
      return;
    }
    setSyncingKeys(p => ({ ...p, [key]: true }));
    try {
      const res = await apiPost<{ success: boolean; data: SyncResult }>(`/brsapi/manage/sync/${sectionId}`);
      if (res?.success && res.data?.success) {
        setToast({ message: `✅ ${TABLE_CONFIG[key]?.label || key}: ${res.data.items_count} رکورد در ${formatDuration(res.data.duration_ms)}`, type: "success" });
      } else {
        setToast({ message: `❌ ${TABLE_CONFIG[key]?.label || key}: ${res?.data?.error || "خطا"}`, type: "error" });
      }
    } catch (err) {
      setToast({ message: `❌ ${TABLE_CONFIG[key]?.label || key}: ${String(err)}`, type: "error" });
    } finally {
      setSyncingKeys(p => ({ ...p, [key]: false }));
      queryClient.invalidateQueries({ queryKey: ["brsapi-sync-status"] });
      queryClient.invalidateQueries({ queryKey: ["brsapi-sync-history"] });
    }
  }, [queryClient]);

  // ── Apply custom freshness thresholds ──
  const effectiveStatus = syncStatus ? applyCustomThresholds(syncStatus, customSettings) : undefined;

  // ── Process status entries ──
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
  const hasIssues = staleCount + outdatedCount + missingCount > 0;

  const healthScore = totalCount > 0 ? Math.round(((okCount) / totalCount) * 100) : 0;
  const healthColor = healthScore >= 80 ? "text-accent-emerald" : healthScore >= 50 ? "text-accent-amber" : "text-accent-rose";

  // ── Build freshness chart data ──
  const chartData = syncHistory
    ? (() => {
        // Aggregate by hour: count successes and errors per hour
        const buckets: Record<string, { time: string; success: number; error: number; items: number }> = {};
        for (const entry of syncHistory) {
          if (!entry.time) continue;
          const d = new Date(entry.time);
          const hourKey = d.toISOString().slice(0, 13) + ":00"; // "2026-07-18T14:00"
          if (!buckets[hourKey]) {
            buckets[hourKey] = { time: hourKey, success: 0, error: 0, items: 0 };
          }
          if (entry.status === "success") buckets[hourKey].success++;
          else buckets[hourKey].error++;
          buckets[hourKey].items += entry.items_count;
        }
        return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
      })()
    : [];

  // Recent sync events (last 20)
  const recentEvents = (syncHistory ?? []).slice(0, 20);

  return (
    <AppLayout title="📡 وضعیت همگام‌سازی داده‌ها" subtitle="بررسی freshness و سلامت داده‌های BrsApi">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── Health Summary Cards ── */}
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
          <p className={`text-2xl font-black ${outdatedCount > 0 ? "text-accent-rose" : "text-surface-600"}`}>{outdatedCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">قدیمی</p>
        </div>
        <div className="glass-card p-3.5 text-center">
          <p className={`text-2xl font-black ${missingCount > 0 ? "text-surface-400" : "text-surface-600"}`}>{missingCount}</p>
          <p className="text-[10px] text-surface-500 mt-0.5">خالی</p>
        </div>
      </div>

      {/* ── Quick Actions Card ── */}
      <div className="mb-5">
        <Card title="⚡ اقدامات سریع">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleSyncAll}
              disabled={isSyncingAll}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                isSyncingAll
                  ? "bg-primary-600/20 text-primary-300 cursor-wait animate-pulse"
                  : "bg-primary-600/15 text-primary-400 border border-primary-600/30 hover:bg-primary-600/25 hover:border-primary-500/50 shadow-sm shadow-primary-600/10"
              }`}
            >
              <span className={`material-icons text-sm ${isSyncingAll ? "animate-spin" : ""}`}>
                {isSyncingAll ? "sync" : "sync"}
              </span>
              {isSyncingAll ? "در حال sync همه بخش‌ها..." : "🔄 Sync All — همه بخش‌ها"}
            </button>
            <button onClick={() => handleSyncNow("symbols")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-primary-600/10 border border-primary-600/20 text-primary-400 hover:bg-primary-600/20 transition-all">
              🔄 نمادها
            </button>
            <button onClick={() => handleSyncNow("gold_coin")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-accent-amber/10 border border-accent-amber/20 text-accent-amber hover:bg-accent-amber/20 transition-all">
              🥇 طلا و سکه
            </button>
            <button onClick={() => handleSyncNow("currency")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-accent-emerald/10 border border-accent-emerald/20 text-accent-emerald hover:bg-accent-emerald/20 transition-all">
              💵 ارز
            </button>
            <button onClick={() => handleSyncNow("crypto")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-surface-800 border border-surface-700 text-surface-400 hover:text-surface-200 hover:border-surface-600 transition-all">
              ₿ کریپتو
            </button>
            <button onClick={() => handleSyncNow("codal")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-surface-800 border border-surface-700 text-surface-400 hover:text-surface-200 hover:border-surface-600 transition-all">
              🏢 کدال
            </button>
          </div>
        </Card>
      </div>

      {/* ── Freshness History Chart ── */}
      <div className="mb-5">
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
          {historyLoading ? (
            <Skeleton className="h-[260px] w-full rounded-xl" />
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-[200px] text-surface-500 text-sm">
              داده‌ای برای نمایش وجود ندارد
            </div>
          ) : (
            <>
              <AreaChartCard
                title=""
                data={chartData.map(d => ({
                  date: d.time.slice(11, 16),
                  time: d.time.slice(11, 16),
                  value: d.success,
                  error: d.error || 0,
                  items: d.items || 0,
                }))}
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
                yAxisLabel="تعداد"
                additionalSeries={[{
                  dataKey: "error",
                  strokeColor: "#FF5252",
                  gradientId: "syncErrorGradient",
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
                  <span className="w-6 border-t-2 border-dashed" style={{ borderColor: "rgba(251, 191, 36, 0.5)" }} />
                  خط چین = میانگین
                </span>
              </div>
            </>
          )}
        </Card>
      </div>

      {/* ── Per-Section Status Table ── */}
      <div className="flex items-center justify-end mb-3">
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
      <Card title="📋 وضعیت بخش‌ها" actions={
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> به‌روز</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> کمی قدیمی</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-rose" /> قدیمی</span>
        </div>
      }>
        {statusLoading ? (
          <div className="space-y-3">{[1, 2, 3].map(i => <Skeleton key={i} className="h-14 w-full rounded-lg" />)}</div>
        ) : statusError ? (
          <p className="text-accent-rose text-sm text-center py-8">خطا در دریافت وضعیت</p>
        ) : entries.length === 0 ? (
          <p className="text-surface-500 text-sm text-center py-8">هیچ داده‌ای یافت نشد. اسکریپت‌های sync را اجرا کنید.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-3 px-3">بخش</th>
                  <th className="pb-3 px-3 text-center">وضعیت</th>
                  <th className="pb-3 px-3 text-center">رکوردها</th>
                  <th className="pb-3 px-3 text-center">آخرین بروزرسانی</th>
                  <th className="pb-3 px-3 text-center">سن داده</th>
                  <th className="pb-3 px-3 text-center">حداکثر مجاز</th>
                  <th className="pb-3 px-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(([key, info]) => {
                  const cfg = TABLE_CONFIG[key] || { label: key, icon: "📦", order: 99 };
                  const meta = STATUS_META[info.status] || STATUS_META.unknown;
                  const isSyncing = syncingKeys[key] ?? false;

                  return (
                    <tr key={key} className={`border-b border-surface-800/30 transition-colors ${isSyncing ? "bg-primary-600/5" : "hover:bg-surface-800/20"}`}>
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
                      <td className="py-3 px-3 text-center font-mono text-surface-300">
                        {formatNumber(info.record_count)}
                      </td>
                      <td className="py-3 px-3 text-center text-surface-400">
                        {info.last_fetched ? (
                          <span title={info.last_fetched}>{formatTime(info.last_fetched)}</span>
                        ) : "—"}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={`font-mono ${
                          info.status === "ok" ? "text-accent-emerald" :
                          info.status === "stale" ? "text-accent-amber" :
                          info.status === "outdated" ? "text-accent-rose" :
                          "text-surface-500"
                        }`}>
                          {info.age_minutes != null ? `${info.age_minutes.toFixed(0)} دقیقه` : "—"}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center text-surface-500 font-mono">
                        {info.max_age_minutes} دقیقه
                      </td>
                      <td className="py-3 px-3 text-center">
                        <button onClick={() => handleSyncNow(key)}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
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

      {/* ── Recent Sync Events ── */}
      <div className="mt-5">
        <Card title="🔄 آخرین رویدادهای Sync (۴۸ ساعت)" actions={
          <span className="text-[10px] text-surface-600">{recentEvents.length} رویداد</span>
        }>
          {historyLoading ? (
            <Skeleton className="h-40 w-full rounded-xl" />
          ) : recentEvents.length === 0 ? (
            <p className="text-surface-500 text-sm text-center py-8">رویدادی ثبت نشده</p>
          ) : (
            <div className="space-y-1 max-h-[400px] overflow-y-auto">
              {recentEvents.map((ev, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface-800/20 transition-colors">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${ev.status === "success" ? "bg-accent-emerald" : "bg-accent-rose"}`} />
                    <span className="text-xs text-surface-400 font-mono truncate max-w-[200px]">{ev.endpoint}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 text-[10px]">
                    <span className="text-surface-500">{ev.category}</span>
                    <span className={`font-bold ${ev.status === "success" ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {ev.status === "success" ? `${ev.items_count} آیتم` : "خطا"}
                    </span>
                    <span className="text-surface-600">{formatDuration(ev.duration_ms)}</span>
                    <span className="text-surface-500">{formatRelativeTime(ev.time)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </AppLayout>
  );
}
