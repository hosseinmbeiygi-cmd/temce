"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface AnomalyItem {
  symbol: string;
  type: "price_spike_up" | "price_spike_down" | "volume_spike";
  severity: "high" | "medium" | "low";
  date: string;
  value: number;
  expected: number;
  z_score: number;
  volume: number;
  price?: number;
  description: string;
}

interface AnomalySummary {
  total_symbols_scanned: number;
  symbols_with_data: number;
  symbols_with_anomalies: number;
  high_severity: number;
  medium_severity: number;
  price_anomalies: number;
  volume_anomalies: number;
}

interface AnomalyResponse {
  items: AnomalyItem[];
  total: number;
  summary: AnomalySummary;
  config: {
    price_threshold: number;
    volume_threshold: number;
    lookback_days: number;
  };
}

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatNum(v: number): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function typeIcon(type: string): string {
  switch (type) {
    case "price_spike_up": return "📈";
    case "price_spike_down": return "📉";
    case "volume_spike": return "📊";
    default: return "⚠️";
  }
}

function typeLabel(type: string): string {
  switch (type) {
    case "price_spike_up": return "جهش قیمت";
    case "price_spike_down": return "سقوط قیمت";
    case "volume_spike": return "جهش حجم";
    default: return type;
  }
}

function severityColor(severity: string): string {
  switch (severity) {
    case "high": return "bg-accent-rose/15 text-accent-rose border-accent-rose/30";
    case "medium": return "bg-accent-amber/15 text-accent-amber border-accent-amber/30";
    case "low": return "bg-surface-600/30 text-surface-400 border-surface-700";
    default: return "bg-surface-600/30 text-surface-400 border-surface-700";
  }
}

const SEVERITY_FILTERS = [
  { key: "all", label: "همه" },
  { key: "high", label: "شدید" },
  { key: "medium", label: "متوسط" },
  { key: "low", label: "ضعیف" },
];

const TYPE_FILTERS = [
  { key: "all", label: "همه انواع" },
  { key: "price", label: "قیمت" },
  { key: "volume", label: "حجم" },
];

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function AnomaliesPage() {
  const [severityFilter, setSeverityFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["anomalies"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: AnomalyResponse }>(
        "/anomalies?limit=60&price_threshold=2.5&volume_threshold=2.0"
      );
      if (!res?.success) throw new Error("Failed to fetch anomalies");
      return res.data;
    },
    refetchInterval: 120_000,
  });

  const items = data?.items ?? [];
  const summary = data?.summary;

  // ── Filters ──
  const filtered = useMemo(() => {
    let list = items;

    if (severityFilter !== "all") {
      list = list.filter((a) => a.severity === severityFilter);
    }
    if (typeFilter === "price") {
      list = list.filter((a) => a.type.includes("price"));
    } else if (typeFilter === "volume") {
      list = list.filter((a) => a.type === "volume_spike");
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((a) => a.symbol.toLowerCase().includes(q));
    }

    return list;
  }, [items, severityFilter, typeFilter, search]);

  // ── Group by symbol ──
  const grouped = useMemo(() => {
    const map = new Map<string, AnomalyItem[]>();
    for (const item of filtered) {
      if (!map.has(item.symbol)) map.set(item.symbol, []);
      map.get(item.symbol)!.push(item);
    }
    return Array.from(map.entries()).sort(
      (a, b) => b[1].length - a[1].length
    );
  }, [filtered]);

  return (
    <AppLayout
      title="🚨 تشخیص ناهنجاری"
      subtitle="شناسایی جهش‌های قیمت و حجم با تحلیل Z-Score"
    >
      {/* ── Summary cards ── */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mb-5">
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-rose">{summary.high_severity}</p>
            <p className="text-xs text-surface-500">شدید</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-accent-amber">{summary.medium_severity}</p>
            <p className="text-xs text-surface-500">متوسط</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-surface-100">{summary.price_anomalies}</p>
            <p className="text-xs text-surface-500">ناهنجاری قیمت</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-primary-300">{summary.volume_anomalies}</p>
            <p className="text-xs text-surface-500">ناهنجاری حجم</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-surface-200">{summary.symbols_with_anomalies}</p>
            <p className="text-xs text-surface-500">نمادهای دارای ناهنجاری</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-xl font-black text-surface-400">{summary.total_symbols_scanned}</p>
            <p className="text-xs text-surface-500">بررسی شده</p>
          </div>
          <div className="glass-card p-3 text-center">
            <p className="text-lg font-black font-mono text-surface-500">{data?.config?.price_threshold}σ / {data?.config?.volume_threshold}σ</p>
            <p className="text-xs text-surface-500">آستانه Z-Score</p>
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجوی نماد..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-44"
        />

        <div className="flex gap-1 flex-wrap">
          {SEVERITY_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setSeverityFilter(f.key)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${
                severityFilter === f.key
                  ? "bg-primary-600 text-white"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="flex gap-1 flex-wrap">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setTypeFilter(f.key)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${
                typeFilter === f.key
                  ? "bg-primary-600 text-white"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => refetch()}
          className="p-1.5 rounded-lg bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
          title="بروزرسانی"
        >
          <span className="material-icons text-sm">refresh</span>
        </button>

        <span className="text-xs text-surface-500">
          {filtered.length} ناهنجاری
        </span>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {isError && !isLoading && (
        <div className="glass-card p-12 text-center text-accent-rose">
          <p className="text-5xl mb-3">⚠️</p>
          <p className="font-bold">خطا در تشخیص ناهنجاری</p>
          <p className="text-sm mt-1 text-surface-500">
            داده کافی در جدول quotes موجود نیست
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-200 rounded-lg text-sm transition-colors"
          >
            تلاش مجدد
          </button>
        </div>
      )}

      {/* ── Empty ── */}
      {!isLoading && !isError && filtered.length === 0 && (
        <div className="glass-card p-12 text-center text-surface-500">
          <p className="text-5xl mb-3">✅</p>
          <p className="font-bold">ناهنجاری‌ای یافت نشد</p>
          <p className="text-sm mt-1">
            {summary
              ? summary.total_symbols_scanned + " نماد بررسی شدند و ناهنجاری قابل توجهی یافت نشد"
              : "داده‌ای برای بررسی موجود نیست"}
          </p>
        </div>
      )}

      {/* ── Anomaly cards (grouped by symbol) ── */}
      {!isLoading && !isError && grouped.length > 0 && (
        <div className="space-y-3">
          {grouped.map(([symbol, anomalies]) => {
            const maxSeverity = anomalies.some((a) => a.severity === "high")
              ? "high"
              : anomalies.some((a) => a.severity === "medium")
              ? "medium"
              : "low";
            return (
              <div
                key={symbol}
                className="glass-card overflow-hidden"
              >
                {/* Header */}
                <Link
                  href={`/symbol/${encodeURIComponent(symbol)}`}
                  className="flex items-center justify-between p-3 bg-surface-800/50 hover:bg-surface-800/70 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-bold text-surface-100">{symbol}</span>
                    <span className="text-xs text-surface-500">
                      {anomalies.length} ناهنجاری
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                        severityColor(maxSeverity)
                      }`}
                    >
                      {maxSeverity === "high"
                        ? "شدید"
                        : maxSeverity === "medium"
                        ? "متوسط"
                        : "ضعیف"}
                    </span>
                    <span className="material-icons text-surface-500 text-sm">
                      chevron_left
                    </span>
                  </div>
                </Link>

                {/* Anomaly list */}
                <div className="divide-y divide-surface-800/30">
                  {anomalies.map((a, i) => (
                    <div
                      key={`${a.date}-${a.type}-${i}`}
                      className="flex items-center gap-3 p-3 hover:bg-white/[0.02] transition-colors text-xs"
                    >
                      <span className="text-base shrink-0">{typeIcon(a.type)}</span>

                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold shrink-0 ${
                          severityColor(a.severity)
                        }`}
                      >
                        {a.severity === "high" ? "شدید" : a.severity === "medium" ? "متوسط" : "ضعیف"}
                      </span>

                      <span className="text-surface-400 shrink-0 font-mono w-[80px]">
                        {a.date?.slice(5) || "—"}
                      </span>

                      <span className="font-bold text-surface-300 shrink-0 w-[70px]">
                        {typeLabel(a.type)}
                      </span>

                      <span className="text-surface-200 font-mono shrink-0 w-[60px] text-right">
                        {a.type.includes("price") || a.type === "volume_spike"
                          ? formatNum(a.value)
                          : "—"}
                      </span>

                      <span className="text-surface-600 shrink-0">vs</span>

                      <span className="text-surface-500 font-mono shrink-0 w-[60px] text-right">
                        {formatNum(a.expected)}
                      </span>

                      <span
                        className={`font-mono font-bold shrink-0 w-[50px] text-right ${
                          a.z_score > 0 ? "text-accent-rose" : "text-accent-emerald"
                        }`}
                      >
                        {a.z_score > 0 ? "+" : ""}
                        {a.z_score?.toFixed(1)}σ
                      </span>

                      <span className="text-surface-500 flex-1 truncate hidden md:block">
                        {a.description}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
