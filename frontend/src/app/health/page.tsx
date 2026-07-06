"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface ServiceCheck {
  status: string;
  latency_ms: number;
  detail: string;
  total_gb?: number;
  used_gb?: number;
  free_gb?: number;
  used_pct?: number;
}

interface HealthData {
  status: string;
  timestamp: string;
  service: string;
  version: string;
  checks: Record<string, ServiceCheck>;
  summary: {
    total: number;
    ok: number;
    degraded: number;
    down: number;
    degraded_services: string[];
    down_services: string[];
  };
}

// ── Status helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const STATUS_CFG: Record<string, { label: string; icon: string; color: string; bg: string; badge: string }> = {
  ok: { label: "سالم", icon: "✅", color: "text-accent-emerald", bg: "bg-accent-emerald/10", badge: "bg-accent-emerald/20 text-accent-emerald" },
  degraded: { label: "مختل", icon: "⚠️", color: "text-accent-amber", bg: "bg-accent-amber/10", badge: "bg-accent-amber/20 text-accent-amber" },
  down: { label: "از کار افتاده", icon: "❌", color: "text-accent-rose", bg: "bg-accent-rose/10", badge: "bg-accent-rose/20 text-accent-rose" },
};

function formatBytes(gb: number): string {
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`;
  return `${gb} GB`;
}

function formatDateTime(iso: string): string {
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
    return iso.slice(0, 19);
  }
}

function latencyLabel(ms: number): string {
  if (ms <= 0) return "—";
  if (ms < 1) return "<1 ms";
  if (ms < 100) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms)} ms`;
}

// ── Service info ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const SERVICE_META: Record<string, { label: string; icon: string; desc: string }> = {
  postgresql: { label: "PostgreSQL", icon: "🗄️", desc: "بانک اطلاعاتی اصلی — داده‌های نمادها، قیمت‌ها، معاملات" },
  redis: { label: "Redis", icon: "⚡", desc: "کش و صف پیام — بهبود سرعت پاسخگویی و Job Queue" },
  brsapi: { label: "BrsApi.ir", icon: "🌐", desc: "API داده‌های بازار — قیمت‌های لحظه‌ای، اخبار کدال، داده‌های کالایی" },
  disk: { label: "Disk", icon: "💾", desc: "فضای ذخیره‌سازی — دیتابیس، فایل‌ها، کش فایل" },
};

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function HealthPage() {
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  const { data, isLoading, isError, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: HealthData }>("/dashboard/health");
      return res.data;
    },
    refetchInterval: autoRefresh ? 10_000 : false,
  });

  const checks = data?.checks || {};
  const summary = data?.summary;
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "";

  const overallCfg = STATUS_CFG[data?.status || ""] || STATUS_CFG.down;

  return (
    <AppLayout title="🩺 سلامت سرویس‌ها" subtitle="وضعیت real-time تمام سرویس‌های پلتفرم">
      <div className="max-w-5xl mx-auto space-y-5">
        {/* ── Overall Status Banner ── */}
        <div className={`glass-card p-4 ${overallCfg.bg} border-r-4 ${data?.status === "ok" ? "border-accent-emerald" : data?.status === "degraded" ? "border-accent-amber" : "border-accent-rose"} flex items-center justify-between gap-4`}>
          <div className="flex items-center gap-3">
            <span className="text-3xl">{overallCfg.icon}</span>
            <div>
              <p className={`text-base font-bold ${overallCfg.color}`}>
                وضعیت کلی: {overallCfg.label}
              </p>
              {data && (
                <p className="text-[10px] text-surface-500 mt-0.5">
                  {data.service} v{data.version} • {summary?.ok}/{summary?.total} سرویس سالم
                  {summary && summary.degraded > 0 && ` • ${summary.degraded} مختل`}
                  {summary && summary.down > 0 && ` • ${summary.down} از کار افتاده`}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <label className="flex items-center gap-1.5 text-[10px] text-surface-500 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="accent-primary-500"
              />
              Auto-refresh
            </label>
            <button onClick={() => refetch()} className="px-2.5 py-1.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-lg text-[10px] transition-colors">
              🔄
            </button>
          </div>
        </div>

        {/* ── Timestamp ── */}
        {data && (
          <div className="text-[10px] text-surface-500 text-center">
            آخرین بروزرسانی: {formatDateTime(data.timestamp)}
            {lastUpdated && <span> (وصل: {lastUpdated})</span>}
          </div>
        )}

        {/* ── Service Cards ── */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-40 w-full" />)}
          </div>
        ) : isError ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-surface-400 text-sm">خطا در دریافت وضعیت سرویس‌ها</p>
            <button onClick={() => refetch()} className="mt-3 px-4 py-2 bg-primary-600 rounded-lg text-sm text-white">
              تلاش مجدد
            </button>
          </div>
        ) : Object.keys(checks).length === 0 ? (
          <div className="text-center py-16">
            <p className="text-5xl mb-4">🔌</p>
            <p className="text-surface-500 text-sm">هیچ سرویسی برای بررسی وجود ندارد</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Object.entries(checks).map(([name, check]) => {
              const cfg = STATUS_CFG[check.status] || STATUS_CFG.down;
              const meta = SERVICE_META[name] || { label: name, icon: "🔧", desc: "" };
              const isDisk = name === "disk";

              return (
                <div key={name} className={`glass-card p-4 border-r-2 ${check.status === "ok" ? "border-accent-emerald/30" : check.status === "degraded" ? "border-accent-amber/30" : "border-accent-rose/30"}`}>
                  {/* Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{meta.icon}</span>
                      <div>
                        <p className="text-sm font-semibold text-surface-200">{meta.label}</p>
                        <p className="text-[9px] text-surface-600">{meta.desc}</p>
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-medium ${cfg.badge}`}>
                      {cfg.icon} {cfg.label}
                    </span>
                  </div>

                  {/* Status + Latency */}
                  <div className="flex gap-4 text-[10px]">
                    <div className="flex-1">
                      <span className="text-surface-500">وضعیت: </span>
                      <span className={cfg.color}>{cfg.label}</span>
                    </div>
                    <div>
                      <span className="text-surface-500">تأخیر: </span>
                      <span className="font-mono text-surface-300">{latencyLabel(check.latency_ms)}</span>
                    </div>
                  </div>

                  {/* Detail */}
                  <p className="text-[10px] text-surface-400 mt-1.5" title={check.detail}>
                    {check.detail}
                  </p>

                  {/* Disk-specific bar */}
                  {isDisk && check.used_pct !== undefined && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-surface-500">
                          {formatBytes(check.used_gb || 0)} / {formatBytes(check.total_gb || 0)}
                        </span>
                        <span className={`font-mono ${check.status === "ok" ? "text-accent-emerald" : check.status === "degraded" ? "text-accent-amber" : "text-accent-rose"}`}>
                          {check.used_pct}%
                        </span>
                      </div>
                      <div className="h-2 bg-surface-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            check.status === "ok" ? "bg-accent-emerald" : check.status === "degraded" ? "bg-accent-amber" : "bg-accent-rose"
                          }`}
                          style={{ width: `${Math.min(check.used_pct, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Latency bar for non-disk services */}
                  {!isDisk && (
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${
                            check.status === "ok"
                              ? "bg-accent-emerald"
                              : check.status === "degraded"
                                ? "bg-accent-amber"
                                : "bg-accent-rose"
                          }`}
                          style={{
                            width: `${Math.min(check.latency_ms > 0 ? (check.latency_ms / 500) * 100 : 0, 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[8px] text-surface-600 font-mono w-12 text-right">{latencyLabel(check.latency_ms)}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Summary Footer ── */}
        <div className="glass-card p-3 text-[10px] text-surface-500 space-y-1">
          <div className="flex flex-wrap gap-4">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-emerald" /> سالم ({summary?.ok || 0})</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> مختل ({summary?.degraded || 0})</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-rose" /> از کار افتاده ({summary?.down || 0})</span>
          </div>
          {summary && summary.degraded_services?.length > 0 && (
            <p>⚠️ سرویس‌های مختل: {summary.degraded_services.join("، ")}</p>
          )}
          {summary && summary.down_services?.length > 0 && (
            <p>❌ سرویس‌های از کار افتاده: {summary.down_services.join("، ")}</p>
          )}
          <p>بروزرسانی خودکار هر ۱۰ ثانیه. تأخیرها بر حسب میلی‌ثانیه (ms) اندازه‌گیری می‌شوند.</p>
        </div>
      </div>
    </AppLayout>
  );
}
