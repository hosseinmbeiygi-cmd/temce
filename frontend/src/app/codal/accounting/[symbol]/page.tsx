"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";

// ── Types ──────────────────────────────────────────────────────────

interface AccountingItem {
  label: string;
  values: Record<string, number>;
}

interface AccountingTable {
  table_index: number;
  headers: string[];
  row_count: number;
  items: AccountingItem[];
}

interface AccountingReport {
  symbol: string;
  filename: string;
  report_type: string;
  date: string;
  title: string;
  tables: AccountingTable[];
  table_count: number;
}

interface ReportMeta {
  symbol: string;
  report_type: string;
  report_type_label: string;
  date: string;
  filename: string;
}

interface AccountingSummary {
  symbol: string;
  total_reports: number;
  latest_reports: Record<string, {
    date: string;
    filename: string;
    label: string;
    items: Record<string, number>;
  }>;
}

interface RatioItem {
  key: string;
  label: string;
  formula: string;
  description: string;
  good_range: string;
  value: number;
  value_pct: number;
  numerator: number;
  denominator: number;
}

interface RatiosResponse {
  symbol: string;
  total_reports: number;
  classified_items: Record<string, number>;
  ratios: RatioItem[];
  ratio_count: number;
}

// ── Helpers ────────────────────────────────────────────────────────

function formatCurrency(val: number | null | undefined): string {
  if (val == null || val === 0) return "—";
  if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(1) + "T";
  if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(1) + "B";
  if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(1) + "M";
  if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(0) + "K";
  return val.toLocaleString();
}

function faNum(s: string): string {
  const digits: Record<string, string> = { "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴", "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹" };
  return s.replace(/[0-9]/g, (d) => digits[d] || d);
}

const REPORT_TYPE_COLORS: Record<string, string> = {
  "ن-۱۰": "bg-blue-500/20 text-blue-300 border-blue-500/30",
  "ن-۳۰": "bg-violet-500/20 text-violet-300 border-violet-500/30",
  "ن-۳۱": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

const REPORT_TYPE_ICONS: Record<string, string> = {
  "ن-۱۰": "📆",
  "ن-۳۰": "📋",
  "ن-۳۱": "📊",
};

function ReportTypeBadge({ type, label }: { type: string; label?: string }) {
  const color = REPORT_TYPE_COLORS[type] || "bg-surface-700 text-surface-400 border-surface-600";
  const icon = REPORT_TYPE_ICONS[type] || "📄";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-lg border ${color}`}>
      {icon} {label || type}
    </span>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function CodalAccountingPage() {
  const params = useParams();
  const symbol = (params?.symbol as string) || "";
  const decodedSymbol = decodeURIComponent(symbol);

  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedReport, setSelectedReport] = useState<string>("");

  // Fetch summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["codal-acct-summary", decodedSymbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: AccountingSummary }>(
        `/codal-accounting/${encodeURIComponent(decodedSymbol)}/financials`
      );
      return res?.data ?? null;
    },
    enabled: !!decodedSymbol,
  });

  // Fetch all reports for the symbol
  const { data: reports, isLoading: reportsLoading } = useQuery({
    queryKey: ["codal-acct-reports", decodedSymbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: ReportMeta[] }>(
        `/codal-accounting/${encodeURIComponent(decodedSymbol)}/reports`
      );
      return res?.data ?? [];
    },
    enabled: !!decodedSymbol,
  });

  // Group reports by type
  const reportTypes = useMemo(() => {
    if (!reports) return [];
    const typeMap: Record<string, { type: string; label: string; reports: ReportMeta[] }> = {};
    for (const r of reports) {
      const key = r.report_type || "سایر";
      if (!typeMap[key]) {
        typeMap[key] = { type: key, label: r.report_type_label || key, reports: [] };
      }
      typeMap[key].reports.push(r);
    }
    return Object.values(typeMap).sort((a, b) => b.reports.length - a.reports.length);
  }, [reports]);

  // Set default selected type
  const activeType = selectedType || (reportTypes[0]?.type ?? "");
  const activeTypeData = reportTypes.find((t) => t.type === activeType);

  // Set default selected report
  const activeReportName = selectedReport || (activeTypeData?.reports[0]?.filename ?? "");

  // Fetch detail for selected report
  const { data: reportDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["codal-acct-detail", decodedSymbol, activeReportName],
    queryFn: async () => {
      if (!activeReportName) return null;
      const res = await apiGet<{ success: boolean; data: AccountingReport }>(
        `/codal-accounting/${encodeURIComponent(decodedSymbol)}/report/${encodeURIComponent(activeReportName)}`
      );
      return res?.data ?? null;
    },
    enabled: !!activeReportName && !!decodedSymbol,
  });

  // Fetch ratios
  const { data: ratiosData, isLoading: ratiosLoading } = useQuery({
    queryKey: ["codal-acct-ratios", decodedSymbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: RatiosResponse }>(
        `/codal-accounting/${encodeURIComponent(decodedSymbol)}/ratios`
      );
      return res?.data ?? null;
    },
    enabled: !!decodedSymbol,
  });

  // Summary stats
  const totalReports = summary?.total_reports ?? 0;
  const summaryEntries = summary?.latest_reports ? Object.entries(summary.latest_reports) : [];

  if (!decodedSymbol) {
    return (
      <AppLayout title="حسابداری کدال" subtitle="انتخاب نماد">
        <div className="max-w-6xl mx-auto py-20 text-center text-surface-500">
          <p className="text-5xl mb-4">📒</p>
          <p className="text-lg">لطفاً یک نماد وارد کنید</p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title={`حسابداری ${decodedSymbol}`}
      subtitle="صورت‌های مالی و نسبت‌های حسابداری از گزارش‌های کدال"
    >
      <div className="max-w-6xl mx-auto space-y-5">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="glass-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary-600/20 flex items-center justify-center text-lg">📒</div>
              <div>
                <h1 className="text-xl font-bold text-surface-100">گزارشات حسابداری {decodedSymbol}</h1>
                <p className="text-sm text-surface-500 mt-0.5">
                  {totalReports > 0
                    ? `${faNum(String(totalReports))} گزارش از ${faNum(String(reportTypes.length))} نوع گزارش`
                    : "صورت‌های مالی استخراج شده از فایل‌های کدال"}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Link href={`/codal/analysis/${encodeURIComponent(decodedSymbol)}`}
                className="text-xs bg-surface-700 hover:bg-surface-600 text-surface-300 px-3 py-2 rounded-lg transition-colors">
                📊 تحلیل بنیادی
              </Link>
              <Link href={`/symbol/${encodeURIComponent(decodedSymbol)}`}
                className="text-xs bg-surface-700 hover:bg-surface-600 text-surface-300 px-3 py-2 rounded-lg transition-colors">
                صفحه نماد
              </Link>
            </div>
          </div>
        </div>

        {summaryLoading || reportsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1,2,3].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
          </div>
        ) : totalReports === 0 ? (
          <div className="text-center py-20 text-surface-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">هیچ گزارش حسابداری برای {decodedSymbol} یافت نشد</p>
            <p className="text-sm mt-2">داده‌های حسابداری فقط برای نمادهای موجود در دایرکتوری codal_excel_files قابل دسترسی است</p>
          </div>
        ) : (
          <>

            {/* ── Summary Cards ──────────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {summaryEntries.map(([type, data]) => (
                <button
                  key={type}
                  onClick={() => { setSelectedType(type); setSelectedReport(""); }}
                  className={`glass-card p-4 text-right hover:bg-surface-800/50 transition-all text-left ${
                    activeType === type ? "ring-2 ring-primary-500/50" : ""
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <ReportTypeBadge type={type} label={data.label} />
                  </div>
                  <p className="text-2xl font-bold text-surface-100 mt-2">
                    {faNum(String(Object.keys(data.items).length))}
                  </p>
                  <p className="text-xs text-surface-500 mt-1">آیتم مالی استخراج شده</p>
                  <p className="text-xs text-surface-600 mt-1 font-mono">{data.date}</p>
                </button>
              ))}
            </div>

            {/* ── Accounting Ratios Section ─────────────────────────────── */}
            {ratiosData && ratiosData.ratios.length > 0 && (
              <Card title="🧮 نسبت‌های حسابداری" subtitle="محاسبه شده از آخرین گزارش‌های مالی">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {ratiosData.ratios.map((ratio) => {
                    const isHealthy = ratio.key === "debt_to_equity"
                      ? ratio.value < 1
                      : ratio.key === "current_ratio"
                      ? ratio.value >= 1.5 && ratio.value <= 3
                      : ratio.value_pct > 10;
                    return (
                      <div
                        key={ratio.key}
                        className={`p-4 rounded-xl border transition-all ${
                          isHealthy
                            ? "bg-accent-emerald/5 border-accent-emerald/20"
                            : "bg-accent-amber/5 border-accent-amber/20"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-surface-300">{ratio.label}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                            isHealthy ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-amber/15 text-accent-amber"
                          }`}>
                            {isHealthy ? "✓ مطلوب" : "⚠ نیاز به بررسی"}
                          </span>
                        </div>
                        <p className={`text-2xl font-black font-mono ${
                          isHealthy ? "text-accent-emerald" : "text-accent-amber"
                        }`}>
                          {ratio.key === "roe" || ratio.key === "roa" || ratio.key === "gross_margin" || ratio.key === "net_margin" || ratio.key === "operating_margin"
                            ? `${ratio.value_pct.toFixed(1)}%`
                            : ratio.value.toFixed(2)}
                        </p>
                        <p className="text-xs text-surface-500 mt-1">{ratio.description}</p>
                        <div className="mt-2 pt-2 border-t border-surface-700/50 flex items-center justify-between text-[10px] text-surface-600">
                          <span>محدوده مطلوب: {ratio.good_range}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {ratiosData.classified_items && Object.keys(ratiosData.classified_items).length > 0 && (
                  <details className="mt-4">
                    <summary className="text-xs text-surface-500 cursor-pointer hover:text-surface-300 transition-colors">
                      آیتم‌های شناسایی شده ({Object.keys(ratiosData.classified_items).length})
                    </summary>
                    <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {Object.entries(ratiosData.classified_items).map(([key, val]) => (
                        <div key={key} className="flex items-center justify-between p-2 rounded-lg bg-surface-800/50 text-xs">
                          <span className="text-surface-400">{key}</span>
                          <span className="font-mono text-surface-200 font-bold">{val.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </Card>
            )}

            {/* ── Report Type Tabs ──────────────────────────────────────── */}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {reportTypes.map((rt) => (
                <button
                  key={rt.type}
                  onClick={() => { setSelectedType(rt.type); setSelectedReport(""); }}
                  className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    activeType === rt.type
                      ? "bg-primary-600 text-white shadow-lg"
                      : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}
                >
                  {REPORT_TYPE_ICONS[rt.type] || "📄"} {rt.label || rt.type}
                  <span className="mr-1.5 text-xs opacity-70">({faNum(String(rt.reports.length))})</span>
                </button>
              ))}
            </div>

            {/* ── Report Selector ────────────────────────────────────────── */}
            {activeTypeData && (
              <div className="glass-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs text-surface-500">انتخاب گزارش:</span>
                </div>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                  {activeTypeData.reports.map((r) => (
                    <button
                      key={r.filename}
                      onClick={() => setSelectedReport(r.filename)}
                      className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                        activeReportName === r.filename
                          ? "bg-primary-600/20 text-primary-300 border border-primary-500/30"
                          : "bg-surface-800 text-surface-400 hover:text-surface-200 border border-surface-700"
                      }`}
                    >
                      {r.date.replace(/_/g, "/")}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ── Report Detail ──────────────────────────────────────────── */}
            {detailLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-10 w-1/3 rounded-lg" />
                <Skeleton className="h-64 w-full rounded-xl" />
              </div>
            ) : reportDetail ? (
              reportDetail.tables.map((table, ti) => (
                <Card key={ti} title={`📋 جدول ${faNum(String(ti + 1))}`} subtitle={`${faNum(String(table.row_count))} ردیف`}>
                  {table.items.length === 0 ? (
                    <p className="text-surface-500 text-sm text-center py-6">داده‌ای در این جدول وجود ندارد</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-right text-sm">
                        <thead>
                          <tr className="text-surface-500 border-b border-surface-700 text-xs">
                            <th className="pb-2 px-3 font-medium">ردیف</th>
                            <th className="pb-2 px-3 font-medium">شرح</th>
                            {table.headers.slice(1).map((h, hi) => (
                              <th key={hi} className="pb-2 px-3 font-medium text-left">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {table.items.map((item, ri) => {
                            const valEntries = Object.entries(item.values);
                            return (
                              <tr key={ri} className={`border-b border-surface-800/50 hover:bg-white/5 transition-colors ${
                                item.label === "جمع" || item.label === "مجموع" ? "bg-primary-600/5 font-bold" : ""
                              }`}>
                                <td className="py-2.5 px-3 text-xs text-surface-500">{faNum(String(ri + 1))}</td>
                                <td className={`py-2.5 px-3 ${item.label === "جمع" || item.label === "مجموع" ? "text-primary-300 font-bold" : "text-surface-200"}`}>
                                  {item.label}
                                </td>
                                {table.headers.slice(1).map((h, hi) => {
                                  const val = valEntries.find(([k]) => k === h)?.[1];
                                  return (
                                    <td key={hi} className={`py-2.5 px-3 font-mono ${
                                      val && val > 0 ? "text-accent-emerald" : val && val < 0 ? "text-accent-rose" : "text-surface-100"
                                    } ${item.label === "جمع" || item.label === "مجموع" ? "font-bold" : ""}`}>
                                      {val != null ? faNum(val.toLocaleString()) : "—"}
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              ))
            ) : (
              <div className="text-center py-12 text-surface-500">
                <p className="text-4xl mb-3">📄</p>
                <p>یک گزارش را انتخاب کنید</p>
              </div>
            )}

            {/* ── Summary from Latest Reports ─────────────────────────────── */}
            {summaryEntries.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {summaryEntries.map(([type, data]) => (
                  <Card key={type} title={`${REPORT_TYPE_ICONS[type] || "📄"} ${data.label}`} subtitle={`آخرین گزارش: ${data.date}`}>
                    {Object.keys(data.items).length === 0 ? (
                      <p className="text-surface-500 text-sm text-center py-6">داده‌ای استخراج نشد</p>
                    ) : (
                      <div className="space-y-1">
                        {Object.entries(data.items).slice(0, 20).map(([label, value], idx) => (
                          <div key={idx} className="flex items-center justify-between py-1.5 border-b border-surface-800/50 last:border-0">
                            <span className="text-sm text-surface-300 truncate ml-2">{label}</span>
                            <span className={`font-mono text-sm font-bold shrink-0 ${
                              value > 0 ? "text-accent-emerald" : value < 0 ? "text-accent-rose" : "text-surface-400"
                            }`}>
                              {formatCurrency(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            )}

            {/* ── All Reports List ────────────────────────────────────────── */}
            {reportTypes.length > 0 && (
              <Card title="📚 همه گزارش‌ها" subtitle={`کل گزارش‌های موجود: ${faNum(String(totalReports))}`}>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {reports?.map((r, i) => {
                    const color = REPORT_TYPE_COLORS[r.report_type] || "bg-surface-700 text-surface-400";
                    return (
                      <button
                        key={r.filename}
                        onClick={() => { setSelectedType(r.report_type); setSelectedReport(r.filename); }}
                        className={`w-full text-right flex items-center justify-between p-2.5 rounded-lg hover:bg-surface-800/50 transition-colors ${
                          activeReportName === r.filename ? "bg-surface-800" : ""
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs text-surface-600 w-6">{faNum(String(i + 1))}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${color}`}>
                            {r.report_type_label || r.report_type}
                          </span>
                          <span className="text-xs text-surface-400 font-mono" dir="ltr">
                            {r.date.replace(/_/g, "/")}
                          </span>
                        </div>
                        <span className="text-[10px] text-surface-600 truncate max-w-[200px]">{r.filename}</span>
                      </button>
                    );
                  })}
                </div>
              </Card>
            )}
          </>
        )}

        {/* ── Quick Links ────────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/codal" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← اطلاعیه‌های کدال</Link>
          <Link href={`/codal/analysis/${encodeURIComponent(decodedSymbol)}`} className="text-accent-emerald/80 hover:text-accent-emerald transition-colors px-2 py-1">📊 تحلیل بنیادی</Link>
          <Link href={`/symbol/${encodeURIComponent(decodedSymbol)}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">نماد {decodedSymbol}</Link>
        </div>
      </div>
    </AppLayout>
  );
}
