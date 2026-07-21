"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet, extractArray } from "@/lib/api";
import { toast } from "sonner";
import DrawdownChart from "@/components/charts/DrawdownChart";

interface RiskMetric {
  label: string;
  value: string;
  status: "safe" | "warning" | "danger";
  description: string;
  icon: string;
  trend?: number;
}

interface RiskAlert {
  id: string;
  title: string;
  description: string;
  status: "active" | "triggered" | "expired";
  severity: "low" | "medium" | "high";
  createdAt: string;
  triggeredAt?: string;
}

interface RiskLimit {
  type: string;
  label: string;
  current: number;
  limit: number;
  unit: string;
  status: "ok" | "warning" | "exceeded";
}

interface DrawdownData {
  index: number;
  drawdown: number;
  date: string;
}

const DEFAULT_METRICS: RiskMetric[] = [
  { label: "Value at Risk (۹۵%)", value: "-۲.۴%", status: "safe", description: "حداکثر زیان محتمل در سطح اطمینان ۹۵٪", icon: "shield", trend: -0.3 },
  { label: "CVaR (۹۵%)", value: "-۴.۱%", status: "warning", description: "میانگین زیان در موارد فراتر از VaR", icon: "warning", trend: 0.5 },
  { label: "Sharpe Ratio", value: "۱.۸۷", status: "safe", description: "نسبت بازده به ریسک", icon: "trending_up", trend: 0.12 },
  { label: "Max Drawdown", value: "-۱۵.۳%", status: "danger", description: "بیشترین کاهش از اوج", icon: "arrow_downward", trend: -2.1 },
  { label: "Volatility", value: "۲۴.۶%", status: "warning", description: "انحراف معیار بازده‌ها", icon: "swap_vert", trend: 1.8 },
  { label: "Beta", value: "۱.۱۲", status: "warning", description: "حساسیت نسبت به بازار", icon: "compare_arrows", trend: 0.05 },
  { label: "Sortino Ratio", value: "۲.۳۱", status: "safe", description: "نسبت بازده به ریسک منفی", icon: "show_chart", trend: 0.2 },
  { label: "Concentration", value: "۳۲%", status: "danger", description: "درصد تمرکز در بزرگترین موقعیت", icon: "donut_large", trend: -1.5 },
];

const DEFAULT_ALERTS: RiskAlert[] = [
  { id: "1", title: "هشدار Max Drawdown", description: "حداکثر کاهش از ۱۲٪ فراتر رفته است", status: "triggered", severity: "high", createdAt: "۱۴۰۳/۰۴/۱۵", triggeredAt: "۱۴۰۳/۰۴/۱۸" },
  { id: "2", title: "هشدار Volatility", description: "نوسانات بازار از حد مجاز بالاتر رفته است", status: "active", severity: "medium", createdAt: "۱۴۰۳/۰۴/۲۰" },
  { id: "3", title: "هشدار Concentration", description: "تمرکز پرتفوی در یک سهم بیش از ۲۵٪ است", status: "active", severity: "high", createdAt: "۱۴۰۳/۰۴/۲۲" },
  { id: "4", title: "هشدار Daily Loss", description: "زیان روزانه از حد مجاز فراتر رفته است", status: "expired", severity: "low", createdAt: "۱۴۰۳/۰۴/۱۰" },
];

const DEFAULT_LIMITS: RiskLimit[] = [
  { type: "position", label: "حداکثر موقعیت در یک سهم", current: 25, limit: 30, unit: "%", status: "warning" },
  { type: "drawdown", label: "حداکثر Drawdown مجاز", current: 15.3, limit: 20, unit: "%", status: "ok" },
  { type: "daily_loss", label: "زیان روزانه مجاز", current: 2.1, limit: 3, unit: "%", status: "ok" },
  { type: "leverage", label: "حداکثر اهرم", current: 1.5, limit: 2, unit: "x", status: "ok" },
  { type: "exposure", label: "حداکثر Exposure", current: 85, limit: 90, unit: "%", status: "warning" },
];

// Deterministic pseudo-random for SSR-safe defaults (seed = index)
const seededRandom = (seed: number) => {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
};
const DEFAULT_DRAWDOWN_DATA: DrawdownData[] = Array.from({ length: 30 }, (_, i) => ({
  index: i,
  drawdown: -(seededRandom(i) * 15 + 2),
  date: `۱۴۰۳/۰۴/${String(i + 1).padStart(2, "0")}`,
}));

export default function RiskPage() {
  const [activeTab, setActiveTab] = useState<"metrics" | "alerts" | "limits">("metrics");

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["risk-metrics"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: RiskMetric[] }>("/risk/metrics");
        const items = extractArray<RiskMetric>(res);
        if (items.length > 0) return items;
      } catch {}
      return null;
    },
    staleTime: 60000,
  });

  const { data: alerts } = useQuery({
    queryKey: ["risk-alerts"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: RiskAlert[] }>("/risk/alerts");
        const items = extractArray<RiskAlert>(res);
        if (items.length > 0) return items;
      } catch {}
      return null;
    },
    staleTime: 30000,
  });

  const { data: limits } = useQuery({
    queryKey: ["risk-limits"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: RiskLimit[] }>("/risk/limits");
        const items = extractArray<RiskLimit>(res);
        if (items.length > 0) return items;
      } catch {}
      return null;
    },
    staleTime: 60000,
  });

  const { data: drawdownData } = useQuery({
    queryKey: ["risk-drawdown"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: DrawdownData[] }>("/risk/drawdown");
        const items = extractArray<DrawdownData>(res);
        if (items.length > 0) return items;
      } catch {}
      return null;
    },
    staleTime: 60000,
  });

  const displayMetrics = metrics || DEFAULT_METRICS;
  const displayAlerts = alerts || DEFAULT_ALERTS;
  const displayLimits = limits || DEFAULT_LIMITS;
  const displayDrawdown = drawdownData || DEFAULT_DRAWDOWN_DATA;

  const getStatusColor = (status: string) => {
    switch (status) {
      case "safe": return "text-accent-emerald";
      case "warning": return "text-accent-amber";
      case "danger": return "text-accent-rose";
      case "ok": return "text-accent-emerald";
      case "exceeded": return "text-accent-rose";
      default: return "text-surface-400";
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case "safe": return "bg-accent-emerald/10";
      case "warning": return "bg-accent-amber/10";
      case "danger": return "bg-accent-rose/10";
      case "ok": return "bg-accent-emerald/10";
      case "exceeded": return "bg-accent-rose/10";
      default: return "bg-surface-800/30";
    }
  };

  const getAlertStatusColor = (status: string) => {
    switch (status) {
      case "active": return "bg-accent-amber/10 text-accent-amber";
      case "triggered": return "bg-accent-rose/10 text-accent-rose";
      case "expired": return "bg-surface-700/30 text-surface-400";
      default: return "bg-surface-700/30 text-surface-400";
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "high": return "bg-accent-rose/10 text-accent-rose";
      case "medium": return "bg-accent-amber/10 text-accent-amber";
      case "low": return "bg-accent-emerald/10 text-accent-emerald";
      default: return "bg-surface-700/30 text-surface-400";
    }
  };

  return (
    <AppLayout title="مدیریت ریسک" subtitle="شاخص‌های ریسک، هشدارها و محدودیت‌ها">
      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab("metrics")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "metrics"
              ? "bg-primary-600/20 text-primary-400"
              : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
          }`}
        >
          <span className="material-icons text-sm align-middle ml-1">analytics</span>
          شاخص‌های ریسک
        </button>
        <button
          onClick={() => setActiveTab("alerts")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "alerts"
              ? "bg-primary-600/20 text-primary-400"
              : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
          }`}
        >
          <span className="material-icons text-sm align-middle ml-1">notifications</span>
          هشدارها
          {displayAlerts.filter(a => a.status === "active").length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-accent-rose/20 text-accent-rose rounded-full">
              {displayAlerts.filter(a => a.status === "active").length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("limits")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "limits"
              ? "bg-primary-600/20 text-primary-400"
              : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
          }`}
        >
          <span className="material-icons text-sm align-middle ml-1">gpp_maybe</span>
          محدودیت‌ها
        </button>
      </div>

      {/* Metrics Tab */}
      {activeTab === "metrics" && (
        <>
          {metricsLoading ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {[1,2,3,4,5,6,7,8].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {displayMetrics.map((m, mi) => (
                <Card key={`${m.label}-${mi}`} className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${getStatusBg(m.status)}`}>
                        <span className={`material-icons text-lg ${getStatusColor(m.status)}`}>{m.icon}</span>
                      </span>
                      <span className="text-xs text-surface-400">{m.label}</span>
                    </div>
                    <span className={`w-2 h-2 rounded-full ${
                      m.status === "safe" ? "bg-accent-emerald" : m.status === "warning" ? "bg-accent-amber" : "bg-accent-rose"
                    }`} />
                  </div>
                  <div className={`text-2xl font-bold font-mono ${getStatusColor(m.status)}`}>
                    {m.value}
                  </div>
                  <p className="text-xs text-surface-500 mt-2">{m.description}</p>
                  {m.trend !== undefined && (
                    <div className={`flex items-center gap-1 mt-2 text-xs ${m.trend > 0 ? "text-accent-rose" : "text-accent-emerald"}`}>
                      <span className="material-icons text-sm">{m.trend > 0 ? "trending_up" : "trending_down"}</span>
                      <span>{m.trend > 0 ? "+" : ""}{m.trend.toFixed(1)}%</span>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}

          {/* Drawdown Chart */}
          <Card title="نمودار Drawdown" subtitle="تحلیل کاهش از اوج پرتفوی" className="mb-6">
            <div className="h-64">
              <DrawdownChart data={displayDrawdown} height={250} />
            </div>
          </Card>

          {/* Quick Actions */}
          <div className="grid sm:grid-cols-3 gap-4">
            <button
              onClick={() => toast.info("تنظیم Stop Loss", { description: "قابلیت در حال توسعه است" })}
              className="glass-card p-4 text-left hover:border-accent-rose transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-lg bg-accent-rose/10 flex items-center justify-center">
                  <span className="material-icons text-accent-rose">stop</span>
                </span>
                <div>
                  <div className="text-sm font-medium text-surface-200">تنظیم Stop Loss</div>
                  <div className="text-xs text-surface-500"> تعیین حد زیان خودکار</div>
                </div>
              </div>
            </button>
            <button
              onClick={() => toast.info("تنظیم Take Profit", { description: "قابلیت در حال توسعه است" })}
              className="glass-card p-4 text-left hover:border-accent-emerald transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-lg bg-accent-emerald/10 flex items-center justify-center">
                  <span className="material-icons text-accent-emerald">flag</span>
                </span>
                <div>
                  <div className="text-sm font-medium text-surface-200">تنظیم Take Profit</div>
                  <div className="text-xs text-surface-500">تعیین حد سود خودکار</div>
                </div>
              </div>
            </button>
            <button
              onClick={() => setActiveTab("alerts")}
              className="glass-card p-4 text-left hover:border-accent-amber transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-lg bg-accent-amber/10 flex items-center justify-center">
                  <span className="material-icons text-accent-amber">history</span>
                </span>
                <div>
                  <div className="text-sm font-medium text-surface-200">تاریخچه هشدارها</div>
                  <div className="text-xs text-surface-500">مشاهده هشدارهای قبلی</div>
                </div>
              </div>
            </button>
          </div>
        </>
      )}

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <Card title="هشدارهای فعال" subtitle="لیست هشدارهای مدیریت ریسک">
          <div className="space-y-3">
            {displayAlerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center gap-4 p-4 rounded-lg bg-surface-800/20 hover:bg-surface-800/30 transition-colors"
              >
                <span className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  alert.severity === "high" ? "bg-accent-rose/10" : alert.severity === "medium" ? "bg-accent-amber/10" : "bg-accent-emerald/10"
                }`}>
                  <span className={`material-icons ${
                    alert.severity === "high" ? "text-accent-rose" : alert.severity === "medium" ? "text-accent-amber" : "text-accent-emerald"
                  }`}>
                    {alert.severity === "high" ? "error" : alert.severity === "medium" ? "warning" : "info"}
                  </span>
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-surface-200">{alert.title}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${getAlertStatusColor(alert.status)}`}>
                      {alert.status === "active" ? "فعال" : alert.status === "triggered" ? "فعال‌شده" : "منقضی"}
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${getSeverityColor(alert.severity)}`}>
                      {alert.severity === "high" ? "بحرانی" : alert.severity === "medium" ? "متوسط" : "کم"}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 mt-1">{alert.description}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-surface-500">
                    <span>ایجاد: {alert.createdAt}</span>
                    {alert.triggeredAt && <span>فعال‌شده: {alert.triggeredAt}</span>}
                  </div>
                </div>
                <button
                  onClick={() => toast.info("جزئیات هشدار", { description: alert.title })}
                  className="px-3 py-1.5 text-xs text-surface-400 hover:text-surface-200 hover:bg-surface-700/30 rounded-lg transition-colors"
                >
                  جزئیات
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Limits Tab */}
      {activeTab === "limits" && (
        <Card title="محدودیت‌های ریسک" subtitle="سطوح مجاز و وضعیت فعلی">
          <div className="space-y-4">
            {displayLimits.map((limit, i) => {
              const percentage = (limit.current / limit.limit) * 100;
              const isWarning = percentage > 80;
              const isExceeded = percentage >= 100;
              return (
                <div key={`${limit.type}-${i}`} className="p-4 rounded-lg bg-surface-800/20">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-surface-200">{limit.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-mono ${isExceeded ? "text-accent-rose" : isWarning ? "text-accent-amber" : "text-accent-emerald"}`}>
                        {limit.current.toFixed(1)}{limit.unit}
                      </span>
                      <span className="text-surface-500">/</span>
                      <span className="text-sm font-mono text-surface-400">
                        {limit.limit}{limit.unit}
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isExceeded ? "bg-accent-rose" : isWarning ? "bg-accent-amber" : "bg-accent-emerald"
                      }`}
                      style={{ width: `${Math.min(percentage, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-surface-500">
                      {percentage.toFixed(1)}% استفاده شده
                    </span>
                    <span className={`text-xs ${isExceeded ? "text-accent-rose" : isWarning ? "text-accent-amber" : "text-accent-emerald"}`}>
                      {isExceeded ? " exceeded" : isWarning ? "نزدیک به حد" : "در محدوده مجاز"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </AppLayout>
  );
}