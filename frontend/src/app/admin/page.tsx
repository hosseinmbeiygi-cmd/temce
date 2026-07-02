"use client";

import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface DashboardMetrics {
  total_instruments: number;
  active_signals: number;
  total_volume: number;
}

interface MarketBreakdown {
  market: string;
  count: number;
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

function formatNumber(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function AdminPage() {
  const { data: dashboardData } = useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: async () => {
      const res = await apiGet<Record<string, unknown>>("/dashboard");
      const metrics = res?.metrics as DashboardMetrics | undefined;
      return metrics || { total_instruments: 0, active_signals: 0, total_volume: 0 };
    },
    refetchInterval: 30000,
  });
  const dashboard = dashboardData;

  const { data: sections } = useQuery({
    queryKey: ["brsapi-sections"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: BrsapiSection[] }>("/brsapi/manage/sections");
      return res.data || [];
    },
    refetchInterval: 30000,
  });

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

  return (
    <AppLayout title="پنل مدیریت" subtitle="مدیریت سیستم، دیتابیس و همگام‌سازی">
      {/* Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-primary-400">storage</span>
            <span className="text-xs text-surface-500">کل رکوردها</span>
          </div>
          <div className="text-2xl font-bold gradient-text">
            {totalRecords ? formatNumber(totalRecords) : <Skeleton className="h-8 w-24" />}
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-accent-emerald">check_circle</span>
            <span className="text-xs text-surface-500">بخش‌های بروز</span>
          </div>
          <div className="text-2xl font-bold text-accent-emerald">
            {syncedSections ?? <Skeleton className="h-8 w-16" />}
            <span className="text-sm text-surface-500 mr-1">از {sections?.length || 0}</span>
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-accent-amber">sync</span>
            <span className="text-xs text-surface-500">بخش‌های API</span>
          </div>
          <div className="text-2xl font-bold text-surface-200">
            {sections?.length || <Skeleton className="h-8 w-16" />}
          </div>
        </div>
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className={`material-icons ${failedSections > 0 ? "text-accent-rose" : "text-surface-500"}`}>
              {failedSections > 0 ? "warning" : "check"}
            </span>
            <span className="text-xs text-surface-500">خطاها</span>
          </div>
          <p className={`text-2xl font-bold ${failedSections > 0 ? "text-accent-rose" : "text-surface-300"}`}>
            {failedSections || 0}
          </p>
        </div>
      </div>

      {/* Database Tables by Category */}
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
                            {formatDuration(sec.last_sync.duration_ms)}
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

      {/* Quick Actions */}
      <h2 className="text-lg font-bold text-surface-200 mb-4">⚡ اقدامات سریع</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <a href="/data" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📡</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">مدیریت داده</p>
          <p className="text-xs text-surface-500 mt-0.5">دریافت و همگام‌سازی داده‌های BrsApi</p>
        </a>
        <a href="/quotes/import" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📥</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">ورود قیمت</p>
          <p className="text-xs text-surface-500 mt-0.5">بارگذاری CSV قیمت‌های روزانه</p>
        </a>
        <a href="/news" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">📰</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">اخبار بازار</p>
          <p className="text-xs text-surface-500 mt-0.5">مشاهده آخرین اخبار و رویدادها</p>
        </a>
        <a href="/settings" className="glass-card p-4 hover:bg-surface-800/60 transition-colors group">
          <div className="text-2xl mb-2">⚙️</div>
          <p className="text-sm font-semibold text-surface-200 group-hover:text-primary-300">تنظیمات</p>
          <p className="text-xs text-surface-500 mt-0.5">تنظیمات کاربری و سیستم</p>
        </a>
      </div>

      {/* System Info */}
      <div className="glass-card p-4">
        <h3 className="font-bold text-surface-200 text-sm mb-3">ℹ️ اطلاعات سیستم</h3>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          <div>
            <span className="text-surface-500">دیتابیس:</span>
            <span className="text-surface-300 mr-1 font-mono">PostgreSQL 18</span>
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
            <span className="text-surface-500">منبع داده:</span>
            <span className="text-surface-300 mr-1 font-mono">BrsApi.ir</span>
          </div>
          <div>
            <span className="text-surface-500">وضعیت:</span>
            <span className="text-surface-300 mr-1">{syncedSections === sections?.length ? "✅ همه بخش‌ها بروز" : "⚠️ نیاز به همگام‌سازی"}</span>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
