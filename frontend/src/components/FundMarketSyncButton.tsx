"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { apiPost } from "@/lib/api";

/**
 * دکمه «همگام‌سازی بازار» — In-Page و Self-Contained.
 *
 * Endpoint: POST /funds/v2/discover (Zero-Config Auto-Discovery)
 * - بدون نیاز به پنل ادمین یا کنسول Jobها.
 * - خطای یک صندوق، بقیه را متوقف نمی‌کند (Quarantine در بک‌اند).
 */

interface DiscoverStats {
  discovered?: number;
  created?: number;
  updated?: number;
  aliases_added?: number;
  conflicts?: number;
  quarantined?: number;
  duration_ms?: number;
}

interface DiscoverResponse {
  success?: boolean;
  data?: {
    total_discovered?: number;
    stats?: DiscoverStats;
  };
}

export default function FundMarketSyncButton() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);

  const runSync = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await apiPost<DiscoverResponse>("/funds/v2/discover");
      const stats: DiscoverStats = res?.data?.stats ?? {};
      const discovered = res?.data?.total_discovered ?? stats.discovered ?? 0;
      const conflicts = stats.conflicts ?? 0;
      const msg =
        `همگام‌سازی کامل شد — ${discovered.toLocaleString("fa-IR")} صندوق` +
        ` | جدید: ${(stats.created ?? 0).toLocaleString("fa-IR")}` +
        ` | به‌روز: ${(stats.updated ?? 0).toLocaleString("fa-IR")}` +
        ` | Alias: ${(stats.aliases_added ?? 0).toLocaleString("fa-IR")}` +
        (conflicts > 0 ? ` | تداخل (نیازمند بررسی): ${conflicts.toLocaleString("fa-IR")}` : "");
      toast.success(msg);
      setLastSync(new Date().toLocaleTimeString("fa-IR"));
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["funds"] }),
        qc.invalidateQueries({ queryKey: ["fund-v2-monitoring"] }),
      ]);
    } catch {
      toast.error("همگام‌سازی بازار ناموفق بود — داده‌های قبلی نمایش داده می‌شوند");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={runSync}
        disabled={busy}
        aria-busy={busy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-surface-600/40 bg-surface-800/60 px-3 py-1.5 text-xs font-bold text-surface-200 transition-colors hover:bg-surface-700/60 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
        {busy ? "در حال همگام‌سازی..." : "همگام‌سازی بازار"}
      </button>
      {lastSync && (
        <span className="text-[10px] text-surface-500">
          آخرین همگام‌سازی: <span dir="ltr">{lastSync}</span>
        </span>
      )}
    </div>
  );
}
