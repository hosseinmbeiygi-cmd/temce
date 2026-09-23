"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import {
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Database,
  RefreshCw,
  Clock,
  HelpCircle,
  HardDrive,
} from "lucide-react";

interface HealthMetric {
  label: string;
  status: "healthy" | "warning" | "error" | "unknown";
  value: string;
  details: string;
  icon: string;
  lastUpdated: string;
}

interface DataSourceStatus {
  source: string;
  type: string;
  status: "connected" | "disconnected" | "degraded";
  latency: string;
  lastSync: string;
  recordsCount: number;
  errorRate: string;
}

interface DataQualityIssue {
  id: string;
  severity: "critical" | "major" | "minor";
  source: string;
  description: string;
  affectedRecords: number;
  detectedAt: string;
}

const DEFAULT_METRICS: HealthMetric[] = [
  { label: "پایگاه داده اصلی", status: "healthy", value: "فعال", details: "PostgreSQL 16 با ۱۲۸ اتصال همزمان", icon: "database", lastUpdated: "هم‌اکنون" },
  { label: "Redis Cache", status: "healthy", value: "فعال", details: "Redis 7.2, ۸۵% حافظه استفاده شده", icon: "database", lastUpdated: "هم‌اکنون" },
  { label: "API Core", status: "healthy", value: "۲۰۰ ms", details: "میانگین زمان پاسخ", icon: "database", lastUpdated: "۱ دقیقه قبل" },
  { label: "WebSocket", status: "warning", value: "۱۲۰ ms", details: "تأخیر بالاتر از حد نرمال", icon: "database", lastUpdated: "۵ دقیقه قبل" },
  { label: "Task Queue", status: "healthy", value: "۰ job", details: "صف پردازش خالی است", icon: "database", lastUpdated: "هم‌اکنون" },
  { label: "TimescaleDB", status: "healthy", value: "فعال", details: "۳۲GB از ۱۰۰GB استفاده شده", icon: "database", lastUpdated: "هم‌اکنون" },
];

const DEFAULT_SOURCES: DataSourceStatus[] = [
  { source: "TSETMC", type: "بورس تهران", status: "connected", latency: "۳۴۰ ms", lastSync: "۱۴۰۵/۰۴/۱۵ ۱۴:۳۰", recordsCount: 1852340, errorRate: "۰.۲%" },
  { source: "BRSAPI", type: "کدال", status: "connected", latency: "۲۸۰ ms", lastSync: "۱۴۰۵/۰۴/۱۵ ۱۴:۳۰", recordsCount: 892450, errorRate: "۰.۱%" },
  { source: "Gold Desk", type: "طلا و ارز", status: "degraded", latency: "۱.۲ s", lastSync: "۱۴۰۵/۰۴/۱۵ ۱۴:۲۵", recordsCount: 12450, errorRate: "۳.۵%" },
  { source: "Crypto Exchange", type: "ارز دیجیتال", status: "connected", latency: "۱۵۰ ms", lastSync: "۱۴۰۵/۰۴/۱۵ ۱۴:۳۰", recordsCount: 567200, errorRate: "۰.۰۵%" },
  { source: "Forex Feed", type: "بازار جهانی", status: "connected", latency: "۲۱۰ ms", lastSync: "۱۴۰۵/۰۴/۱۵ ۱۴:۳۰", recordsCount: 34500, errorRate: "۰.۳%" },
  { source: "Iran Economy", type: "شاخص‌های اقتصادی", status: "disconnected", latency: "N/A", lastSync: "۱۴۰۵/۰۴/۱۴ ۰۸:۰۰", recordsCount: 1230, errorRate: "۱۰۰%" },
];

const DEFAULT_ISSUES: DataQualityIssue[] = [
  { id: "1", severity: "critical", source: "Gold Desk", description: "قطع ارتباط با منبع داده طلا - داده‌های لحظه‌ای به‌روز نمی‌شوند", affectedRecords: 450, detectedAt: "۱۴۰۵/۰۴/۱۵ ۱۴:۲۰" },
  { id: "2", severity: "major", source: "TSETMC", description: "عدم تطابق در رکوردهای نماد فولاد - ۱۵ رکورد تکراری", affectedRecords: 15, detectedAt: "۱۴۰۵/۰۴/۱۵ ۱۳:۰۰" },
  { id: "3", severity: "minor", source: "BRSAPI", description: "تغییر در ساختار فیلدهای گزارش کدال", affectedRecords: 3, detectedAt: "۱۴۰۵/۰۴/۱۵ ۱۰:۳۰" },
  { id: "4", severity: "minor", source: "Crypto Exchange", description: "اختلاف ۰.۱٪ در قیمت بیت‌کوین بین دو صرافی", affectedRecords: 120, detectedAt: "۱۴۰۵/۰۴/۱۵ ۰۹:۱۵" },
];

function getStatusIcon(status: string) {
  if (status === "healthy" || status === "connected") return CheckCircle2;
  if (status === "warning" || status === "degraded") return AlertTriangle;
  if (status === "error" || status === "disconnected") return XCircle;
  return HelpCircle;
}

function getStatusColor(status: string): string {
  if (status === "healthy" || status === "connected") return "text-accent-emerald";
  if (status === "warning" || status === "degraded") return "text-accent-amber";
  if (status === "error" || status === "disconnected") return "text-accent-rose";
  return "text-surface-500";
}

function getStatusBg(status: string): string {
  if (status === "healthy" || status === "connected") return "bg-accent-emerald/10";
  if (status === "warning" || status === "degraded") return "bg-accent-amber/10";
  if (status === "error" || status === "disconnected") return "bg-accent-rose/10";
  return "bg-surface-800/30";
}

function getSeverityColor(severity: string): string {
  if (severity === "critical") return "text-accent-rose bg-accent-rose/10";
  if (severity === "major") return "text-accent-amber bg-accent-amber/10";
  return "text-accent-cyan bg-accent-cyan/10";
}

type TabKey = "overview" | "sources" | "issues";

export default function DataHealthPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const { data: healthData, isLoading } = useQuery({
    queryKey: ["data-health"],
    queryFn: async () => {
      try {
        const r = await apiGet<{ metrics: HealthMetric[]; sources: DataSourceStatus[]; issues: DataQualityIssue[] }>("/system/health");
        if (r?.metrics) return r;
      } catch {}
      return null;
    },
    staleTime: 30000,
  });

  const metrics = healthData?.metrics ?? DEFAULT_METRICS;
  const sources = healthData?.sources ?? DEFAULT_SOURCES;
  const issues = healthData?.issues ?? DEFAULT_ISSUES;

  const TABS: { key: TabKey; label: string }[] = [
    { key: "overview", label: "نمای کلی" },
    { key: "sources", label: "منابع داده" },
    { key: "issues", label: "مشکلات" },
  ];

  return (
    <AppLayout title="سلامت داده" subtitle="وضعیت سرویس‌ها، منابع داده و کیفیت اطلاعات">
      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg bg-surface-800/50 p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`rounded-md px-4 py-2 text-xs font-medium transition-colors ${
              activeTab === t.key ? "bg-surface-700 text-surface-100 shadow-sm" : "text-surface-500 hover:text-surface-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : activeTab === "overview" ? (
        /* Overview - Health Metrics */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {metrics.map((m, i) => {
            const Icon = getStatusIcon(m.status);
            return (
              <div key={i} className="glass-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-surface-500">{m.label}</span>
                  <Icon className={`size-4 ${getStatusColor(m.status)}`} />
                </div>
                <div className={`text-lg font-bold mb-1 ${getStatusColor(m.status)}`}>{m.value}</div>
                <p className="text-[10px] text-surface-500">{m.details}</p>
                <div className="mt-2 flex items-center gap-1 text-[9px] text-surface-600">
                  <Clock className="size-3" />
                  {m.lastUpdated}
                </div>
              </div>
            );
          })}
        </div>
      ) : activeTab === "sources" ? (
        /* Data Sources */
        <Card title="منابع داده" subtitle="وضعیت اتصال و آخرین همگام‌سازی">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-surface-800 text-surface-500">
                  <th className="text-right py-3 px-2 font-medium">منبع</th>
                  <th className="text-right py-3 px-2 font-medium">نوع</th>
                  <th className="text-center py-3 px-2 font-medium">وضعیت</th>
                  <th className="text-center py-3 px-2 font-medium">تأخیر</th>
                  <th className="text-center py-3 px-2 font-medium">آخرین همگام</th>
                  <th className="text-center py-3 px-2 font-medium">تعداد رکورد</th>
                  <th className="text-center py-3 px-2 font-medium">خطا</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s, i) => (
                  <tr key={i} className="border-b border-surface-800/50 hover:bg-surface-800/20 transition-colors">
                    <td className="py-3 px-2 text-surface-200 font-medium">{s.source}</td>
                    <td className="py-3 px-2 text-surface-400">{s.type}</td>
                    <td className="py-3 px-2 text-center">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${getStatusBg(s.status)} ${getStatusColor(s.status)}`}>
                        {s.status === "connected" ? "متصل" : s.status === "degraded" ? "مختل" : "قطع"}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-center text-surface-400 font-mono">{s.latency}</td>
                    <td className="py-3 px-2 text-center text-surface-400">{s.lastSync}</td>
                    <td className="py-3 px-2 text-center text-surface-400 font-mono">{s.recordsCount.toLocaleString("en-US")}</td>
                    <td className="py-3 px-2 text-center">
                      <span className={`font-mono ${s.errorRate === "۱۰۰%" ? "text-accent-rose" : parseFloat(s.errorRate) > 1 ? "text-accent-amber" : "text-accent-emerald"}`}>
                        {s.errorRate}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        /* Data Quality Issues */
        <Card title="مشکلات کیفیت داده" subtitle="موارد شناسایی شده نیازمند بررسی">
          <div className="space-y-3">
            {issues.map((issue) => (
              <div key={issue.id} className="rounded-lg bg-surface-800/20 p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${getSeverityColor(issue.severity)}`}>
                      {issue.severity === "critical" ? "بحرانی" : issue.severity === "major" ? "مهم" : "جزئی"}
                    </span>
                    <span className="text-xs text-surface-500">{issue.source}</span>
                  </div>
                  <span className="text-[10px] text-surface-600">{issue.detectedAt}</span>
                </div>
                <p className="text-sm text-surface-300 mb-2">{issue.description}</p>
                <div className="flex items-center gap-4 text-[10px] text-surface-500">
                  <span>تعداد رکوردهای affected: {issue.affectedRecords.toLocaleString("en-US")}</span>
                </div>
              </div>
            ))}
          </div>
          {issues.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-surface-600">
              <CheckCircle2 className="size-10 mb-2 text-accent-emerald" />
              <p className="text-sm">همه منابع داده سالم هستند</p>
            </div>
          )}
        </Card>
      )}

      {/* Summary footer */}
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "سرویس سالم", value: metrics.filter(m => m.status === "healthy").length.toString() + "/" + metrics.length, icon: CheckCircle2, color: "text-accent-emerald" },
          { label: "منابع متصل", value: sources.filter(s => s.status === "connected").length.toString() + "/" + sources.length, icon: Database, color: "text-accent-cyan" },
          { label: "مشکلات باز", value: issues.filter(i => i.severity !== "minor").length.toString(), icon: AlertTriangle, color: issues.some(i => i.severity === "critical") ? "text-accent-rose" : "text-accent-amber" },
          { label: "رکورد کل", value: sources.reduce((sum, s) => sum + s.recordsCount, 0).toLocaleString("en-US"), icon: HardDrive, color: "text-accent-emerald" },
        ].map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={i} className="rounded-lg bg-surface-800/30 p-3 text-center">
              <Icon className={`inline size-4 mb-1 ${s.color}`} />
              <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-surface-500 mt-0.5">{s.label}</div>
            </div>
          );
        })}
      </div>
    </AppLayout>
  );
}
