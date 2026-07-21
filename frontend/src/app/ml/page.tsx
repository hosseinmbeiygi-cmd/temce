"use client";

import React, { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";

import MLBacktestTab from "@/components/charts/MLBacktestTab";

// ══════════════════════════════════════════════════════════════════════════════
// TYPES
// ══════════════════════════════════════════════════════════════════════════════

interface TrainRun {
  id: string; experiment_name: string; model_type: string;
  symbol?: string; symbols?: string[]; status: string;
  metrics: Record<string, number>; train_samples?: number;
  feature_names?: string[]; created_at?: string;
}

interface TrainAllResult {
  model_type: string; total_symbols: number; successful: number;
  failed: number; total_duration_seconds: number;
  best_r2: number | null; best_symbol: string | null;
  avg_r2: number | null;
  results: Array<{
    symbol: string; success: boolean; run_id?: string;
    metrics?: Record<string, number>; error?: string; duration_seconds: number;
  }>;
}

interface ComparisonItem {
  model_type: string; symbol: string;
  metrics: Record<string, number>; version?: string; run_id?: string;
}

interface DataPreview {
  symbol: string; has_instrument: boolean;
  ohlcv_rows: number; history_rows: number;
  history_start: string | null; history_end: string | null;
  trade_flow_rows: number; trade_rows: number;
  estimated_features: number;
}

interface PredictionItem {
  symbol: string; prediction: number; confidence: number;
  direction: "up" | "down" | "neutral";
  model_type: string; created_at?: string;
}

// ══════════════════════════════════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════════════════════════════════

const DATA_SOURCES = [
  { value: "auto", label: "Auto (Quote → Historical)", icon: "🤖", desc: "اولویت با QuoteModel، fallback به Historical" },
  { value: "historical", label: "HistoricalDailyModel", icon: "📜", desc: "داده‌های تاریخی قیمت روزانه" },
  { value: "ohlcv", label: "QuoteModel (OHLCV)", icon: "📊", desc: "داده‌های لحظه‌ای قیمت" },
];

const FEATURE_GROUPS = [
  { value: "price", label: "قیمت", icon: "💵" },
  { value: "technical", label: "تکنیکال", icon: "📈" },
  { value: "trades", label: "حقیقی/حقوقی", icon: "🔄" },
  { value: "microstructure", label: "ریزساختار", icon: "🔬" },
  { value: "all", label: "همه", icon: "📊" },
];

const ALL_MODELS = [
  "xgboost", "lightgbm", "catboost", "random_forest",
  "extra_trees", "hist_gradient_boosting", "bayesian_ridge", "huber_regressor",
];

const MODEL_META: Record<string, { icon: string; color: string; desc: string }> = {
  xgboost:   { icon: "⚡",  color: "text-accent-emerald",  desc: "Gradient Boosting سریع و دقیق" },
  lightgbm:  { icon: "🚀",  color: "text-accent-cyan",     desc: "سبک‌وزن با مصرف حافظه کم" },
  catboost:  { icon: "🐱",  color: "text-accent-amber",    desc: "بهینه برای داده‌های دسته‌بندی" },
  random_forest: { icon: "🌲", color: "text-accent-emerald", desc: "ensemble درختان تصمیم" },
  extra_trees:{ icon: "🌳",  color: "text-accent-emerald", desc: "Extra randomized trees" },
  hist_gradient_boosting: { icon: "📈", color: "text-primary-400", desc: "Gradient Boosting با histogram-based" },
  bayesian_ridge: { icon: "📐", color: "text-accent-amber", desc: "رگرسیون خطی بیزی" },
  huber_regressor:{ icon: "🛡️", color: "text-accent-rose", desc: "مقاوم در برابر outlier" },
};

const TASK_TYPES = [
  { value: "regression", label: "رگرسیون", icon: "📈", desc: "پیش‌بینی درصد تغییر قیمت" },
  { value: "classification", label: "طبقه‌بندی", icon: "🎯", desc: "پیش‌بینی جهت حرکت (صعود/نزول)" },
];

// ══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════════════════════

function useAllSymbols() {
  return useQuery({
    queryKey: ["ml-all-symbols"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { items: { symbol: string }[] } }>("/instruments?page_size=10000");
      return (res?.data?.items ?? []).map(s => s.symbol).filter(Boolean);
    },
    staleTime: 60_000,
  });
}

function InfoCard({ icon, label, value, color, subtitle }: {
  icon: string; label: string; value: string | number; color?: string; subtitle?: string;
}) {
  return (
    <div className="glass-card p-3.5 text-center hover:scale-[1.02] transition-transform duration-200">
      <p className={`text-2xl font-black font-mono ${color || "text-surface-100"}`}>
        {typeof value === "number" ? value.toLocaleString("fa-IR") : value}
      </p>
      <p className="text-[10px] text-surface-500 mt-0.5">{icon} {label}</p>
      {subtitle && <p className="text-[8px] text-surface-600 mt-0.5">{subtitle}</p>}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running:    "bg-accent-amber/15 text-accent-amber animate-pulse",
    completed:  "bg-accent-emerald/15 text-accent-emerald",
    failed:     "bg-accent-rose/15 text-accent-rose",
    cancelled:  "bg-surface-600/30 text-surface-400",
  };
  return <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${colors[status] || colors.failed}`}>{status}</span>;
}

function MiniBar({ value, maxVal, color }: { value: number; maxVal: number; color?: string }) {
  const pct = maxVal > 0 ? Math.max(2, Math.abs(value) / maxVal * 100) : 0;
  return (
    <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
      <div className={`h-full rounded-full transition-all duration-500 ${color || "bg-accent-cyan"}`}
        style={{ width: `${pct}%` }} />
    </div>
  );
}

const fmtPct = (v: number) => (v >= 0 ? "+" : "") + (v * 100).toFixed(2) + "%";

// ══════════════════════════════════════════════════════════════════════════════
// TAB 0: DASHBOARD — Overview + stats + performance heatmap
// ══════════════════════════════════════════════════════════════════════════════

function DashboardTab() {
  const { data: allSymbols = [] } = useAllSymbols();

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ["ml-runs-limited"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: TrainRun[] }>("/ml/runs?limit=100");
      return r?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  const { data: comparisons = [] } = useQuery({
    queryKey: ["ml-comparison"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: ComparisonItem[] }>("/ml/comparison");
      return r?.data ?? [];
    },
    refetchInterval: 60_000,
  });

  const { data: predictions = [] } = useQuery({
    queryKey: ["ml-predictions"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: PredictionItem[] }>("/ml/predictions?limit=500");
      return r?.data ?? [];
    },
    refetchInterval: 60_000,
  });

  // Computed stats
  const totalRuns = runs?.length ?? 0;
  const completedRuns = runs?.filter(r => r.status === "completed").length ?? 0;
  const failedRuns = runs?.filter(r => r.status === "failed").length ?? 0;
  const totalPredictions = predictions?.length ?? 0;
  const totalComparisons = comparisons?.length ?? 0;

  const trainedSymbols = new Set<string>();
  runs?.forEach(r => {
    if (r.symbol) trainedSymbols.add(r.symbol);
    r.symbols?.forEach(s => trainedSymbols.add(s));
  });

  // Best model performance
  const bestComparison = comparisons?.length
    ? [...comparisons].sort((a, b) => (b.metrics?.mean_r2 ?? -999) - (a.metrics?.mean_r2 ?? -999))[0]
    : null;

  // Average R² across all comparisons
  const avgR2 = comparisons?.length
    ? comparisons.reduce((s, c) => s + (c.metrics?.mean_r2 ?? 0), 0) / comparisons.length
    : 0;

  // Model performance heatmap data
  const modelsInData = Array.from(new Set(comparisons?.map(c => c.model_type) ?? []));
  const heatmapData = modelsInData.map(mt => {
    const items = comparisons.filter(c => c.model_type === mt);
    const avgR2Model = items.reduce((s, c) => s + (c.metrics?.mean_r2 ?? 0), 0) / items.length;
    const avgMAE = items.reduce((s, c) => s + (c.metrics?.mean_mae ?? 0), 0) / items.length;
    const posRate = items.length > 0 ? items.filter(c => (c.metrics?.mean_r2 ?? 0) >= 0).length / items.length : 0;
    return { model_type: mt, avg_r2: avgR2Model, avg_mae: avgMAE, count: items.length, pos_rate: posRate };
  }).sort((a, b) => b.avg_r2 - a.avg_r2);

  // Recent runs timeline (last 15)
  const recentRuns = (runs ?? []).slice(0, 15);

  // R² heatmap color
  const r2Color = (v: number) => {
    if (v >= 0.1) return "bg-accent-emerald/30 text-accent-emerald";
    if (v >= 0) return "bg-accent-emerald/15 text-accent-emerald";
    if (v >= -0.1) return "bg-accent-rose/15 text-accent-rose";
    return "bg-accent-rose/30 text-accent-rose";
  };

  return (
    <div className="space-y-5">
      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <InfoCard icon="📊" label="کل نمادها" value={allSymbols.length} color="text-primary-300"
          subtitle={`${trainedSymbols.size} آموزش‌دیده`} />
        <InfoCard icon="🧠" label="آموزش‌ها" value={totalRuns} color="text-surface-100"
          subtitle={`${completedRuns} موفق`} />
        <InfoCard icon="🎯" label="پیش‌بینی‌ها" value={totalPredictions} color="text-accent-cyan" />
        <InfoCard icon="📈" label="مقایسه‌ها" value={totalComparisons} color="text-surface-200" />
        <InfoCard icon="🏆" label="بهترین R²"
          value={bestComparison ? bestComparison.metrics?.mean_r2?.toFixed(4) ?? "—" : "—"}
          color="text-accent-emerald"
          subtitle={bestComparison ? `${bestComparison.model_type}/${bestComparison.symbol}` : ""} />
        <InfoCard icon="📉" label="میانگین R²"
          value={comparisons.length > 0 ? avgR2.toFixed(4) : "—"}
          color={avgR2 >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Model Performance Heatmap ── */}
        <Card title="🗺️ نقشه عملکرد مدل‌ها" subtitle={`${modelsInData.length} مدل • ${totalComparisons} مقایسه`}>
          {heatmapData.length === 0 ? (
            <p className="text-surface-500 text-sm text-center py-8">هنوز مدلی مقایسه نشده — ابتدا آموزش دهید</p>
          ) : (
            <div className="space-y-2">
              {heatmapData.map(hd => (
                <div key={hd.model_type} className="flex items-center gap-2">
                  <span className="text-[10px] text-surface-300 w-28 truncate font-bold" title={hd.model_type}>
                    {MODEL_META[hd.model_type]?.icon || "🔧"} {hd.model_type}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-5 bg-surface-800 rounded-lg overflow-hidden" dir="ltr">
                        <div className={`h-full rounded-lg transition-all duration-700 ${r2Color(hd.avg_r2)}`}
                          style={{ width: `${Math.min(100, Math.max(5, (hd.avg_r2 + 0.3) * 100))}%` }} />
                      </div>
                      <span className={`text-[10px] font-mono w-14 text-left ${(hd.avg_r2) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {hd.avg_r2 >= 0 ? "+" : ""}{hd.avg_r2.toFixed(4)}
                      </span>
                    </div>
                  </div>
                  <span className="text-[9px] text-surface-500 w-16 text-center">
                    {hd.count} نماد • {(hd.pos_rate * 100).toFixed(0)}%+
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* ── Recent Training Runs Timeline ── */}
        <Card title="⏱️ آخرین آموزش‌ها" subtitle={`${totalRuns} آموزش`}>
          {runsLoading ? (
            <Skeleton className="h-48 w-full rounded-xl" />
          ) : recentRuns.length === 0 ? (
            <p className="text-surface-500 text-sm text-center py-8">هنوز آموزشی اجرا نشده</p>
          ) : (
            <div className="space-y-1 max-h-[320px] overflow-y-auto">
              {recentRuns.map(run => (
                <div key={run.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface-800/20 transition-colors">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${
                      run.status === "completed" ? "bg-accent-emerald" :
                      run.status === "failed" ? "bg-accent-rose" : "bg-accent-amber"
                    }`} />
                    <div className="min-w-0">
                      <p className="text-[10px] text-surface-300 font-bold truncate">
                        {MODEL_META[run.model_type]?.icon || "🔧"} {run.model_type}
                        <span className="text-surface-500 font-normal mx-1">•</span>
                        <span className="text-surface-400 font-normal">{run.symbol || (run.symbols || []).slice(0, 3).join(", ")}</span>
                      </p>
                      {run.created_at && (
                        <p className="text-[8px] text-surface-600">{run.created_at.slice(0, 16).replace("T", " ")}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatusBadge status={run.status} />
                    {run.metrics?.mean_r2 != null && (
                      <span className={`text-[10px] font-mono ${run.metrics.mean_r2 >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {run.metrics.mean_r2 >= 0 ? "+" : ""}{run.metrics.mean_r2.toFixed(4)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Feature Groups Usage ── */}
      {totalRuns > 0 && (
        <Card title="🧩 توزیع گروه ویژگی‌ها" subtitle="گروه‌های ویژگی استفاده‌شده در آموزش‌ها">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {FEATURE_GROUPS.filter(fg => fg.value !== "all").map(fg => {
              const count = runs?.filter(r =>
                r.feature_names?.some(fn => {
                  if (fg.value === "price") return fn.startsWith("ma_") || fn.startsWith("vol_") || fn.startsWith("ret_") || fn.startsWith("range_");
                  if (fg.value === "technical") return fn.startsWith("rsi") || fn.startsWith("macd") || fn.startsWith("atr") || fn.startsWith("squeeze");
                  if (fg.value === "trades") return fn.startsWith("real_") || fn.startsWith("legal_") || fn.startsWith("buy_sell") || fn.startsWith("smart_money");
                  if (fg.value === "microstructure") return fn.startsWith("vwap") || fn.startsWith("trade_count") || fn.startsWith("trade_intensity") || fn.startsWith("price_efficiency");
                  return false;
                })
              ).length ?? 0;
              return (
                <div key={fg.value} className="glass-card p-3 text-center">
                  <p className="text-2xl mb-1">{fg.icon}</p>
                  <p className="text-lg font-black text-surface-200">{count}</p>
                  <p className="text-[9px] text-surface-500">{fg.label}</p>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 1: DATA MINING — Data quality & availability
// ══════════════════════════════════════════════════════════════════════════════

function DataMiningTab() {
  const { data: allSymbols = [] } = useAllSymbols();
  const [previewSymbol, setPreviewSymbol] = useState("فولاد");
  const [previewData, setPreviewData] = useState<DataPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const loadPreview = useCallback(async (sym: string) => {
    setLoadingPreview(true);
    try {
      const res = await apiGet<{ success: boolean; data: DataPreview }>(`/ml/data-preview/${encodeURIComponent(sym)}`);
      setPreviewData(res?.data ?? null);
    } catch { setPreviewData(null); }
    setLoadingPreview(false);
  }, []);

  // Stats from all symbols
  const { data: runs } = useQuery({
    queryKey: ["ml-runs-limited"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: TrainRun[] }>("/ml/runs?limit=50");
      return r?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  const totalSymbols = allSymbols.length;
  const totalRuns = runs?.length ?? 0;
  const completedRuns = runs?.filter(r => r.status === "completed").length ?? 0;
  const failedRuns = runs?.filter(r => r.status === "failed").length ?? 0;

  // Find symbols with successful runs
  const trainedSymbols = new Set<string>();
  runs?.forEach(r => {
    if (r.symbol) trainedSymbols.add(r.symbol);
    r.symbols?.forEach(s => trainedSymbols.add(s));
  });

  // Auto-load preview for default symbol on mount
  React.useEffect(() => { loadPreview(previewSymbol); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-5">
      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <InfoCard icon="📊" label="کل نمادها" value={totalSymbols} color="text-primary-300"
          subtitle={`${totalSymbols} نماد در دیتابیس`} />
        <InfoCard icon="🎯" label="آموزش‌ها" value={totalRuns} color="text-surface-100"
          subtitle={`${completedRuns} موفق, ${failedRuns} ناموفق`} />
        <InfoCard icon="✅" label="آموزش دیده" value={trainedSymbols.size} color="text-accent-emerald"
          subtitle={`از ${totalSymbols} نماد`} />
        <InfoCard icon="📈" label="داده تاریخی" value="4,597+" color="text-accent-amber"
          subtitle="ردیف برای فولاد" />
      </div>

      {/* Data Preview */}
      <div className="mb-5">
        <Card title="🔍 پیش‌نمایش داده نماد" subtitle="مشاهده موجودی داده و ویژگی‌های یک نماد خاص">
          <div className="flex gap-2 mb-4">
            <select value={previewSymbol} onChange={e => { setPreviewSymbol(e.target.value); loadPreview(e.target.value); }}
              className="flex-1 bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500">
              {allSymbols.slice(0, 200).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={() => loadPreview(previewSymbol)}
              className="px-4 py-2 bg-primary-600/20 text-primary-400 border border-primary-600/30 rounded-lg text-xs font-bold hover:bg-primary-600/30 transition-all">
              🔍 بررسی
            </button>
          </div>

          {loadingPreview ? (
            <Skeleton className="h-32 w-full rounded-xl" />
          ) : previewData ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.history_rows > 0 ? "text-accent-emerald" : "text-surface-500"} ${true ? "" : ""}`}>
                  {previewData.history_rows.toLocaleString("fa-IR")}
                </p>
                <p className="text-[9px] text-surface-500">📜 ردیف تاریخچه</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.ohlcv_rows > 0 ? "text-accent-emerald" : "text-surface-500"}`}>
                  {previewData.ohlcv_rows.toLocaleString("fa-IR")}
                </p>
                <p className="text-[9px] text-surface-500">📊 ردیف OHLCV</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.history_start ? "text-surface-200" : "text-surface-500"}`}>
                  {previewData.history_start?.slice(0, 10) || "—"}
                </p>
                <p className="text-[9px] text-surface-500">📅 شروع تاریخچه</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.history_end ? "text-surface-200" : "text-surface-500"}`}>
                  {previewData.history_end?.slice(0, 10) || "—"}
                </p>
                <p className="text-[9px] text-surface-500">📅 پایان تاریخچه</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.trade_flow_rows > 0 ? "text-accent-emerald" : "text-surface-500"}`}>
                  {previewData.trade_flow_rows.toLocaleString("fa-IR")}
                </p>
                <p className="text-[9px] text-surface-500">🔄 جریان حقیقی/حقوقی</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.trade_rows > 0 ? "text-accent-emerald" : "text-surface-500"}`}>
                  {previewData.trade_rows.toLocaleString("fa-IR")}
                </p>
                <p className="text-[9px] text-surface-500">🔬 ریزمعاملات</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className="text-lg font-black font-mono text-surface-200">
                  {previewData.estimated_features}
                </p>
                <p className="text-[9px] text-surface-500">🧮 ویژگی‌های قابل استخراج</p>
              </div>
              <div className="bg-surface-800/50 rounded-xl p-3 text-center">
                <p className={`text-lg font-black font-mono ${previewData.has_instrument ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {previewData.has_instrument ? "✅" : "❌"}
                </p>
                <p className="text-[9px] text-surface-500">🔗 اتصال به Instrument</p>
              </div>
            </div>
          ) : (
            <p className="text-surface-500 text-sm text-center py-6">یک نماد انتخاب کنید و دکمه بررسی را بزنید</p>
          )}
        </Card>
      </div>

      {/* Recent Runs */}
      <Card title="⚙️ آخرین آموزش‌ها" actions={
        <span className="text-[10px] text-surface-600">{runs?.length ?? 0} رکورد</span>
      }>
        {!runs ? (
          <Skeleton className="h-40 w-full rounded-xl" />
        ) : runs.length === 0 ? (
          <p className="text-surface-500 text-sm text-center py-6">هنوز آموزشی اجرا نشده</p>
        ) : (
          <div className="space-y-1 max-h-[320px] overflow-y-auto">
            {runs.slice(0, 20).map(run => (
              <div key={run.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface-800/20 transition-colors">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${
                    run.status === "completed" ? "bg-accent-emerald" :
                    run.status === "failed" ? "bg-accent-rose" : "bg-accent-amber"
                  }`} />
                  <span className="text-[10px] text-surface-400 font-mono truncate max-w-[150px]">{run.model_type}</span>
                  <span className="text-[10px] text-surface-500">{run.symbol || (run.symbols || []).join(", ")}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-[9px]">
                  <StatusBadge status={run.status} />
                  {run.metrics?.mean_r2 != null && (
                    <span className={`font-mono ${run.metrics.mean_r2 >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      R²: {run.metrics.mean_r2.toFixed(4)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 2: TRAINING — Full training pipeline
// ══════════════════════════════════════════════════════════════════════════════

function TrainingTab() {
  const queryClient = useQueryClient();
  const { data: allSymbols = [] } = useAllSymbols();

  // Form state
  const [dataSource, setDataSource] = useState("auto");
  const [taskType, setTaskType] = useState("regression");
  const [featureGroups, setFeatureGroups] = useState<string[]>(["price", "technical"]);
  const [selectedModels, setSelectedModels] = useState<string[]>(["xgboost"]);
  const [singleSymbol, setSingleSymbol] = useState("فولاد");
  const [nSplits, setNSplits] = useState(3);

  // Results
  const [allResults, setAllResults] = useState<{ model: string; result: TrainAllResult }[]>([]);
  const [trainCount, setTrainCount] = useState(0);

  // Mutations
  const trainSingle = useMutation({
    mutationFn: (data: Record<string, unknown>) => apiPost("/ml/train", data),
    retry: false,
    onSuccess: (res: any) => {
      toast.success(res?.data?.message || "✅ آموزش موفق");
      queryClient.invalidateQueries({ queryKey: ["ml-runs"] });
      queryClient.invalidateQueries({ queryKey: ["ml-runs-limited"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const trainAllMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => apiPost<{ success: boolean; data: TrainAllResult }>("/ml/train-all", data),
    retry: false,
    onSuccess: (res) => {
      const d = res?.data;
      if (!d) return;
      setAllResults(prev => [...prev, { model: d.model_type, result: d }]);
      setTrainCount(prev => prev + 1);
      queryClient.invalidateQueries({ queryKey: ["ml-runs"] });
      queryClient.invalidateQueries({ queryKey: ["ml-comparison"] });
      queryClient.invalidateQueries({ queryKey: ["ml-runs-limited"] });
    },
    onError: (err: Error) => {
      toast.error(err.message);
      setTrainCount(prev => prev + 1);
    },
  });

  const isTraining = trainAllMutation.isPending || trainSingle.isPending;

  const toggleModel = (m: string) => {
    setSelectedModels(prev => prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]);
  };

  const toggleFeatureGroup = (fg: string) => {
    if (fg === "all") { setFeatureGroups(["all"]); return; }
    setFeatureGroups(prev => {
      const next = prev.includes(fg) ? prev.filter(x => x !== fg) : [...prev.filter(x => x !== "all"), fg];
      return next.length === 0 ? ["price"] : next;
    });
  };

  const handleTrainSingle = () => {
    if (!selectedModels.length) { toast.error("حداقل یک مدل انتخاب کنید"); return; }
    for (const model of selectedModels) {
      trainSingle.mutate({
        model_type: model,
        symbols: [singleSymbol],
        feature_groups: featureGroups.includes("all") ? ["price", "technical", "trades", "microstructure"] : featureGroups,
        data_source: dataSource,
        task_type: taskType,
        n_cv_splits: nSplits,
      });
    }
  };

  const handleTrainAll = () => {
    if (!selectedModels.length) { toast.error("حداقل یک مدل انتخاب کنید"); return; }
    setAllResults([]);
    setTrainCount(0);
    for (const model of selectedModels) {
      trainAllMutation.mutate({
        model_type: model,
        feature_groups: featureGroups.includes("all") ? ["price", "technical", "trades", "microstructure"] : featureGroups,
        data_source: dataSource,
        task_type: taskType,
        n_cv_splits: nSplits,
      });
    }
  };

  // Aggregate results
  let totalSymbols = 0, totalSuccess = 0, totalFailed = 0, totalTime = 0;
  const allChartData: { label: string; r2: number }[] = [];
  for (const { model, result } of allResults) {
    totalSymbols += result.total_symbols;
    totalSuccess += result.successful;
    totalFailed += result.failed;
    totalTime += result.total_duration_seconds;
    for (const r of result.results) {
      if (r.success && r.metrics?.mean_r2 != null) {
        allChartData.push({ label: `${r.symbol} (${model})`, r2: r.metrics.mean_r2 });
      }
    }
  }
  const hasResults = allResults.length > 0;

  // Sorted R² bar chart
  const sortedR2 = [...allChartData].sort((a, b) => b.r2 - a.r2).slice(0, 15);
  const maxAbsR2 = Math.max(...sortedR2.map(d => Math.abs(d.r2)), 0.01);

  return (
    <div className="space-y-5">
      {/* ── Config Panel ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Data Source */}
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-xs text-surface-400 font-bold mb-2.5">📂 منبع داده</label>
          <div className="space-y-1.5">
            {DATA_SOURCES.map(ds => (
              <button key={ds.value} onClick={() => setDataSource(ds.value)}
                className={`w-full text-right px-3 py-2 rounded-xl text-[11px] font-medium transition-all border ${
                  dataSource === ds.value
                    ? "bg-primary-600/20 border-primary-500/30 text-primary-300"
                    : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
                }`}>
                <span className="ml-1.5">{ds.icon}</span>
                <span className="font-bold">{ds.label}</span>
                <p className="text-[8px] text-surface-600 mt-0.5 pr-5">{ds.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Task Type + CV */}
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-xs text-surface-400 font-bold mb-2.5">🎯 نوع مسئله</label>
          <div className="space-y-1.5 mb-4">
            {TASK_TYPES.map(tt => (
              <button key={tt.value} onClick={() => setTaskType(tt.value)}
                className={`w-full text-right px-3 py-2 rounded-xl text-[11px] font-medium transition-all border ${
                  taskType === tt.value
                    ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald"
                    : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
                }`}>
                <span className="ml-1.5">{tt.icon}</span>
                {tt.label}
                <p className="text-[8px] text-surface-600 mt-0.5 pr-5">{tt.desc}</p>
              </button>
            ))}
          </div>
          <label className="block text-[10px] text-surface-500 font-bold mb-1">Fold‌های CV</label>
          <div className="flex gap-1">
            {[2, 3, 5, 10].map(n => (
              <button key={n} onClick={() => setNSplits(n)}
                className={`flex-1 py-1.5 rounded-lg text-[11px] font-bold transition-all ${
                  nSplits === n
                    ? "bg-primary-600/30 text-primary-300"
                    : "bg-surface-800 text-surface-500 hover:text-surface-300"
                }`}>{n}</button>
            ))}
          </div>
        </div>

        {/* Feature Groups */}
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-xs text-surface-400 font-bold mb-2.5">🧩 گروه ویژگی</label>
          <div className="grid grid-cols-1 gap-1.5">
            {FEATURE_GROUPS.map(fg => (
              <button key={fg.value} onClick={() => toggleFeatureGroup(fg.value)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all border ${
                  featureGroups.includes(fg.value) || (fg.value === "all" && featureGroups.length > 3)
                    ? "bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan"
                    : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
                }`}>
                <span>{fg.icon}</span>
                <span className="flex-1">{fg.label}</span>
                {(featureGroups.includes(fg.value) || (fg.value === "all" && featureGroups.length > 3)) &&
                  <span className="material-icons text-xs">check</span>}
              </button>
            ))}
          </div>
          <p className="text-[8px] text-surface-600 mt-1.5">{featureGroups.length} گروه انتخاب شد</p>
        </div>

        {/* Models + Actions */}
        <div className="glass-card p-4 rounded-2xl">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-surface-400 font-bold">🤖 مدل‌ها</label>
            <div className="flex gap-1">
              <button onClick={() => setSelectedModels([...ALL_MODELS])}
                className="text-[8px] px-1.5 py-0.5 rounded bg-surface-800 text-surface-500 hover:text-surface-300">همه</button>
              <button onClick={() => setSelectedModels(["xgboost"])}
                className="text-[8px] px-1.5 py-0.5 rounded bg-surface-800 text-surface-500 hover:text-surface-300">پیش‌فرض</button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-1">
            {ALL_MODELS.map(m => {
              const meta = MODEL_META[m];
              const isSelected = selectedModels.includes(m);
              return (
                <button key={m} onClick={() => toggleModel(m)}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all border ${
                    isSelected
                      ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald"
                      : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
                  }`}>
                  <span>{meta?.icon || "🔧"}</span>
                  <span className="flex-1 font-bold">{m}</span>
                  {isSelected && <span className="material-icons text-xs">check</span>}
                </button>
              );
            })}
          </div>

          <div className="mt-3 space-y-2">
            <select value={singleSymbol} onChange={e => setSingleSymbol(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-2 py-1.5 text-[10px] text-surface-200 outline-none focus:border-primary-500">
              {allSymbols.slice(0, 100).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={handleTrainSingle} disabled={isTraining}
              className="w-full py-2 rounded-xl text-[11px] font-bold bg-primary-600/20 text-primary-400 border border-primary-600/30 hover:bg-primary-600/30 transition-all disabled:opacity-40 flex items-center justify-center gap-1.5">
              {trainSingle.isPending ? <span className="material-icons animate-spin text-sm">refresh</span> : "🚀"}
              آموزش روی {singleSymbol}
            </button>
            <button onClick={handleTrainAll} disabled={isTraining}
              className="w-full py-2.5 rounded-xl text-xs font-bold bg-accent-amber/15 text-accent-amber border border-accent-amber/30 hover:bg-accent-amber/25 transition-all disabled:opacity-40 flex items-center justify-center gap-1.5">
              {trainAllMutation.isPending
                ? <><span className="material-icons animate-spin text-sm">refresh</span> در حال آموزش...</>
                : "🔥 آموزش روی همه نمادها"}
            </button>
            <p className="text-[8px] text-surface-600 text-center">
              {allSymbols.length} نماد • {selectedModels.length} مدل • {nSplits}‑fold CV
            </p>
          </div>
        </div>
      </div>

      {/* ── Progress ── */}
      {isTraining && (
        <div className="glass-card p-4 rounded-2xl border border-accent-amber/20">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-icons text-accent-amber animate-spin text-sm">refresh</span>
            <span className="text-sm font-bold text-surface-200">در حال آموزش...</span>
          </div>
          <div className="h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
            <div className="h-full w-full bg-gradient-to-r from-primary-600 via-accent-cyan to-primary-600 rounded-full animate-pulse" />
          </div>
        </div>
      )}

      {/* ── Multi-model progress ── */}
      {trainCount > 0 && trainCount < selectedModels.length && (
        <div className="glass-card p-3 rounded-2xl border border-accent-amber/20">
          <div className="flex items-center justify-between">
            <span className="text-xs text-surface-300">✅ {trainCount} / {selectedModels.length} مدل کامل شد</span>
            <span className="text-[10px] text-surface-500">{trainAllMutation.isPending ? "در حال پردازش..." : "آماده"}</span>
          </div>
          <div className="mt-1.5 h-1.5 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
            <div className="h-full bg-accent-emerald rounded-full transition-all duration-500"
              style={{ width: `${(trainCount / selectedModels.length) * 100}%` }} />
          </div>
        </div>
      )}

      {/* ── Results ── */}
      {hasResults && !isTraining && (
        <>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            <InfoCard icon="🎯" label="مدل‌ها" value={allResults.length} color="text-primary-300" />
            <InfoCard icon="📊" label="کل نمادها" value={totalSymbols} color="text-surface-100" />
            <InfoCard icon="✅" label="موفق" value={totalSuccess} color="text-accent-emerald" />
            <InfoCard icon="❌" label="ناموفق" value={totalFailed} color="text-accent-rose" />
            <InfoCard icon="🏆" label="بهترین R²"
              value={totalSuccess > 0 ? Math.max(...allChartData.filter(d => !isNaN(d.r2)).map(d => d.r2)).toFixed(4) : "—"}
              color="text-accent-amber" />
            <InfoCard icon="⏱" label="زمان کل" value={`${totalTime.toFixed(0)}s`} color="text-surface-400" />
          </div>

          {/* R² Bar Chart */}
          {sortedR2.length > 0 && (
            <Card title="📊 R² برترین نمادها" subtitle={`${allResults.map(a => a.model).join(" + ")}`}>
              <div className="space-y-1.5 mt-1">
                {sortedR2.map(d => (
                  <div key={d.label} className="flex items-center gap-2">
                    <span className="text-[9px] text-surface-400 w-16 truncate font-mono text-right" title={d.label}>{d.label}</span>
                    <div className="flex-1 h-3.5 bg-surface-800/50 rounded-full overflow-hidden" dir="ltr">
                      <div className={`h-full rounded-full transition-all duration-700 ${d.r2 >= 0 ? "bg-accent-emerald" : "bg-accent-rose"}`}
                        style={{ width: `${(Math.abs(d.r2) / maxAbsR2) * 100}%` }} />
                    </div>
                    <span className={`text-[9px] font-mono w-14 text-left ${d.r2 >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {d.r2 >= 0 ? "+" : ""}{d.r2.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Per-model results */}
          {allResults.map(({ model, result }) => {
            const sortedResults = [...result.results].sort((a, b) => {
              if (a.success !== b.success) return a.success ? -1 : 1;
              return (b.metrics?.mean_r2 ?? -999) - (a.metrics?.mean_r2 ?? -999);
            });
            return (
              <Card key={model} title={`📋 ${MODEL_META[model]?.icon || "🔧"} نتایج ${model}`}
                actions={<span className="text-[10px] text-surface-500">{result.successful} موفق / {result.failed} ناموفق</span>}>
                <div className="overflow-x-auto">
                  <table className="w-full text-right text-[10px]">
                    <thead>
                      <tr className="text-surface-500 border-b border-surface-700">
                        <th className="pb-2 px-2">#</th>
                        <th className="pb-2 px-2">نماد</th>
                        <th className="pb-2 px-2 text-center">وضعیت</th>
                        <th className="pb-2 px-2 text-center font-mono">R²</th>
                        <th className="pb-2 px-2 text-center font-mono">MAE</th>
                        <th className="pb-2 px-2 text-center font-mono">RMSE</th>
                        <th className="pb-2 px-2 text-center">نمونه</th>
                        <th className="pb-2 px-2 text-center">زمان</th>
                        <th className="pb-2 px-2 w-16">نوار R²</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedResults.map((r, i) => {
                        const mR2 = r.metrics?.mean_r2 ?? null;
                        const mMAE = r.metrics?.mean_mae ?? null;
                        const mRMSE = r.metrics?.mean_rmse ?? null;
                        const samples = r.metrics?.train_samples ?? r.metrics?.mean_train_size;
                        return (
                          <tr key={r.symbol} className={`border-b border-surface-800/30 hover:bg-white/5 transition-colors ${!r.success ? "opacity-50" : ""}`}>
                            <td className="py-2 px-2 text-surface-500">{i + 1}</td>
                            <td className="py-2 px-2 font-bold text-surface-200">{r.symbol}</td>
                            <td className="py-2 px-2 text-center">{r.success ? "✅" : "❌"}</td>
                            <td className={`py-2 px-2 text-center font-mono ${mR2 != null ? (mR2 >= 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-600"}`}>
                              {mR2 != null ? mR2.toFixed(4) : "—"}
                            </td>
                            <td className="py-2 px-2 text-center font-mono text-surface-300">{mMAE != null ? mMAE.toFixed(4) : "—"}</td>
                            <td className="py-2 px-2 text-center font-mono text-surface-300">{mRMSE != null ? mRMSE.toFixed(4) : "—"}</td>
                            <td className="py-2 px-2 text-center font-mono text-surface-400">{samples ?? "—"}</td>
                            <td className="py-2 px-2 text-center text-surface-500">{r.duration_seconds.toFixed(1)}s</td>
                            <td className="py-2 px-2">{mR2 != null && <MiniBar value={mR2} maxVal={1} color={mR2 >= 0 ? "bg-accent-emerald" : "bg-accent-rose"} />}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })}
        </>
      )}

      {!hasResults && !isTraining && (
        <div className="glass-card p-10 text-center text-surface-500">
          <p className="text-5xl mb-3">🧠</p>
          <p className="font-bold text-surface-400">آماده آموزش</p>
          <p className="text-sm mt-1">منبع داده، مدل‌ها و ویژگی‌ها را انتخاب کنید و دکمه آموزش را بزنید</p>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 3: COMPARISON — Side-by-side model comparison
// ══════════════════════════════════════════════════════════════════════════════

function ComparisonTab() {
  const { data: comparisons = [], isLoading } = useQuery({
    queryKey: ["ml-comparison"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: ComparisonItem[] }>("/ml/comparison");
      return r?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  const [metricFilter, setMetricFilter] = useState("mean_r2");
  const [sortBy, setSortBy] = useState<"asc" | "desc">("desc");

  if (isLoading) return <div className="space-y-3">{[1, 2].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>;
  if (!comparisons.length) return <div className="glass-card p-12 text-center"><p className="text-5xl mb-3">📊</p><p className="font-bold text-surface-400">مدلی برای مقایسه نیست</p><p className="text-sm mt-1 text-surface-500">ابتدا یک آموزش اجرا کنید</p></div>;

  // Available metrics
  const metricKeys = new Set<string>();
  comparisons.forEach(c => { if (c.metrics) Object.keys(c.metrics).forEach(k => metricKeys.add(k)); });
  const orderedMetrics = ["mean_r2", "mean_mae", "mean_rmse", "mean_mape", "mean_accuracy", "mean_f1"];
  const visibleMetrics = orderedMetrics.filter(m => metricKeys.has(m));

  // Find best per metric
  const bestPerMetric = visibleMetrics.map(mk => {
    const best = comparisons.reduce<ComparisonItem | null>((b, c) => {
      const v = c.metrics?.[mk]; if (v == null) return b;
      if (b == null) return c;
      const bv = b.metrics?.[mk] ?? -999;
      const isError = mk.includes("mae") || mk.includes("mse") || mk.includes("rmse");
      return isError ? (v < bv ? c : b) : (v > bv ? c : b);
    }, null);
    return { metric: mk, best };
  }).filter(x => x.best != null);

  // Sorted comparison table
  const sortedComp = [...comparisons].sort((a, b) => {
    const av = a.metrics?.[metricFilter] ?? -999;
    const bv = b.metrics?.[metricFilter] ?? -999;
    return sortBy === "desc" ? bv - av : av - bv;
  });

  // Top models by model_type
  const modelsInData = Array.from(new Set(comparisons.map(c => c.model_type)));

  return (
    <div className="space-y-5">
      {/* Summary badges */}
      <div className="flex flex-wrap gap-2">
        {bestPerMetric.map(({ metric, best }) => (
          <span key={metric} className="text-[10px] bg-surface-800/50 px-2.5 py-1 rounded-full text-surface-400 border border-surface-700/30">
            🏆 <b className="text-surface-200">{metric.replace("mean_", "").toUpperCase()}</b>:
            <span className="text-accent-emerald ml-1">{best!.model_type}/{best!.symbol}</span>
            <span className="text-surface-500 ml-1">({(best!.metrics?.[metric] ?? 0).toFixed(4)})</span>
          </span>
        ))}
      </div>

      {/* Model vs Model Chart */}
      {modelsInData.length >= 2 && (
        <Card title="📊 مقایسه مدل‌ها" subtitle={`${comparisons.length} رکورد • ${modelsInData.length} مدل`}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {modelsInData.map(mt => {
              const items = comparisons.filter(c => c.model_type === mt);
              const avgR2 = items.reduce((s, c) => s + (c.metrics?.mean_r2 ?? 0), 0) / items.length;
              const posCount = items.filter(c => (c.metrics?.mean_r2 ?? 0) >= 0).length;
              return (
                <div key={mt} className="glass-card p-3 text-center">
                  <p className="text-base font-black text-surface-200">{MODEL_META[mt]?.icon || "🔧"} {mt}</p>
                  <p className={`text-xl font-black font-mono mt-1 ${avgR2 >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {avgR2.toFixed(4)}
                  </p>
                  <p className="text-[9px] text-surface-500">میانگین R² • {items.length} نماد</p>
                  <p className="text-[9px] text-surface-600 mt-0.5">{posCount}/{items.length} مثبت</p>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Comparison Table */}
      <Card title="📋 جدول مقایسه" actions={
        <div className="flex items-center gap-2">
          <select value={metricFilter} onChange={e => setMetricFilter(e.target.value)}
            className="bg-surface-800 text-[10px] text-surface-300 border border-surface-700 rounded-lg px-2 py-1 outline-none">
            {visibleMetrics.map(mk => (
              <option key={mk} value={mk}>{mk.replace("mean_", "").toUpperCase()}</option>
            ))}
          </select>
          <button onClick={() => setSortBy(s => s === "desc" ? "asc" : "desc")}
            className="text-[10px] px-2 py-1 rounded-lg bg-surface-800 text-surface-400 hover:text-surface-200">
            {sortBy === "desc" ? "⬇ نزولی" : "⬆ صعودی"}
          </button>
        </div>
      }>
        <div className="overflow-x-auto">
          <table className="w-full text-right text-[10px]">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 px-2">مدل</th>
                <th className="pb-2 px-2">نماد</th>
                {visibleMetrics.map(mk => (
                  <th key={mk} className={`pb-2 px-2 font-mono text-center ${mk === metricFilter ? "text-primary-300" : ""}`}>
                    {mk.replace("mean_", "").toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedComp.map((c, i) => (
                <tr key={`${c.model_type}-${c.symbol}-${i}`} className="border-b border-surface-800/30 hover:bg-white/5">
                  <td className="py-2 px-2 font-bold text-surface-200">{c.model_type}</td>
                  <td className="py-2 px-2 text-surface-400">{c.symbol}</td>
                  {visibleMetrics.map(mk => {
                    const v = c.metrics?.[mk];
                    const isBest = bestPerMetric.find(b => b.metric === mk)?.best === c;
                    return (
                      <td key={mk} className={`py-2 px-2 font-mono text-center ${
                        isBest ? "bg-accent-emerald/10 rounded" : ""
                      } ${
                        mk === metricFilter ? "font-bold" : ""
                      } ${
                        mk === "mean_r2" ? (v != null && v >= 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-300"
                      }`}>
                        {v != null ? v.toFixed(4) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 4: PREDICTIONS — View and run predictions
// ══════════════════════════════════════════════════════════════════════════════

function PredictionsTab() {
  const [selectedModel, setSelectedModel] = useState("xgboost");
  const [predictSymbol, setPredictSymbol] = useState("فولاد");
  const [predictionResult, setPredictionResult] = useState<any>(null);
  const [predicting, setPredicting] = useState(false);

  const { data: allSymbols = [] } = useAllSymbols();

  // Fetch models list
  const { data: modelsData } = useQuery({
    queryKey: ["ml-models"],
    queryFn: async () => {
      try {
        const r = await apiGet<{ success: boolean; data: Array<{ id: string; model_type: string }> }>("/ml/models");
        return r?.data ?? [];
      } catch (e) {
        console.warn("Failed to fetch models:", e);
        return [];
      }
    },
  });

  // Derived model types (no effect needed)
  const derivedModels = React.useMemo(
    () => Array.from(new Set((modelsData ?? []).map(m => m.model_type))),
    [modelsData]
  );

  // Sync selectedModel with available models
  React.useEffect(() => {
    if (derivedModels.length > 0 && !derivedModels.includes(selectedModel)) {
      setSelectedModel(derivedModels[0]);
    }
  }, [derivedModels, selectedModel]);

  // Fetch predictions list
  const { data: predictions = [], isLoading: predLoading } = useQuery({
    queryKey: ["ml-predictions"],
    queryFn: async () => {
      try {
        const r = await apiGet<{ success: boolean; data: PredictionItem[] }>("/ml/predictions?limit=50");
        return r?.data ?? [];
      } catch (e) {
        console.warn("Failed to fetch predictions:", e);
        return [];
      }
    },
    refetchInterval: 30_000,
  });

  const handlePredict = async () => {
    setPredicting(true);
    try {
      const res = await apiPost<{ success: boolean; data: any }>("/ml/predict-real", {
        model_id: selectedModel,
        symbol: predictSymbol,
      });
      setPredictionResult(res?.data ?? null);
    } catch (err: any) {
      toast.error(err.message);
      setPredictionResult(null);
    }
    setPredicting(false);
  };

  return (
    <div className="space-y-5">
      {/* Prediction form */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-xs text-surface-400 font-bold mb-2">🤖 مدل</label>
          <div className="flex flex-wrap gap-1.5">
            {derivedModels.length > 0 ? derivedModels.map(mt => (
              <button key={mt} onClick={() => setSelectedModel(mt)}
                className={`px-3 py-2 rounded-lg text-[11px] font-medium transition-all border ${
                  selectedModel === mt
                    ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald"
                    : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
                }`}>
                {MODEL_META[mt]?.icon || "🔧"} {mt}
              </button>
            )) : (
              <p className="text-[10px] text-surface-500">مدلی یافت نشد. ابتدا آموزش دهید.</p>
            )}
          </div>
        </div>

        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-xs text-surface-400 font-bold mb-2">📊 نماد</label>
          <select value={predictSymbol} onChange={e => setPredictSymbol(e.target.value)}
            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500">
            {allSymbols.slice(0, 200).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="glass-card p-4 rounded-2xl flex items-end">
          <button onClick={handlePredict} disabled={predicting || !selectedModel}
            className="w-full py-3 rounded-xl text-sm font-bold bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30 hover:bg-accent-emerald/25 transition-all disabled:opacity-40 flex items-center justify-center gap-2">
            {predicting ? <span className="material-icons animate-spin text-sm">refresh</span> : "🔮"}
            پیش‌بینی
          </button>
        </div>
      </div>

      {/* Prediction result */}
      {predictionResult && (
        <Card title="🎯 نتیجه پیش‌بینی" subtitle={`${selectedModel} • ${predictSymbol}`}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="glass-card p-3 text-center">
              <p className={`text-2xl font-black font-mono ${
                (predictionResult.prediction ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"
              }`}>
                {fmtPct(predictionResult.prediction ?? 0)}
              </p>
              <p className="text-[9px] text-surface-500">📈 تغییر پیش‌بینی شده</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-2xl font-black font-mono text-surface-200">
                {predictionResult.confidence != null ? (predictionResult.confidence * 100).toFixed(0) + "%" : "—"}
              </p>
              <p className="text-[9px] text-surface-500">🎯 اطمینان</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className={`text-2xl font-black ${
                predictionResult.direction === "up" ? "text-accent-emerald" :
                predictionResult.direction === "down" ? "text-accent-rose" : "text-surface-500"
              }`}>
                {predictionResult.direction === "up" ? "📈 صعود" :
                 predictionResult.direction === "down" ? "📉 نزول" : "➡️ خنثی"}
              </p>
              <p className="text-[9px] text-surface-500">جهت پیش‌بینی</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-2xl font-black font-mono text-surface-400">
                {predictionResult.model_type || selectedModel}
              </p>
              <p className="text-[9px] text-surface-500">مدل</p>
            </div>
          </div>

          {predictionResult.feature_importance && (
            <div className="mt-4">
              <p className="text-xs text-surface-400 font-bold mb-2">🔥 اهمیت ویژگی‌ها</p>
              <div className="space-y-1">
                {Object.entries(predictionResult.feature_importance)
                  .sort(([, a]: any, [, b]: any) => b - a)
                  .slice(0, 10)
                  .map(([feat, val]: [string, any]) => (
                    <div key={feat} className="flex items-center gap-2">
                      <span className="text-[9px] text-surface-400 w-32 truncate text-right font-mono">{feat}</span>
                      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
                        <div className="h-full bg-accent-amber rounded-full" style={{ width: `${(val as number) * 100}%` }} />
                      </div>
                      <span className="text-[9px] font-mono text-surface-500 w-10 text-left">{(val as number * 100).toFixed(0)}%</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Predictions list */}
      <Card title="📋 آخرین پیش‌بینی‌ها" actions={
        <span className="text-[10px] text-surface-600">{predictions.length} رکورد</span>
      }>
        {predLoading ? (
          <Skeleton className="h-40 w-full rounded-xl" />
        ) : predictions.length === 0 ? (
          <p className="text-surface-500 text-sm text-center py-6">پیش‌بینی ذخیره‌شده‌ای وجود ندارد</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-[10px]">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 px-2">نماد</th>
                  <th className="pb-2 px-2">مدل</th>
                  <th className="pb-2 px-2 text-center">جهت</th>
                  <th className="pb-2 px-2 text-center font-mono">تغییرات</th>
                  <th className="pb-2 px-2 text-center">اطمینان</th>
                  <th className="pb-2 px-2 text-center">زمان</th>
                </tr>
              </thead>
              <tbody>
                {predictions.slice(0, 30).map((p, i) => (
                  <tr key={i} className="border-b border-surface-800/30 hover:bg-white/5">
                    <td className="py-2 px-2 font-bold text-surface-200">{p.symbol}</td>
                    <td className="py-2 px-2 text-surface-400">{p.model_type}</td>
                    <td className={`py-2 px-2 text-center font-bold ${
                      p.direction === "up" ? "text-accent-emerald" :
                      p.direction === "down" ? "text-accent-rose" : "text-surface-500"
                    }`}>
                      {p.direction === "up" ? "📈" : p.direction === "down" ? "📉" : "➡️"}
                    </td>
                    <td className={`py-2 px-2 text-center font-mono ${(p.prediction ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {fmtPct(p.prediction)}
                    </td>
                    <td className="py-2 px-2 text-center">
                      <div className="flex items-center gap-1 justify-center">
                        <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
                          <div className={`h-full rounded-full ${
                            (p.confidence ?? 0) >= 0.7 ? "bg-accent-emerald" :
                            (p.confidence ?? 0) >= 0.4 ? "bg-accent-amber" : "bg-accent-rose"
                          }`} style={{ width: `${(p.confidence ?? 0) * 100}%` }} />
                        </div>
                        <span className="text-[8px] text-surface-500">{(p.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="py-2 px-2 text-center text-surface-500">{p.created_at?.slice(11, 19) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB 5: BACKTEST — Walk-forward backtest results
// ══════════════════════════════════════════════════════════════════════════════

function BacktestTab() {
  return <MLBacktestTab />;
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════

const TABS = [
  { key: "dashboard" as const, label: "🏠 داشبورد",     desc: "نمای کلی و آمار" },
  { key: "data" as const,      label: "📊 داده‌کاوی",    desc: "کیفیت و دسترسی داده" },
  { key: "training" as const,  label: "🧠 آموزش",        desc: "آموزش مدل‌های پیش‌بینی" },
  { key: "compare" as const,   label: "📊 مقایسه",       desc: "مقایسه مدل‌ها" },
  { key: "predict" as const,   label: "🎯 پیش‌بینی",     desc: "اجرای پیش‌بینی" },
  { key: "backtest" as const,  label: "📈 بک‌تست",       desc: "ارزیابی عملکرد" },
];

export default function MLPage() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "data" | "training" | "compare" | "predict" | "backtest">("dashboard");

  return (
    <AppLayout title="🧠 یادگیری ماشین" subtitle="پلتفرم پیش‌بینی هوشمند بازار سرمایه — آموزش، ارزیابی و پیش‌بینی مدل‌ها">
      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-5 bg-surface-800/50 rounded-2xl p-1 border border-surface-700/50 w-fit overflow-x-auto" dir="rtl">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 whitespace-nowrap ${
              activeTab === tab.key
                ? "bg-primary-600/30 text-primary-300 shadow-sm shadow-primary-600/10"
                : "text-surface-400 hover:text-surface-200"
            }`}>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "dashboard" && <DashboardTab />}
      {activeTab === "data" && <DataMiningTab />}
      {activeTab === "training" && <TrainingTab />}
      {activeTab === "compare" && <ComparisonTab />}
      {activeTab === "predict" && <PredictionsTab />}
      {activeTab === "backtest" && <BacktestTab />}
    </AppLayout>
  );
}
