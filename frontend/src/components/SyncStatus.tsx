"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import { applyCustomThresholds, loadSyncSettings } from "@/lib/sync-settings";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface TableSyncInfo {
  last_fetched: string | null;
  record_count: number;
  age_minutes: number;
  status: "ok" | "stale" | "outdated" | "missing" | "unknown" | "error";
  max_age_minutes: number;
  error?: string;
}

type SyncStatusMap = Record<string, TableSyncInfo>;

interface SyncResult {
  success: boolean;
  items_count: number;
  duration_ms: number;
  error?: string;
}

// ── Config ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

/** Maps sync-status keys (from get_sync_status) to backend section IDs (from POST /manage/sync/{section_id}) */
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

const TABLE_LABELS: Record<string, { label: string; icon: string; order: number }> = {
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

function getLabel(key: string): { label: string; icon: string } {
  return TABLE_LABELS[key] || { label: key, icon: "📦" };
}

// ── Toaster ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: { message: string; type: "success" | "error" | "warning"; onClose: () => void }) {
  const router = useRouter();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const timer = setTimeout(() => onCloseRef.current(), 4000);
    return () => clearTimeout(timer);
  }, []); // stable — never recreates the timeout

  return (
    <div
      className={`fixed bottom-4 right-4 z-[100] flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-2xl text-xs font-medium transition-all animate-slide-up ${
        type === "success"
          ? "bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30"
          : type === "warning"
          ? "bg-accent-amber/15 text-accent-amber border border-accent-amber/30"
          : "bg-accent-rose/15 text-accent-rose border border-accent-rose/30"
      }`}
      style={{ animation: "slideUp 0.3s ease-out" }}
    >
      <span className="material-icons text-sm">{type === "success" ? "check_circle" : type === "warning" ? "warning_amber" : "error"}</span>
      <span className="flex-1 min-w-0">{message}</span>
      {type === "warning" && (
        <button
          onClick={() => { router.push("/sync"); onClose(); }}
          className="px-2 py-1 rounded-lg text-[10px] font-bold bg-accent-amber/20 text-accent-amber hover:bg-accent-amber/30 transition-all shrink-0"
        >
          رفتن به sync
        </button>
      )}
      <button onClick={onClose} className="mr-1 opacity-60 hover:opacity-100 shrink-0">
        <span className="material-icons text-sm">close</span>
      </button>
      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

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
    return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
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

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "bg-accent-emerald",
    stale: "bg-accent-amber",
    outdated: "bg-accent-rose",
    missing: "bg-surface-600",
    unknown: "bg-surface-500",
    error: "bg-accent-rose",
  };
  return (
    <span
      className={`w-2 h-2 rounded-full shrink-0 ${colors[status] || "bg-surface-600"}`}
      title={status}
    />
  );
}

function StatusLabel({ status }: { status: string }) {
  const labels: Record<string, string> = {
    ok: "به‌روز",
    stale: "کمی قدیمی",
    outdated: "قدیمی",
    missing: "بدون داده",
    unknown: "نامشخص",
    error: "خطا",
  };
  const colors: Record<string, string> = {
    ok: "text-accent-emerald",
    stale: "text-accent-amber",
    outdated: "text-accent-rose",
    missing: "text-surface-500",
    unknown: "text-surface-400",
    error: "text-accent-rose",
  };
  return (
    <span className={`text-[10px] font-semibold ${colors[status] || "text-surface-500"}`}>
      {labels[status] || status}
    </span>
  );
}

// ── SyncStatus ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function SyncStatus() {
  // ── Load custom freshness thresholds ──
  const [customSettings, setCustomSettings] = useState(() => loadSyncSettings());
  useEffect(() => {
    const handler = () => setCustomSettings(loadSyncSettings());
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [syncingKeys, setSyncingKeys] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "warning" } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasShownOutdatedToast = useRef(false);

  // Click outside to close
  useEffect(() => {
    if (!expanded) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [expanded]);

  // ── Fetch sync status ──
  const { data: syncStatus, isLoading, isError } = useQuery({
    queryKey: ["brsapi-sync-status"],
    queryFn: async (): Promise<SyncStatusMap> => {
      const res = await apiGet<{ success: boolean; data: SyncStatusMap }>("/brsapi/sync-status");
      return res?.data ?? {};
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  // ── Sync Now handler ──
  const handleSyncNow = useCallback(async (key: string) => {
    const sectionId = SECTION_ID_MAP[key];
    if (!sectionId) {
      setToast({ message: `بخش '${key}' پشتیبانی نمی‌شود`, type: "error" });
      return;
    }

    setSyncingKeys((prev) => ({ ...prev, [key]: true }));
    try {
      const res = await apiPost<{ success: boolean; data: SyncResult }>(
        `/brsapi/manage/sync/${sectionId}`
      );

      if (res?.success && res.data?.success) {
        const items = res.data.items_count ?? 0;
        const dur = formatDuration(res.data.duration_ms ?? 0);
        setToast({ message: `✅ ${getLabel(key).label}: ${items} رکورد در ${dur}`, type: "success" });
      } else {
        setToast({
          message: `❌ ${getLabel(key).label}: ${res?.data?.error || "خطا در sync"}`,
          type: "error",
        });
      }
    } catch (err) {
      setToast({ message: `❌ ${getLabel(key).label}: ${String(err)}`, type: "error" });
    } finally {
      setSyncingKeys((prev) => ({ ...prev, [key]: false }));
      // Refresh the sync status data
      queryClient.invalidateQueries({ queryKey: ["brsapi-sync-status"] });
    }
  }, [queryClient]);

  // ── Helpers: Browser Notification ──
  const sendBrowserNotification = useCallback(
    (title: string, body: string) => {
      if (typeof window === "undefined" || !("Notification" in window)) return;

      if (Notification.permission === "granted") {
        const notif = new Notification(title, {
          body,
          icon: "/favicon.ico",
          tag: "temce-sync-outdated",
        });
        notif.onclick = () => {
          window.focus();
          window.location.href = "/sync";
        };
      } else if (Notification.permission !== "denied") {
        // Only request on user interaction — do it silently here
        Notification.requestPermission().then((perm) => {
          if (perm === "granted") {
            const notif = new Notification(title, {
              body,
              icon: "/favicon.ico",
              tag: "temce-sync-outdated",
            });
            notif.onclick = () => {
              window.focus();
              window.location.href = "/sync";
            };
          }
        });
      }
    },
    []
  );

  // ── Outdated data toast + browser notification (once per page load) ──
  useEffect(() => {
    if (hasShownOutdatedToast.current) return;
    if (!syncStatus) return;

    const outdatedKeys = Object.entries(syncStatus)
      .filter(([, info]) => info.status === "outdated" && info.record_count > 0)
      .map(([key]) => {
        const cfg = TABLE_LABELS[key];
        return cfg ? `${cfg.icon} ${cfg.label}` : key;
      });

    if (outdatedKeys.length > 0) {
      setToast({
        message: `⚠️ داده‌های ${outdatedKeys.join("، ")} قدیمی هستند — لطفاً sync کنید`,
        type: "warning",
      });
      hasShownOutdatedToast.current = true;

      // Browser Notification API
      const sectionNames = outdatedKeys.join("، ");
      sendBrowserNotification(
        "⚠️ داده‌های قدیمی — همگام‌سازی نیاز است",
        `${sectionNames} — برای sync کلیک کنید`
      );
    }
  }, [syncStatus, sendBrowserNotification]);

  // ── Apply custom freshness thresholds ──
  const effectiveStatus = syncStatus ? applyCustomThresholds(syncStatus, customSettings) : undefined;

  // ── Aggregate status ──
  const entries = effectiveStatus
    ? Object.entries(effectiveStatus)
        .filter(([, info]) => info.record_count > 0 || info.status !== "missing")
        .sort(([aKey], [bKey]) => {
          const aOrder = TABLE_LABELS[aKey]?.order ?? 99;
          const bOrder = TABLE_LABELS[bKey]?.order ?? 99;
          return aOrder - bOrder;
        })
    : [];

  const okCount = entries.filter(([, info]) => info.status === "ok").length;
  const staleCount = entries.filter(([, info]) => info.status === "stale").length;
  const outdatedCount = entries.filter(([, info]) => info.status === "outdated").length;
  const missingCount = entries.filter(([, info]) => info.status === "missing").length;
  const totalCount = entries.length;

  const hasIssues = staleCount + outdatedCount + missingCount > 0;

  // ── Overall health dot ──
  const overallStatus: string =
    missingCount === totalCount ? "missing" :
    outdatedCount > 0 ? "outdated" :
    staleCount > 0 ? "stale" :
    totalCount > 0 ? "ok" : "unknown";

  const isAnySyncing = Object.values(syncingKeys).some(Boolean);

  return (
    <div className="relative" dir="rtl" ref={containerRef}>
      {/* ── Toast notification ── */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── Compact pill button ── */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all border ${
          expanded
            ? "bg-surface-800 border-primary-500/40 text-surface-200"
            : hasIssues
              ? "bg-accent-amber/10 border-accent-amber/30 text-accent-amber hover:bg-accent-amber/15"
              : "bg-surface-800/50 border-surface-700 text-surface-400 hover:bg-surface-700/50 hover:text-surface-300"
        } ${isAnySyncing ? "animate-pulse" : ""}`}
      >
        {/* Status indicator */}
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            overallStatus === "ok" ? "bg-accent-emerald" :
            overallStatus === "stale" ? "bg-accent-amber" :
            overallStatus === "outdated" ? "bg-accent-rose" :
            "bg-surface-500"
          } ${isAnySyncing ? "animate-ping" : ""}`}
        />

        <span className={`material-icons text-sm ${isAnySyncing ? "animate-spin" : ""}`}>
          {isAnySyncing ? "sync" : "sync"}
        </span>

        {/* Summary */}
        {isLoading ? (
          <span className="text-surface-500">...</span>
        ) : hasIssues ? (
          <span className="flex items-center gap-1">
            {staleCount > 0 && <span>{staleCount} قدیمی</span>}
            {outdatedCount > 0 && <span>{outdatedCount} خیلی قدیمی</span>}
            {missingCount > 0 && <span>{missingCount} خالی</span>}
          </span>
        ) : (
          <span className="flex items-center gap-1">
            <span className="text-accent-emerald">به‌روز</span>
            <span className="text-surface-500">({okCount}/{totalCount})</span>
          </span>
        )}

        <span className="material-icons text-sm transition-transform" style={{ transform: expanded ? "rotate(180deg)" : "" }}>
          expand_more
        </span>
      </button>

      {/* ── Expanded panel ── */}
      {expanded && (
        <div className="absolute left-0 top-full mt-1.5 z-50 w-[400px] max-h-[480px] overflow-y-auto glass-card p-3 shadow-xl border border-surface-700/60">
          <div className="flex items-center justify-between mb-2.5 pb-2 border-b border-surface-700/50">
            <h4 className="text-xs font-bold text-surface-200">وضعیت همگام‌سازی داده‌ها</h4>
            <div className="flex items-center gap-2 text-[10px] text-surface-500">
              {okCount > 0 && <span className="text-accent-emerald">{okCount} به‌روز</span>}
              {staleCount > 0 && <span className="text-accent-amber">{staleCount} کمی قدیمی</span>}
              {outdatedCount > 0 && <span className="text-accent-rose">{outdatedCount} قدیمی</span>}
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-surface-800/30 animate-pulse rounded-lg" />
              ))}
            </div>
          ) : isError ? (
            <p className="text-xs text-accent-rose text-center py-4">
              خطا در دریافت وضعیت
            </p>
          ) : entries.length === 0 ? (
            <p className="text-xs text-surface-500 text-center py-4">
              هیچ داده‌ای یافت نشد. اسکریپت‌های sync را اجرا کنید.
            </p>
          ) : (
            <div className="space-y-1">
              {entries.map(([key, info]) => {
                const { label, icon } = getLabel(key);
                const isSyncing = syncingKeys[key] ?? false;

                return (
                  <div
                    key={key}
                    className={`flex items-center justify-between py-1.5 px-2 rounded-lg transition-colors ${
                      isSyncing
                        ? "bg-primary-600/10 border border-primary-500/20"
                        : "hover:bg-surface-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <StatusDot status={info.status} />
                      <span className="text-xs text-surface-300 truncate">{icon} {label}</span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {/* Record count */}
                      <span className="text-[10px] font-mono text-surface-600" title={`${formatNumber(info.record_count)} رکورد`}>
                        {formatNumber(info.record_count)}
                      </span>

                      {/* Last fetched / syncing indicator */}
                      {isSyncing ? (
                        <span className="flex items-center gap-1 text-[10px] text-accent-amber font-medium">
                          <span className="material-icons text-xs animate-spin">sync</span>
                          در حال sync...
                        </span>
                      ) : info.last_fetched ? (
                        <span
                          className="text-[10px] text-surface-500"
                          title={`آخرین بروزرسانی: ${formatTime(info.last_fetched)}`}
                        >
                          {formatRelativeTime(info.last_fetched)}
                        </span>
                      ) : (
                        <span className="text-[10px] text-surface-600">—</span>
                      )}

                      {/* Status label */}
                      <StatusLabel status={info.status} />

                      {/* ── Sync Now button ── */}
                      <button
                        onClick={() => handleSyncNow(key)}
                        disabled={isSyncing}
                        className={`flex items-center justify-center w-7 h-7 rounded-lg text-xs transition-all ${
                          isSyncing
                            ? "bg-primary-600/20 text-primary-300 cursor-wait"
                            : "bg-surface-800 text-surface-400 hover:bg-primary-600/20 hover:text-primary-300 border border-surface-700 hover:border-primary-500/30"
                        }`}
                        title={`Sync ${label}`}
                      >
                        <span className={`material-icons text-sm ${isSyncing ? "animate-spin" : ""}`}>
                          {isSyncing ? "sync" : "sync"}
                        </span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Footer ── */}
          <div className="mt-2.5 pt-2 border-t border-surface-700/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <a
                href="/sync-settings"
                className="text-[10px] text-primary-400 hover:text-primary-300 transition-colors"
              >
                ⚙️ تنظیمات آستانه
              </a>
              <a
                href="/brsapi"
                className="text-[10px] text-primary-400 hover:text-primary-300 transition-colors"
              >
                مدیریت داده‌ها →
              </a>
            </div>
            <span className="text-[9px] text-surface-600">
              بروزرسانی خودکار هر ۶۰ ثانیه
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
