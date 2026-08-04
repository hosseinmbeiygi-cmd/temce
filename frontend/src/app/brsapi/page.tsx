"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

// ------ Types -------------------------------------------------------------------------------------------------------

interface SyncInfo {
  status: string | null;
  items_count: number;
  duration_ms: number;
  completed_at: string | null;
  error_message: string | null;
}

interface SectionData {
  id: string;
  name: string;
  name_en: string;
  icon: string;
  category: string;
  has_date_range: boolean;
  record_count: number;
  last_data_date: string | null;
  last_sync: SyncInfo | null;
}

interface SyncResult {
  endpoint: string;
  section_id: string;
  success: boolean;
  items_count: number;
  duration_ms: number;
  skipped: number;
  error: string | null;
}

interface HealthData {
  status: string;
  commodity_prices: number;
  crypto_prices: number;
  symbol_snapshots: number;
  index_values: number;
  option_snapshots: number;
  ime_futures: number;
}

interface BatchSyncResult {
  total: number;
  success_count: number;
  fail_count: number;
  total_duration_ms: number;
  results: { symbol: string; success: boolean; items_count?: number; duration_ms?: number; error?: string }[];
}

// ------ Category Config ----------------------------------------------------------------------------------------------

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  tsetmc: { label: "TSETMC (بورس)", color: "bg-accent-emerald/15 text-accent-emerald" },
  ime: { label: "IME (بورس کالا)", color: "bg-accent-amber/15 text-accent-amber" },
  commodity: { label: "Commodity (کامودیتی)", color: "bg-accent-rose/15 text-accent-rose" },
  cryptocurrency: { label: "Cryptocurrency (ارز دیجیتال)", color: "bg-accent-violet/15 text-accent-violet" },
  codal: { label: "Codal (کدال)", color: "bg-primary-600/15 text-primary-300" },
};

const CATEGORY_ORDER = ["tsetmc", "ime", "commodity", "cryptocurrency", "codal"];

// ------ Helpers -----------------------------------------------------------------------------------------------------

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function formatDuration(ms: number): string {
  if (ms < 1000) return ms.toFixed(0) + "ms";
  if (ms < 60000) return (ms / 1000).toFixed(1) + "s";
  return (ms / 60000).toFixed(1) + "min";
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    return `${diffDays}d ago`;
  } catch {
    return dateStr.substring(0, 10);
  }
}

// ------ Components --------------------------------------------------------------------------------------------------

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-xs text-surface-500">never synced</span>;
  if (status === "success")
    return <span className="text-xs bg-accent-emerald/15 text-accent-emerald px-2 py-0.5 rounded-full">success</span>;
  if (status === "failed" || status === "error")
    return <span className="text-xs bg-accent-rose/15 text-accent-rose px-2 py-0.5 rounded-full">failed</span>;
  if (status === "running" || status === "in_progress")
    return <span className="text-xs bg-accent-amber/15 text-accent-amber px-2 py-0.5 rounded-full animate-pulse">running...</span>;
  return <span className="text-xs text-surface-500 px-2 py-0.5 rounded-full bg-surface-800">{status}</span>;
}

function SectionIcon({ icon }: { icon: string }) {
  return <span className="text-lg">{icon}</span>;
}

// ── History Data Section (Crypto/Gold/Currency from BrsApi) ──────────────

interface HistoryStatus {
  [key: string]: {
    table: string;
    rows: number;
    min_date: string | null;
    max_date: string | null;
    symbols: number;
    error?: string;
  };
}

function HistoryDataSection() {
  const [importing, setImporting] = useState(false);
  const [lastResult, setLastResult] = useState<{ total_inserted: number; files_imported: number; duration_s: number } | null>(null);

  const { data: historyStatus, refetch: refetchHistory } = useQuery<HistoryStatus>({
    queryKey: ["brsapi-history-status"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: HistoryStatus }>("/brsapi/manage/history-status");
      return res?.data ?? {};
    },
    refetchInterval: false,
  });

  const doImportJson = useCallback(async () => {
    setImporting(true);
    setLastResult(null);
    try {
      const res = await apiPost<{ success: boolean; data: { total_inserted: number; files_imported: number; duration_s: number } }>(
        "/brsapi/manage/import-json-history"
      );
      if (res?.success) {
        setLastResult(res.data);
        refetchHistory();
      }
    } catch (err) {
      console.error("Import error:", err);
    }
    setImporting(false);
  }, [refetchHistory]);

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-surface-100">📊 تاریخچه داده‌ها</h3>
        <button onClick={() => refetchHistory()} className="text-xs text-surface-500 hover:text-surface-200 flex items-center gap-1">
          <span className="material-icons text-sm">refresh</span> بروزرسانی
        </button>
      </div>

      {/* Status Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        {historyStatus && Object.entries(historyStatus).map(([label, info]) => (
          <div key={label} className="bg-surface-800/50 rounded-xl p-3">
            <div className="text-xs text-surface-500 mb-1">{label}</div>
            <div className="text-lg font-bold font-mono text-surface-100">{formatNumber(info.rows)}</div>
            <div className="text-[10px] text-surface-500 mt-1">
              {info.symbols} نماد • {info.min_date || "—"} → {info.max_date || "—"}
            </div>
          </div>
        ))}
      </div>

      {/* Instructions */}
      <div className="bg-surface-800/30 rounded-lg p-3 mb-3 text-xs text-surface-400 space-y-1">
        <div className="font-medium text-surface-300">مراحل دریافت داده تاریخچه:</div>
        <div>۱. اسکریپت دریافت را از ترمینال اجرا کنید: <code className="bg-surface-700 px-1 rounded text-accent-emerald">python scripts/fetch_all_history.py</code></div>
        <div>۲. دکمه زیر را بزنید تا فایل‌ها وارد دیتابیس شوند</div>
      </div>

      {/* Import Button */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={doImportJson}
          disabled={importing}
          className={`flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
            importing
              ? "bg-accent-emerald/20 text-accent-emerald animate-pulse"
              : "bg-accent-emerald hover:bg-accent-emerald/80 text-white"
          } disabled:opacity-50`}
        >
          <span className={`material-icons text-sm ${importing ? "animate-spin" : ""}`}>
            {importing ? "sync" : "download"}
          </span>
          {importing ? "در حال وارد کردن..." : "وارد کردن از JSON فایل‌ها"}
        </button>
      </div>

      {/* Last Result */}
      {lastResult && (
        <div className="mt-3 bg-accent-emerald/10 border border-accent-emerald/20 rounded-lg p-3 text-xs text-accent-emerald">
          ✅ {lastResult.files_imported} فایل • {formatNumber(lastResult.total_inserted)} ردیف وارد شد • {lastResult.duration_s}s
        </div>
      )}
    </div>
  );
}

function SyncButton({
  sectionId,
  label,
  disabled,
  syncing,
  onSync,
}: {
  sectionId: string;
  label?: string;
  disabled?: boolean;
  syncing?: boolean;
  onSync: (id: string) => void;
}) {
  return (
    <button
      onClick={() => onSync(sectionId)}
      disabled={disabled || syncing}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
        syncing
          ? "bg-accent-amber/20 text-accent-amber animate-pulse cursor-wait"
          : "bg-primary-600 hover:bg-primary-500 text-white"
      } disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      <span className={`material-icons text-sm ${syncing ? "animate-spin" : ""}`}>
        {syncing ? "sync" : "sync"}
      </span>
      {syncing ? "Syncing..." : label || "Sync"}
    </button>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------

export default function BrsapiManagementPage() {
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [batchSyncing, setBatchSyncing] = useState<Record<string, boolean>>({});
  const [syncingSections, setSyncingSections] = useState<Record<string, boolean>>({});

  const showNotification = useCallback((type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  }, []);

  // Fetch all sections
  const {
    data: sectionsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["brsapi-sections"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: SectionData[] }>("/brsapi/manage/sections");
      return res?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  // Fetch health
  const { data: healthData } = useQuery({
    queryKey: ["brsapi-health"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: HealthData }>("/brsapi/health");
      return res?.data ?? null;
    },
    refetchInterval: 30_000,
  });

  // Sync individual section
  const doSyncSection = useCallback(
    async (sectionId: string) => {
      setSyncingSections((prev) => ({ ...prev, [sectionId]: true }));
      try {
        const res = await apiPost<{ success: boolean; data: SyncResult }>(
          `/brsapi/manage/sync/${sectionId}`
        );
        if (res?.success) {
          showNotification("success", `Sync completed: ${res.data.items_count} items in ${formatDuration(res.data.duration_ms)}`);
        } else {
          showNotification("error", `Sync failed: ${(res as { error?: string })?.error || "Unknown error"}`);
        }
      } catch (err) {
        showNotification("error", `Sync error: ${err instanceof Error ? err.message : "Unknown"}`);
      }
      setSyncingSections((prev) => ({ ...prev, [sectionId]: false }));
      refetch();
    },
    [refetch, showNotification]
  );

  // Sync top symbols
  const doSyncTopSymbols = useCallback(
    async (limit: number = 10) => {
      setBatchSyncing((prev) => ({ ...prev, topSymbols: true }));
      try {
        const res = await apiPost<{ success: boolean; data: BatchSyncResult }>(
          `/brsapi/manage/sync-top-symbols?limit=${limit}`
        );
        if (res?.success) {
          showNotification(
            "success",
            `Top ${limit} symbols synced: ${res.data.success_count} OK, ${res.data.fail_count} failed in ${formatDuration(res.data.total_duration_ms)}`
          );
        } else {
          showNotification("error", (res as { error?: string })?.error || "Sync failed");
        }
      } catch (err) {
        showNotification("error", `Sync error: ${err instanceof Error ? err.message : "Unknown"}`);
      }
      setBatchSyncing((prev) => ({ ...prev, topSymbols: false }));
      refetch();
    },
    [refetch, showNotification]
  );

  // Sync all history
  const doSyncAllHistory = useCallback(
    async (limit: number = 0) => {
      setBatchSyncing((prev) => ({ ...prev, allHistory: true }));
      try {
        const res = await apiPost<{ success: boolean; data: BatchSyncResult }>(
          `/brsapi/manage/sync-all-history?limit=${limit}`
        );
        if (res?.success) {
          showNotification(
            "success",
            `History sync completed: ${res.data.success_count}/${res.data.total} OK, ${formatDuration(res.data.total_duration_ms)}`
          );
        } else {
          showNotification("error", (res as { error?: string })?.error || "Sync failed");
        }
      } catch (err) {
        showNotification("error", `Sync error: ${err instanceof Error ? err.message : "Unknown"}`);
      }
      setBatchSyncing((prev) => ({ ...prev, allHistory: false }));
      refetch();
    },
    [refetch, showNotification]
  );

  // Group sections by category
  const grouped = sectionsData?.reduce(
    (acc, section) => {
      const cat = section.category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(section);
      return acc;
    },
    {} as Record<string, SectionData[]>
  );

  // Calculate totals
  const totalRecords = sectionsData?.reduce((sum, s) => sum + s.record_count, 0) ?? 0;
  const totalSynced = sectionsData?.filter((s) => s.last_sync?.status === "success").length ?? 0;

  return (
    <AppLayout
      title="BrsApi Management Dashboard"
      subtitle={`${sectionsData?.length ?? 0} data sections • ${formatNumber(totalRecords)} total records • ${totalSynced} synced`}
    >
      <div className="max-w-7xl mx-auto space-y-5">
        {/* Notification toast */}
        {notification && (
          <div
            className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium transition-all ${
              notification.type === "success"
                ? "bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30"
                : "bg-accent-rose/20 text-accent-rose border border-accent-rose/30"
            }`}
          >
            <span className="material-icons text-sm ml-1 align-text-bottom">
              {notification.type === "success" ? "check_circle" : "error"}
            </span>
            {notification.message}
          </div>
        )}

        {/* Health Status */}
        {healthData && (
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-surface-100">
                🔌 Connection Status
              </h3>
              <span
                className={`text-xs font-bold px-2 py-1 rounded-full ${
                  healthData.status === "connected"
                    ? "bg-accent-emerald/15 text-accent-emerald"
                    : "bg-accent-rose/15 text-accent-rose"
                }`}
              >
                {healthData.status === "connected" ? "● Connected" : "● Disconnected"}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-center">
              {[
                { label: "Symbol Snapshots", value: healthData.symbol_snapshots, icon: "📊" },
                { label: "Index Values", value: healthData.index_values, icon: "📈" },
                { label: "Commodity Prices", value: healthData.commodity_prices, icon: "🌍" },
                { label: "Crypto Prices", value: healthData.crypto_prices, icon: "₿" },
                { label: "Option Snapshots", value: healthData.option_snapshots, icon: "🎯" },
                { label: "IME Futures", value: healthData.ime_futures, icon: "🛢️" },
              ].map((item, ii) => (
                <div key={`${item.label}-${ii}`} className="bg-surface-800/50 rounded-xl p-2.5">
                  <span className="text-xs text-surface-500 block">{item.icon} {item.label}</span>
                  <span className="text-lg font-bold font-mono text-surface-100">{formatNumber(item.value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Batch Actions */}
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-surface-100">⚡ Batch Operations</h3>
            <button
              onClick={() => refetch()}
              className="text-xs text-surface-500 hover:text-surface-200 transition-colors flex items-center gap-1"
            >
              <span className="material-icons text-sm">refresh</span>
              Refresh
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => doSyncTopSymbols(10)}
              disabled={batchSyncing.topSymbols}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                batchSyncing.topSymbols
                  ? "bg-accent-amber/20 text-accent-amber animate-pulse"
                  : "bg-surface-700 hover:bg-surface-600 text-surface-200"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <span className={`material-icons text-sm ${batchSyncing.topSymbols ? "animate-spin" : ""}`}>
                {batchSyncing.topSymbols ? "sync" : "sync"}
              </span>
              {batchSyncing.topSymbols ? "Syncing..." : "Sync Top 10 Symbols (Detail)"}
            </button>

            <button
              onClick={() => doSyncAllHistory(0)}
              disabled={batchSyncing.allHistory}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                batchSyncing.allHistory
                  ? "bg-accent-amber/20 text-accent-amber animate-pulse"
                  : "bg-surface-700 hover:bg-surface-600 text-surface-200"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <span className={`material-icons text-sm ${batchSyncing.allHistory ? "animate-spin" : ""}`}>
                {batchSyncing.allHistory ? "sync" : "sync"}
              </span>
              {batchSyncing.allHistory ? "Syncing..." : "Sync ALL History Prices"}
            </button>

            <button
              onClick={() => doSyncTopSymbols(50)}
              disabled={batchSyncing.topSymbols}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-surface-700 hover:bg-surface-600 text-surface-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-icons text-sm">sync</span>
              Sync Top 50 Symbols
            </button>

            <Link
              href="/brsapi/codal"
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-primary-600/20 text-primary-300 hover:bg-primary-600/30 transition-all"
            >
              <span className="material-icons text-sm">description</span>
              Codal Announcements
            </Link>

            <Link
              href="/brsapi/history/%D9%81%D9%88%D9%84%D8%A7%D8%AF"
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-surface-700 hover:bg-surface-600 text-surface-200 transition-all"
            >
              <span className="material-icons text-sm">history</span>
              View Sample History
            </Link>
          </div>
        </div>

        {/* History Data Status & Sync */}
        <HistoryDataSection />

        {/* Category Filters */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveCategory(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeCategory === null
                ? "bg-primary-600 text-white shadow-lg"
                : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            All ({sectionsData?.length ?? 0})
          </button>
          {CATEGORY_ORDER.map((cat) => {
            const count = grouped?.[cat]?.length ?? 0;
            if (count === 0) return null;
            const meta = CATEGORY_META[cat];
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeCategory === cat
                    ? "bg-primary-600 text-white shadow-lg"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                {meta?.label ?? cat} ({count})
              </button>
            );
          })}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-surface-100">{sectionsData?.length ?? 0}</div>
            <div className="text-xs text-surface-500">Data Sections</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-accent-emerald">{formatNumber(totalRecords)}</div>
            <div className="text-xs text-surface-500">Total Records</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-primary-300">{totalSynced}</div>
            <div className="text-xs text-surface-500">Synced Sections</div>
          </div>
          <div className="glass-card p-3 text-center">
            <div className="text-2xl font-bold text-surface-100">
              {totalSynced > 0 ? Math.round((totalSynced / (sectionsData?.length ?? 1)) * 100) : 0}%
            </div>
            <div className="text-xs text-surface-500">Sync Coverage</div>
          </div>
        </div>

        {/* Sections List */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg font-medium">Failed to load BrsApi sections</p>
            <p className="text-sm mt-1 text-surface-500">
              Make sure the backend API is running and accessible
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          CATEGORY_ORDER.map((cat) => {
            const sections = grouped?.[cat];
            if (!sections || sections.length === 0) return null;
            if (activeCategory && activeCategory !== cat) return null;

            const meta = CATEGORY_META[cat];
            const catTotal = sections.reduce((s, sec) => s + sec.record_count, 0);

            return (
              <div key={cat}>
                {/* Category Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${meta?.color ?? "bg-surface-700 text-surface-300"}`}>
                      {meta?.label ?? cat}
                    </span>
                    <span className="text-xs text-surface-500">{sections.length} sections</span>
                  </div>
                  <span className="text-xs text-surface-500">{formatNumber(catTotal)} records</span>
                </div>

                {/* Section Cards */}
                <div className="space-y-2 mb-6">
                  {sections.map((section) => {
                    const sync = section.last_sync;
                    const needsSync = !sync || (section.record_count === 0);

                    return (
                      <div
                        key={section.id}
                        className={`glass-card p-4 hover:bg-surface-800/50 transition-colors ${
                          needsSync ? "border-r-2 border-accent-amber/50" : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4">
                          {/* Left: Icon + Info */}
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <SectionIcon icon={section.icon} />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h4 className="text-sm font-semibold text-surface-100">
                                  {section.name}
                                </h4>
                                <span className="text-[10px] text-surface-500 font-mono">
                                  {section.id}
                                </span>
                                {section.has_date_range && (
                                  <span className="text-[10px] bg-primary-600/10 text-primary-300 px-1.5 py-0.5 rounded">
                                    date range
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-3 mt-1 text-xs text-surface-500">
                                <span className="font-mono font-bold text-surface-300">
                                  {formatNumber(section.record_count)}
                                </span>
                                <span>records</span>
                                {section.last_data_date && (
                                  <>
                                    <span>•</span>
                                    <span className="text-primary-300" title={`Last data date: ${section.last_data_date}`}>
                                      📅 {section.last_data_date.length > 10 ? section.last_data_date : section.last_data_date.substring(0, 10)}
                                    </span>
                                  </>
                                )}
                                {sync && (
                                  <>
                                    <span>•</span>
                                    <StatusBadge status={sync.status} />
                                    <span>•</span>
                                    <span>{formatRelativeTime(sync.completed_at)}</span>
                                    {sync.duration_ms > 0 && (
                                      <span className="text-surface-600">
                                        ({formatDuration(sync.duration_ms)})
                                      </span>
                                    )}
                                  </>
                                )}
                                {!sync && (
                                  <>
                                    <span>•</span>
                                    <span className="text-accent-amber">not synced yet</span>
                                  </>
                                )}
                              </div>
                              {sync?.error_message && (
                                <div className="mt-1 text-[10px] text-accent-rose/80 truncate max-w-md">
                                  Error: {sync.error_message}
                                </div>
                              )}
                              {needsSync && (
                                <div className="mt-1">
                                  <span className="text-[10px] bg-accent-amber/10 text-accent-amber px-1.5 py-0.5 rounded">
                                    Data may be incomplete
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Right: Actions */}
                          <div className="flex items-center gap-2 shrink-0">
                            {sync && (
                              <>
                                {/* Download button */}
                                <a
                                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/brsapi/manage/download/${section.id}?format=json`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700 transition-all"
                                  title="Download JSON"
                                >
                                  <span className="material-icons text-sm">download</span>
                                </a>
                                <a
                                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/brsapi/manage/download/${section.id}?format=csv`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 hover:bg-surface-700 transition-all"
                                  title="Download CSV"
                                >
                                  <span className="text-xs font-bold">CSV</span>
                                </a>
                              </>
                            )}
                            <SyncButton
                              sectionId={section.id}
                              label="Sync"
                              syncing={syncingSections[section.id]}
                              onSync={doSyncSection}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}

        {/* Empty state */}
        {!isLoading && sectionsData?.length === 0 && (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">No data sections found</p>
            <p className="text-sm mt-1">Ensure the BrsApi integration is properly configured on the backend</p>
          </div>
        )}

        {/* Quick Links */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/instruments" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← All Symbols
          </Link>
          <Link href="/commodities" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            Commodities
          </Link>
          <Link href="/crypto" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            Crypto
          </Link>
          <Link href="/codal" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            Codal
          </Link>
          <Link href="/markets" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            Markets
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}
