"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";

// ------ Types -------------------------------------------------------------------------------------------------------------
interface MLModel {
  id: string;
  name: string;
  task: string;
  framework: string;
  versions: MLVersion[];
  tags: string[];
  latest_version?: string;
  created_at: string;
}

interface MLVersion {
  version: string;
  stage: string;
  metrics: Record<string, number>;
  parameters: Record<string, unknown>;
  artifact_path: string;
  created_at: string;
}

interface TrainingRun {
  id: string;
  experiment_name: string;
  model_type: string;
  symbol?: string;
  symbols?: string[];
  status: string;
  metrics: Record<string, number>;
  feature_names?: string[];
  train_samples?: number;
  val_samples?: number;
  artifact_path?: string;
}

interface TrainResponse {
  run_id: string;
  experiment_name: string;
  model_type: string;
  status: string;
  message: string;
}

interface ComparisonItem {
  model_type: string;
  symbol: string;
  metrics: Record<string, number>;
  run_id?: string;
  experiment_name?: string;
  artifact_path?: string;
  version?: string;
}

type MLTab = "models" | "runs" | "train" | "predict" | "compare";

const TABS: { key: MLTab; label: string; icon: string }[] = [
  { key: "models", label: "مدل‌ها", icon: "🧠" },
  { key: "compare", label: "مقایسه", icon: "📊" },
  { key: "runs", label: "آموزش‌ها", icon: "⚙️" },
  { key: "train", label: "آموزش جدید", icon: "🚀" },
  { key: "predict", label: "پیش‌بینی", icon: "🔮" },
];

const MODEL_TYPES = ["xgboost", "random_forest", "linear_regression", "lstm", "transformer"];

// Hook to fetch all active symbols from the database
function useAllSymbols() {
  const { data: allSymbols = [] } = useQuery({
    queryKey: ["ml-all-symbols"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { items: { symbol: string }[] } }>("/symbols?page_size=10000");
      return (res?.data?.items ?? []).map((s) => s.symbol).filter(Boolean);
    },
    staleTime: 60_000,
  });
  return allSymbols;
}

interface StageBadgeProps { stage: string }
function StageBadge({ stage }: StageBadgeProps) {
  const colors: Record<string, string> = {
    production: "bg-accent-emerald/15 text-accent-emerald",
    staging: "bg-accent-amber/15 text-accent-amber",
    development: "bg-surface-600/30 text-surface-400",
    archived: "bg-accent-rose/15 text-accent-rose",
  };
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${colors[stage] || colors.development}`}>{stage}</span>;
}

// ------ Feature Importance Chart (inline SVG bar chart) -------------------------------------------------------------------
function FeatureImportanceChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).slice(0, 12);
  if (entries.length === 0) return null;

  const maxVal = Math.max(...entries.map(([, v]) => v));

  return (
    <div className="mt-4">
      <p className="text-xs text-surface-400 font-bold mb-3">📊 اهمیت ویژگی‌ها (Feature Importance)</p>
      <div className="space-y-1.5">
        {entries.map(([name, importance]) => (
          <div key={name} className="flex items-center gap-3">
            <span className="text-[10px] text-surface-400 w-28 truncate text-right font-mono" title={name}>{name}</span>
            <div className="flex-1 h-4 bg-surface-800/50 rounded-full overflow-hidden" dir="ltr">
              <div
                className="h-full bg-gradient-to-r from-primary-600 to-accent-cyan rounded-full transition-all duration-500"
                style={{ width: `${(importance / maxVal) * 100}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-surface-500 w-12 text-left">{(importance * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ------ Radar Chart Component (inline SVG) ---------------------------------------------------------------------------------
const RADAR_COLORS = [
  { fill: "rgba(0, 200, 255, 0.15)", stroke: "#00C8FF", label: "text-accent-cyan" },
  { fill: "rgba(0, 230, 118, 0.15)", stroke: "#00E676", label: "text-accent-emerald" },
  { fill: "rgba(255, 214, 0, 0.15)", stroke: "#FFD600", label: "text-accent-amber" },
  { fill: "rgba(255, 82, 82, 0.15)", stroke: "#FF5252", label: "text-accent-rose" },
  { fill: "rgba(224, 64, 251, 0.15)", stroke: "#E040FB", label: "text-accent-purple" },
  { fill: "rgba(0, 230, 200, 0.15)", stroke: "#00E6C8", label: "text-surface-200" },
];

function ModelRadarChart({ comparisons, metricKeys }: { comparisons: ComparisonItem[]; metricKeys: string[] }) {
  // Use only 5-6 metrics that make sense for radar (omit MSE/RMSE which overlap with MAE)
  const radarMetrics = ["r2", "accuracy", "f1", "precision", "recall", "mape"].filter(m => metricKeys.includes(m));
  if (radarMetrics.length < 3 || comparisons.length < 1) return null;

  // Normalize values to 0-1 range per metric across all models
  const ranges: Record<string, { min: number; max: number }> = {};
  for (const mk of radarMetrics) {
    let vals = comparisons.map(c => c.metrics?.[mk]).filter(v => v != null) as number[];
    if (vals.length === 0) continue;
    ranges[mk] = { min: Math.min(...vals), max: Math.max(...vals) };
  }

  const normalize = (mk: string, v: number | undefined): number => {
    if (v == null) return 0;
    const r = ranges[mk];
    if (!r || r.max === r.min) return 0.5;
    // For mape (error metric), lower is better → invert
    if (mk === "mape") return 1 - (v - r.min) / (r.max - r.min);
    return (v - r.min) / (r.max - r.min);
  };

  // Chart dimensions
  const cx = 160, cy = 160, radius = 130;
  const levels = 5;
  const angleStep = (2 * Math.PI) / radarMetrics.length;

  // Compute polygon points for each model
  const modelPolygons = comparisons.slice(0, 6).map((c, mi) => {
    const points = radarMetrics.map((mk, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const val = normalize(mk, c.metrics?.[mk]);
      const r = val * radius;
      return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
    });
    return { points: points.join(" "), color: RADAR_COLORS[mi % RADAR_COLORS.length], label: `${c.model_type}/${c.symbol}` };
  });

  return (
    <div className="mt-6 mb-6">
      <p className="text-xs text-surface-400 font-bold mb-3 text-center">📡 نمودار راداری — مقایسه بصری مدل‌ها</p>
      <div className="flex flex-col items-center">
        <svg width={320} height={320} viewBox="0 0 320 320" className="max-w-full">
          {/* Background grid: concentric polygons */}
          {Array.from({ length: levels }, (_, li) => {
            const r = ((li + 1) / levels) * radius;
            const pts = radarMetrics.map((_, i) => {
              const angle = -Math.PI / 2 + i * angleStep;
              return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
            });
            return <polygon key={li} points={pts.join(" ")} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />;
          })}

          {/* Axis lines */}
          {radarMetrics.map((mk, i) => {
            const angle = -Math.PI / 2 + i * angleStep;
            const x2 = cx + radius * Math.cos(angle);
            const y2 = cy + radius * Math.sin(angle);
            const labelX = cx + (radius + 22) * Math.cos(angle);
            const labelY = cy + (radius + 22) * Math.sin(angle);
            const anchor = angle > -0.1 && angle < Math.PI - 0.1 ? "start" : angle > Math.PI - 0.1 ? "end" : "middle";
            return (
              <g key={mk}>
                <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
                <text x={labelX} y={labelY} textAnchor={anchor} dominantBaseline="middle"
                  fill="rgba(255,255,255,0.5)" fontSize={9} fontFamily="monospace">
                  {mk.toUpperCase()}
                </text>
              </g>
            );
          })}

          {/* Model polygons */}
          {modelPolygons.map((mp, i) => (
            <g key={i}>
              <polygon points={mp.points} fill={mp.color.fill} stroke={mp.color.stroke} strokeWidth={2}
                opacity={0.8} className="transition-opacity hover:opacity-100 cursor-pointer" />
              {/* Dots on vertices */}
              {mp.points.split(" ").map((pt, pi) => {
                const [x, y] = pt.split(",").map(Number);
                return <circle key={pi} cx={x} cy={y} r={3} fill={mp.color.stroke} opacity={0.8} />;
              })}
            </g>
          ))}

          {/* Center dot */}
          <circle cx={cx} cy={cy} r={2} fill="rgba(255,255,255,0.2)" />
        </svg>

        {/* Legend */}
        <div className="flex flex-wrap gap-3 justify-center mt-2">
          {modelPolygons.map((mp, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: mp.color.stroke }} />
              <span className="text-[10px] text-surface-400">{mp.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ------ Model Comparison Table ---------------------------------------------------------------------------------------------
function ComparisonTab() {
  const { data: comparisons = [], isLoading } = useQuery({
    queryKey: ["ml-comparison"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: ComparisonItem[] }>("/ml/comparison");
      return res?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  // Collect unique metric keys
  const metricKeys = new Set<string>();
  comparisons.forEach(c => {
    if (c.metrics) Object.keys(c.metrics).forEach(k => metricKeys.add(k));
  });
  const orderedMetrics = ["r2", "mae", "mse", "rmse", "mape", "accuracy", "f1", "precision", "recall"];

  if (isLoading) {
    return <div className="space-y-3">{[1, 2].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>;
  }

  if (comparisons.length === 0) {
    return (
      <div className="glass-card p-12 text-center text-surface-500">
        <p className="text-5xl mb-3">📊</p>
        <p className="font-bold">مدلی برای مقایسه وجود ندارد</p>
        <p className="text-sm mt-1">ابتدا یک مدل را از بخش آموزش جدید آموزش دهید</p>
      </div>
    );
  }

  // Find best model per metric
  const bestModel: Record<string, string> = {};
  for (const mk of orderedMetrics) {
    if (!metricKeys.has(mk)) continue;
    const best = comparisons.reduce<ComparisonItem | null>((best, c) => {
      const v = c.metrics?.[mk];
      const bv = best?.metrics?.[mk];
      if (v == null) return best;
      if (bv == null) return c;
      return (mk === "mse" || mk === "mae" || mk === "rmse") ? (v < bv ? c : best) : (v > bv ? c : best);
    }, null);
    if (best) bestModel[mk] = `${best.model_type}/${best.symbol}`;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-right text-xs">
        <thead>
          <tr className="text-surface-500 border-b border-surface-700">
            <th className="pb-2 px-2 whitespace-nowrap">مدل</th>
            <th className="pb-2 px-2 whitespace-nowrap">نماد</th>
            {orderedMetrics.filter(mk => metricKeys.has(mk)).map(mk => (
              <th key={mk} className="pb-2 px-2 font-mono text-center">{mk.toUpperCase()}</th>
            ))}
            <th className="pb-2 px-2 whitespace-nowrap">ورژن</th>
          </tr>
        </thead>
        <tbody>
          {comparisons.map((c, i) => {
            const label = `${c.model_type}/${c.symbol}`;
            return (
              <tr key={`${c.model_type}-${c.symbol}-${i}`} className="border-b border-surface-800/30 hover:bg-white/5">
                <td className="py-2.5 px-2 font-bold text-surface-200">{c.model_type}</td>
                <td className="py-2.5 px-2 text-surface-400">{c.symbol}</td>
                {orderedMetrics.filter(mk => metricKeys.has(mk)).map(mk => {
                  const v = c.metrics?.[mk];
                  const isBest = bestModel[mk] === label;
                  return (
                    <td key={mk} className={`py-2.5 px-2 font-mono text-center ${isBest ? "text-accent-emerald font-bold" : "text-surface-300"}`}>
                      {v != null ? (mk === "r2" || mk === "accuracy" || mk === "f1" ? v.toFixed(3) : v.toFixed(4)) : "—"}
                      {isBest && <span className="mr-1 text-[9px]">👑</span>}
                    </td>
                  );
                })}
                <td className="py-2.5 px-2 text-surface-500 font-mono">{c.version || c.run_id?.slice(0, 8) || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {/* Mini metric badges */}
      <div className="flex flex-wrap gap-2 mt-4">
        {Object.entries(bestModel).map(([mk, label]) => (
          <span key={mk} className="text-[10px] bg-surface-800/50 px-2 py-1 rounded-full text-surface-400">
            🏆 بهترین <b className="text-surface-200">{mk.toUpperCase()}</b>: <span className="text-accent-emerald">{label}</span>
          </span>
        ))}
      </div>

      {/* Radar chart */}
      <ModelRadarChart comparisons={comparisons} metricKeys={Array.from(metricKeys)} />
    </div>
  );
}

// ------ Models Tab --------------------------------------------------------------------------------------------------------
function ModelsTab() {
  const { data: models, isLoading } = useQuery({
    queryKey: ["ml-models"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: MLModel[] }>("/ml/models");
      return res?.data ?? [];
    },
    refetchInterval: 60_000,
  });

  if (isLoading) return <div className="space-y-4">{[1,2,3].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}</div>;

  if (!models?.length) return (
    <div className="glass-card p-12 text-center text-surface-500">
      <p className="text-5xl mb-3">🧠</p>
      <p className="font-bold">مدلی ثبت نشده است</p>
      <p className="text-sm mt-1">از بخش آموزش جدید می‌توانید یک مدل آموزش دهید</p>
    </div>
  );

  return (
    <div className="space-y-4">
      {models.map(model => (
        <div key={model.id} className="glass-card p-5">
          <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-surface-100 text-lg">{model.name}</span>
                <span className="text-xs font-mono bg-surface-800 px-2 py-0.5 rounded-full text-surface-400">{model.id}</span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-surface-500">
                <span>📋 {model.task}</span>
                <span>🔧 {model.framework}</span>
                <span>📅 {formatDateShamsi(model.created_at)}</span>
                {model.latest_version && <span>📌 v{model.latest_version}</span>}
              </div>
            </div>
            <div className="flex gap-1 flex-wrap">
              {model.tags?.map(t => (
                <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-primary-600/10 text-primary-300">{t}</span>
              ))}
            </div>
          </div>

          {model.versions?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-2 px-2">ورژن</th>
                    <th className="pb-2 px-2">Stage</th>
                    <th className="pb-2 px-2">دقت</th>
                    <th className="pb-2 px-2">F1</th>
                    <th className="pb-2 px-2">MSE</th>
                    <th className="pb-2 px-2">MAE</th>
                    <th className="pb-2 px-2">R²</th>
                    <th className="pb-2 px-2">تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {model.versions.map((v, i) => (
                    <tr key={`${v.version}-${i}`} className="border-b border-surface-800/30 hover:bg-white/5">
                      <td className="py-2 px-2 font-mono font-bold text-surface-200">{v.version}</td>
                      <td className="py-2 px-2"><StageBadge stage={v.stage} /></td>
                      <td className="py-2 px-2 font-mono text-surface-200">{v.metrics?.accuracy != null ? `${(v.metrics.accuracy * 100).toFixed(1)}%` : "—"}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{v.metrics?.f1 != null ? v.metrics.f1.toFixed(3) : "—"}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{v.metrics?.mse != null ? v.metrics.mse.toFixed(2) : "—"}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{v.metrics?.mae != null ? v.metrics.mae.toFixed(2) : "—"}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{v.metrics?.r2 != null ? v.metrics.r2.toFixed(3) : "—"}</td>
                      <td className="py-2 px-2 text-surface-400">{formatDateShamsi(v.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ------ Runs Tab ----------------------------------------------------------------------------------------------------------
function RunsTab() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["ml-runs"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: TrainingRun[] }>("/ml/runs");
      return res?.data ?? [];
    },
    refetchInterval: 10_000,
  });

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data: featureImportance } = useQuery({
    queryKey: ["ml-feature-importance", selectedRunId],
    queryFn: async () => {
      if (!selectedRunId) return null;
      const res = await apiGet<{ success: boolean; data: Record<string, number> }>(`/ml/runs/${selectedRunId}/feature-importance`);
      return res?.data ?? null;
    },
    enabled: !!selectedRunId,
  });

  function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, string> = {
      running: "bg-accent-amber/15 text-accent-amber animate-pulse",
      completed: "bg-accent-emerald/15 text-accent-emerald",
      failed: "bg-accent-rose/15 text-accent-rose",
      cancelled: "bg-surface-600/30 text-surface-400",
    };
    return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${colors[status] || colors.failed}`}>{status}</span>;
  }

  if (isLoading) return <div className="space-y-3">{[1,2,3].map(i => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>;

  if (!runs?.length) return (
    <div className="glass-card p-12 text-center text-surface-500">
      <p className="text-5xl mb-3">⚙️</p>
      <p className="font-bold">آموزشی اجرا نشده است</p>
      <p className="text-sm mt-1">از بخش آموزش جدید می‌توانید یک آموزش را شروع کنید</p>
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div className="glass-card p-2.5 text-center">
          <p className="text-lg font-bold text-surface-100">{runs.length}</p>
          <p className="text-xs text-surface-500">کل ران‌ها</p>
        </div>
        <div className="glass-card p-2.5 text-center">
          <p className="text-lg font-bold text-accent-emerald">{runs.filter(r => r.status === "completed").length}</p>
          <p className="text-xs text-surface-500">کامل شده</p>
        </div>
        <div className="glass-card p-2.5 text-center">
          <p className="text-lg font-bold text-accent-amber">{runs.filter(r => r.status === "running").length}</p>
          <p className="text-xs text-surface-500">در حال اجرا</p>
        </div>
        <div className="glass-card p-2.5 text-center">
          <p className="text-lg font-bold text-accent-rose">{runs.filter(r => r.status === "failed").length}</p>
          <p className="text-xs text-surface-500">ناموفق</p>
        </div>
      </div>

      {runs.map(run => {
        const symbols = run.symbols || (run.symbol ? [run.symbol] : []);
        return (
          <div key={run.id} className="glass-card p-4">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-surface-200">{run.experiment_name || "بدون نام"}</span>
                  <StatusBadge status={run.status} />
                  <span className="text-xs font-mono text-surface-500">{run.id}</span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-surface-500 flex-wrap">
                  <span>🤖 {run.model_type}</span>
                  {symbols.length > 0 && <span>📊 {symbols.join(", ")}</span>}
                  {run.train_samples != null && <span>📈 {run.train_samples.toLocaleString("fa-IR")} نمونه</span>}
                </div>
              </div>
              {run.status === "completed" && run.id && (
                <button
                  onClick={() => setSelectedRunId(selectedRunId === run.id ? null : run.id)}
                  className={`text-[10px] px-2 py-1 rounded-lg transition-colors ${
                    selectedRunId === run.id ? "bg-primary-600/30 text-primary-300" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}
                >
                  {selectedRunId === run.id ? "بستن اهمیت" : "اهمیت ویژگی‌ها"}
                </button>
              )}
            </div>
            {run.metrics && Object.keys(run.metrics).length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-surface-800/50">
                {Object.entries(run.metrics).map(([k, v]) => (
                  <span key={k} className="text-xs bg-surface-800/50 px-2 py-1 rounded-lg">
                    <span className="text-surface-500">{k}:</span>{" "}
                    <span className={`font-mono ${k === "r2" || k === "accuracy" ? "text-accent-emerald" : "text-surface-200"}`}>
                      {typeof v === "number" ? (k === "r2" || k === "accuracy" ? (v * 100).toFixed(1) + "%" : v.toFixed(4)) : String(v)}
                    </span>
                  </span>
                ))}
              </div>
            )}
            {/* Feature importance inline */}
            {selectedRunId === run.id && featureImportance && Object.keys(featureImportance).length > 0 && (
              <FeatureImportanceChart data={featureImportance} />
            )}
            {selectedRunId === run.id && (!featureImportance || Object.keys(featureImportance).length === 0) && (
              <p className="text-[10px] text-surface-500 mt-2">اطلاعات اهمیت ویژگی‌ها در دسترس نیست</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------ Symbol Search -----------------------------------------------------------------------------------------------------
interface SymbolOption {
  symbol: string;
  name: string;
}

function SymbolSearchInput({ value, onChange }: { value: string; onChange: (symbol: string) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const { data: suggestions = [] } = useQuery({
    queryKey: ["symbol-search", query],
    queryFn: async () => {
      if (!query.trim()) return [];
      const res = await apiGet<{ success: boolean; data: { items: SymbolOption[] } }>(`/symbols/search?q=${encodeURIComponent(query)}&page_size=10`);
      return res?.data?.items ?? [];
    },
    enabled: query.trim().length >= 1,
    staleTime: 30_000,
  });

  return (
    <div className="relative">
      <input value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        placeholder="جستجوی نماد..."
        className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500" />
      {open && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-surface-800 border border-surface-700 rounded-lg shadow-xl max-h-48 overflow-y-auto">
          {suggestions.map((s: SymbolOption) => (
            <button key={s.symbol} onMouseDown={() => { onChange(s.symbol); setQuery(s.symbol); setOpen(false); }}
              className="w-full text-right px-3 py-2 text-sm text-surface-200 hover:bg-primary-600/20 transition-colors flex items-center justify-between">
              <span>{s.symbol}</span>
              <span className="text-[10px] text-surface-500 truncate max-w-[200px]">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ------ Prediction Results Table (real data from predict-all) ------------------------------------------------------------------
interface PredictionResult {
  symbol: string;
  model_type: string;
  prediction: number;
  accuracy: number;
  confidence: number;
  f1_score: number;
  mse: number;
  samples: number;
  duration_seconds: number;
  timestamp: string;
  batch_id: string;
  // Real prediction extra fields
  predicted_change_pct?: number;
  last_price?: number;
  feature_importance?: Record<string, number>;
  model_loaded_from?: string;
  prediction_failed?: boolean;
}

function PredictionResults({ symbolSearch }: { symbolSearch: string }) {
  const { data: results = [], isLoading } = useQuery({
    queryKey: ["ml-predictions", symbolSearch],
    queryFn: async () => {
      const endpoint = symbolSearch.trim() ? `/ml/predictions?symbol=${encodeURIComponent(symbolSearch.trim())}` : "/ml/predictions";
      const res = await apiGet<{ success: boolean; data: PredictionResult[] }>(endpoint);
      return res?.data ?? [];
    },
    refetchInterval: 30_000,
  });

  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  if (isLoading) return <div className="text-center text-surface-500 py-4">در حال بارگذاری...</div>;

  if (!results.length) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-right text-xs">
        <thead>
          <tr className="text-surface-500 border-b border-surface-700">
            <th className="pb-2 px-2">نماد</th>
            <th className="pb-2 px-2">مدل</th>
            <th className="pb-2 px-2">پیش‌بینی</th>
            <th className="pb-2 px-2">قیمت فعلی</th>
            <th className="pb-2 px-2">تغییر پیش‌بینی</th>
            <th className="pb-2 px-2">اطمینان</th>
            <th className="pb-2 px-2">نمونه</th>
            <th className="pb-2 px-2">منبع</th>
            <th className="pb-2 px-2">جزئیات</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const isExpanded = expandedSymbol === r.symbol;
            return (
              <React.Fragment key={`${r.symbol}-${i}`}>
                <tr className={`border-b border-surface-800/30 hover:bg-white/5 ${r.prediction_failed ? "opacity-50" : ""}`}>
                  <td className="py-2.5 px-2 font-bold text-surface-200">
                    {r.symbol}
                    {r.prediction_failed && <span className="mr-1 text-accent-rose" title="پیش‌بینی ناموفق">⚠️</span>}
                  </td>
                  <td className="py-2.5 px-2 text-surface-400">{r.model_type}</td>
                  <td className="py-2.5 px-2 font-mono text-accent-cyan">
                    {r.prediction ? r.prediction.toLocaleString("fa-IR") : "—"}
                  </td>
                  <td className="py-2.5 px-2 font-mono text-surface-300">
                    {r.last_price != null ? r.last_price.toLocaleString("fa-IR") : "—"}
                  </td>
                  <td className="py-2.5 px-2">
                    {r.predicted_change_pct != null ? (
                      <span className={`font-mono font-bold ${r.predicted_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {r.predicted_change_pct >= 0 ? "+" : ""}{r.predicted_change_pct.toFixed(2)}%
                      </span>
                    ) : "—"}
                  </td>
                  <td className="py-2.5 px-2">
                    <div className="flex items-center gap-1">
                      <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${r.confidence >= 0.8 ? "bg-accent-emerald" : r.confidence >= 0.7 ? "bg-accent-amber" : "bg-accent-rose"}`}
                          style={{ width: `${r.confidence * 100}%` }}
                        />
                      </div>
                      <span className="font-mono text-surface-300 text-[10px]">{(r.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-2.5 px-2 font-mono text-surface-400">
                    {r.samples ? r.samples.toLocaleString("fa-IR") : "—"}
                  </td>
                  <td className="py-2.5 px-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      r.model_loaded_from === "artifact" ? "bg-accent-emerald/15 text-accent-emerald" :
                      r.model_loaded_from === "fallback-mock" ? "bg-accent-rose/15 text-accent-rose" :
                      "bg-primary-600/15 text-primary-300"
                    }`}>
                      {r.model_loaded_from === "artifact" ? "مدل آموزش‌دیده" :
                       r.model_loaded_from === "untrained" ? "مدل خام" :
                       r.model_loaded_from === "fallback-mock" ? "شبیه‌سازی" :
                       r.model_loaded_from || "—"}
                    </span>
                  </td>
                  <td className="py-2.5 px-2">
                    {r.feature_importance && Object.keys(r.feature_importance).length > 0 && (
                      <button
                        onClick={() => setExpandedSymbol(isExpanded ? null : r.symbol)}
                        className={`text-[10px] px-2 py-1 rounded-lg transition-colors ${
                          isExpanded ? "bg-primary-600/30 text-primary-300" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                        }`}
                      >
                        {isExpanded ? "بستن" : "اهمیت ویژگی‌ها"}
                      </button>
                    )}
                  </td>
                </tr>
                {isExpanded && r.feature_importance && Object.keys(r.feature_importance).length > 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 pb-3">
                      <FeatureImportanceChart data={r.feature_importance} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
      {/* Summary stats */}
      <div className="flex flex-wrap gap-2 mt-3 text-[10px] text-surface-500">
        <span>✅ موفق: {results.filter(r => !r.prediction_failed).length}</span>
        <span>❌ ناموفق: {results.filter(r => r.prediction_failed).length}</span>
        <span>⏱ میانگین زمان: {results.length > 0
          ? (results.reduce((s, r) => s + r.duration_seconds, 0) / results.length).toFixed(2) + "ث"
          : "—"}</span>
      </div>
    </div>
  );
}

// ------ Animated Progress Bar Component -----------------------------------------------------------------------------------
function ProgressBar({ label, isIndeterminate = true, elapsed = 0 }: { label: string; isIndeterminate?: boolean; elapsed?: number }) {
  const formatElapsed = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return mins > 0 ? mins + ":" + secs.toString().padStart(2, "0") : secs + "ث";
  };

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="material-icons text-accent-amber animate-spin text-sm">refresh</span>
          <span className="text-sm font-bold text-surface-200">{label}</span>
        </div>
        <span className="text-[10px] font-mono text-surface-500">⏱ {formatElapsed(elapsed)}</span>
      </div>
      <div className="h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
        {isIndeterminate ? (
          <div className="h-full w-full bg-gradient-to-r from-primary-600 via-accent-cyan to-primary-600 rounded-full animate-progress" />
        ) : (
          <div className="h-full bg-accent-emerald rounded-full transition-all duration-500" style={{ width: "100%" }} />
        )}
      </div>
      <div className="flex justify-between mt-1.5">
        <span className="text-[9px] text-surface-500">در حال پردازش...</span>
        <span className="text-[9px] text-surface-500">لطفاً صبر کنید</span>
      </div>
    </div>
  );
}

// ------ Train Tab ---------------------------------------------------------------------------------------------------------
function TrainTab() {
  const queryClient = useQueryClient();
  const allSymbols = useAllSymbols();
  const [form, setForm] = useState({
    experiment_name: "",
    model_type: "xgboost",
    symbols: ["فولاد"],
    start_date: "",
    end_date: "",
  });
  const [symbolInput, setSymbolInput] = useState("");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [showResults, setShowResults] = useState(false);
  const [lastTrainResult, setLastTrainResult] = useState<TrainResponse | null>(null);
  interface TrainAllData {
    model_type: string;
    total_symbols: number;
    successful: number;
    failed: number;
    total_duration_seconds: number;
    best_r2: number | null;
    best_symbol: string | null;
    avg_r2: number | null;
    data_source?: string;
    results: Array<{
      symbol: string;
      success: boolean;
      run_id?: string;
      metrics?: Record<string, number>;
      duration_seconds: number;
      error?: string;
    }>;
  }
  const [lastTrainAllResult, setLastTrainAllResult] = useState<TrainAllData | null>(null);

  const trainMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      return apiPost<TrainResponse>("/ml/train", data);
    },
    retry: false,
    onSuccess: (res) => {
      toast.success("آموزش با موفقیت کامل شد");
      queryClient.invalidateQueries({ queryKey: ["ml-runs"] });
      queryClient.invalidateQueries({ queryKey: ["ml-comparison"] });
      setLastTrainResult(res || null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const predictAllMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      return apiPost<{ success: boolean; data: { batch_id: string; results: PredictionResult[]; successful?: number; failed?: number; total_duration_seconds?: number } }>("/ml/predict-all", data);
    },
    retry: false,
    onSuccess: (res) => {
      const data = res?.data;
      const count = data?.results?.length ?? 0;
      const successful = data?.successful ?? count;
      const failed = data?.failed ?? 0;
      const duration = data?.total_duration_seconds;
      const msg = failed > 0
        ? "✅ " + successful + " موفق / ❌ " + failed + " ناموفق از " + count + " نماد" + (duration ? " در " + duration.toFixed(1) + "ثانیه" : "")
        : "✅ پیش‌بینی " + count + " نماد با موفقیت انجام شد" + (duration ? " در " + duration.toFixed(1) + "ثانیه" : "");
      toast.success(msg);
      queryClient.invalidateQueries({ queryKey: ["ml-predictions"] });
      setShowResults(true);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // ── Train-All Mutation ──
  const trainAllMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      return apiPost<{ success: boolean; data: {
        model_type: string;
        total_symbols: number;
        successful: number;
        failed: number;
        total_duration_seconds: number;
        best_r2: number | null;
        best_symbol: string | null;
        avg_r2: number | null;
        results: Array<{
          symbol: string;
          success: boolean;
          run_id?: string;
          metrics?: Record<string, number>;
          duration_seconds: number;
          error?: string;
        }>;
      } }>("/ml/train-all", data);
    },
    retry: false,
    onSuccess: (res) => {
      const data = res?.data;
      if (!data) return;
      const msg = data.failed > 0
        ? "✅ آموزش " + data.successful + " موفق / ❌ " + data.failed + " ناموفق از " + data.total_symbols + " نماد" + (data.best_symbol ? " — بهترین: " + data.best_symbol + " (R²=" + (data.best_r2?.toFixed(3) ?? "") + ")" : "") + " در " + data.total_duration_seconds.toFixed(1) + "ثانیه"
        : "✅ آموزش " + data.successful + " نماد با موفقیت انجام شد" + (data.best_symbol ? " — بهترین: " + data.best_symbol + " (R²=" + (data.best_r2?.toFixed(3) ?? "") + ")" : "") + " در " + data.total_duration_seconds.toFixed(1) + "ثانیه";
      toast.success(msg);
      setLastTrainAllResult(data);
      queryClient.invalidateQueries({ queryKey: ["ml-runs"] });
      queryClient.invalidateQueries({ queryKey: ["ml-comparison"] });
      queryClient.invalidateQueries({ queryKey: ["ml-models"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // ── Progress bar timers ──
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  React.useEffect(() => {
    if (predictAllMutation.isPending) {
      setElapsed(0);
      elapsedRef.current = setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);
    } else {
      if (elapsedRef.current) {
        clearInterval(elapsedRef.current);
        elapsedRef.current = null;
      }
      if (!predictAllMutation.isPending && !predictAllMutation.isSuccess && !predictAllMutation.isError) {
        setElapsed(0);
      }
    }
    return () => {
      if (elapsedRef.current) {
        clearInterval(elapsedRef.current);
        elapsedRef.current = null;
      }
    };
  }, [predictAllMutation.isPending]);

  const [elapsedTrainAll, setElapsedTrainAll] = useState(0);
  const elapsedTrainAllRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  React.useEffect(() => {
    if (trainAllMutation.isPending) {
      setElapsedTrainAll(0);
      elapsedTrainAllRef.current = setInterval(() => {
        setElapsedTrainAll(prev => prev + 1);
      }, 1000);
    } else {
      if (elapsedTrainAllRef.current) {
        clearInterval(elapsedTrainAllRef.current);
        elapsedTrainAllRef.current = null;
      }
      if (!trainAllMutation.isPending && !trainAllMutation.isSuccess && !trainAllMutation.isError) {
        setElapsedTrainAll(0);
      }
    }
    return () => {
      if (elapsedTrainAllRef.current) {
        clearInterval(elapsedTrainAllRef.current);
        elapsedTrainAllRef.current = null;
      }
    };
  }, [trainAllMutation.isPending]);

  const addSymbol = () => {
    const s = symbolInput.trim();
    if (s && !form.symbols.includes(s)) {
      setForm(prev => ({ ...prev, symbols: [...prev.symbols, s] }));
      setSymbolInput("");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* ── Training Form ── */}
      <Card title="🚀 آموزش مدل جدید با داده واقعی">
        <div className="space-y-4">
          {/* Experiment Name */}
          <div>
            <label className="block text-xs text-surface-400 mb-1.5 font-bold">نام آزمایش</label>
            <input value={form.experiment_name} onChange={e => setForm(prev => ({ ...prev, experiment_name: e.target.value }))}
              placeholder="مثلاً: xgboost-v1-فولاد"
              className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-surface-200 outline-none focus:border-primary-500" />
          </div>

          {/* Model Type */}
          <div>
            <label className="block text-xs text-surface-400 mb-1.5 font-bold">نوع مدل</label>
            <div className="flex flex-wrap gap-2">
              {MODEL_TYPES.map(mt => (
                <button key={mt} onClick={() => setForm(prev => ({ ...prev, model_type: mt }))}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.model_type === mt ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}>{mt}</button>
              ))}
            </div>
          </div>

          {/* Symbols */}
          <div>
            <label className="block text-xs text-surface-400 mb-1.5 font-bold">نماد (ها)</label>
            <div className="flex gap-2 mb-2">
              <input value={symbolInput} onChange={e => setSymbolInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addSymbol()}
                placeholder="نام نماد"
                className="flex-1 bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500" />
              <button onClick={addSymbol} className="px-3 py-2 bg-surface-700 hover:bg-surface-600 text-surface-200 rounded-lg text-sm transition-colors">+</button>
            </div>
            <div className="flex flex-wrap gap-1">
              {form.symbols.map(s => (
                <span key={s} className="inline-flex items-center gap-1 text-xs bg-primary-600/20 text-primary-300 px-2 py-1 rounded-full">
                  {s}
                  <button onClick={() => setForm(prev => ({ ...prev, symbols: prev.symbols.filter(x => x !== s) }))}
                    className="text-primary-400 hover:text-primary-200">✕</button>
                </span>
              ))}
            </div>
            <div className="flex gap-1 mt-2 flex-wrap">
              {allSymbols.filter(s => !form.symbols.includes(s)).slice(0, 20).map(s => (
                <button key={s} onClick={() => setForm(prev => ({ ...prev, symbols: [...prev.symbols, s] }))}
                  className="text-[10px] px-2 py-0.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-full transition-colors">+{s}</button>
              ))}
              {allSymbols.length > 20 && <span className="text-[10px] text-surface-500">+{allSymbols.length - 20} نماد دیگر</span>}
            </div>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-surface-400 mb-1.5 font-bold">از تاریخ</label>
              <input type="date" value={form.start_date} onChange={e => setForm(prev => ({ ...prev, start_date: e.target.value }))}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="block text-xs text-surface-400 mb-1.5 font-bold">تا تاریخ</label>
              <input type="date" value={form.end_date} onChange={e => setForm(prev => ({ ...prev, end_date: e.target.value }))}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500" />
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => trainMutation.mutate({
              experiment_name: form.experiment_name,
              model_type: form.model_type,
              symbols: form.symbols,
              start_date: form.start_date,
              end_date: form.end_date,
              target: "price_change_pct",
            })} disabled={trainMutation.isPending || form.symbols.length === 0}
              className="flex-1 py-3 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl font-bold transition-all flex items-center justify-center gap-2">
              {trainMutation.isPending ? (
                <><span className="material-icons animate-spin text-sm">refresh</span> در حال آموزش...</>
              ) : "شروع آموزش واقعی 🚀"}
            </button>

            <button onClick={() => trainAllMutation.mutate({ model_type: form.model_type, max_concurrency: 5 })} disabled={trainAllMutation.isPending}
              className="px-5 py-3 bg-accent-emerald/20 hover:bg-accent-emerald/30 border border-accent-emerald/30 text-accent-emerald rounded-xl font-bold transition-all flex items-center justify-center gap-2">
              {trainAllMutation.isPending ? (
                <><span className="material-icons animate-spin text-sm">refresh</span> آموزش...</>
              ) : "🧪 آموزش همه نمادها"}
            </button>

            <button onClick={() => predictAllMutation.mutate({ model_type: form.model_type, max_concurrency: 50 })} disabled={predictAllMutation.isPending}
              className="px-5 py-3 bg-accent-amber/20 hover:bg-accent-amber/30 border border-accent-amber/30 text-accent-amber rounded-xl font-bold transition-all flex items-center justify-center gap-2">
              {predictAllMutation.isPending ? (
                <><span className="material-icons animate-spin text-sm">refresh</span> آزمایش...</>
              ) : "🧪 آزمایش همه نمادها"}
            </button>
          </div>

          {/* Training result */}
          {lastTrainResult && (
            <div className="bg-accent-emerald/10 border border-accent-emerald/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-emerald">✅</span>
                <span className="font-bold text-surface-200 text-sm">{lastTrainResult.message}</span>
              </div>
              <div className="text-xs text-surface-400 space-y-1">
                <p>شناسه: <span className="font-mono text-surface-300">{lastTrainResult.run_id}</span></p>
                <p>وضعیت: <span className="text-accent-emerald">{lastTrainResult.status}</span></p>
              </div>
            </div>
          )}

          {trainMutation.isError && (
            <div className="bg-accent-rose/10 border border-accent-rose/20 rounded-xl p-4 text-accent-rose text-sm">
              خطا: {(trainMutation.error as Error)?.message || "آموزش ناموفق"}
            </div>
          )}
        </div>
      </Card>

      {/* ── Progress Bars ── */}
      {trainAllMutation.isPending && (
        <ProgressBar label="🧪 آموزش همه نمادها (CPU-intensive)" elapsed={elapsedTrainAll} />
      )}
      {predictAllMutation.isPending && (
        <ProgressBar label="🧪 آزمایش همه نمادها" elapsed={elapsed} />
      )}

      {/* ── Train-All Results ── */}
      {lastTrainAllResult && !trainAllMutation.isPending && (
        <Card title="📊 نتایج آموزش روی همه نمادها" subtitle={lastTrainAllResult.data_source === "database" ? "داده‌های واقعی از دیتابیس" : "نمادهای پیش‌فرض"}>
          <div className="space-y-4">
            {/* Stats overview */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="glass-card p-3 text-center">
                <p className="text-lg font-bold text-surface-100">{String(lastTrainAllResult.total_symbols ?? "—")}</p>
                <p className="text-[10px] text-surface-500">کل نمادها</p>
              </div>
              <div className="glass-card p-3 text-center">
                <p className="text-lg font-bold text-accent-emerald">{String(lastTrainAllResult.successful ?? "—")}</p>
                <p className="text-[10px] text-surface-500">موفق</p>
              </div>
              <div className="glass-card p-3 text-center">
                <p className="text-lg font-bold text-accent-rose">{String(lastTrainAllResult.failed ?? "—")}</p>
                <p className="text-[10px] text-surface-500">ناموفق</p>
              </div>
              <div className="glass-card p-3 text-center">
                <p className="text-lg font-bold text-primary-300">{(lastTrainAllResult.total_duration_seconds as number)?.toFixed(1) ?? "—"}ث</p>
                <p className="text-[10px] text-surface-500">زمان کل</p>
              </div>
            </div>

            {/* Best / Average R² */}
            {(lastTrainAllResult.best_r2 != null || lastTrainAllResult.avg_r2 != null) && (
              <div className="flex flex-wrap gap-3">
                {lastTrainAllResult.best_symbol && (
                  <span className="text-xs bg-accent-emerald/15 text-accent-emerald px-3 py-1.5 rounded-lg font-bold">
                    🏆 بهترین: {String(lastTrainAllResult.best_symbol)} — R²={(lastTrainAllResult.best_r2 as number)?.toFixed(4)}
                  </span>
                )}
                {lastTrainAllResult.avg_r2 != null && (
                  <span className="text-xs bg-primary-600/15 text-primary-300 px-3 py-1.5 rounded-lg font-bold">
                    📊 میانگین R²: {(lastTrainAllResult.avg_r2 as number).toFixed(4)}
                  </span>
                )}
              </div>
            )}

            {/* Results table */}
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="pb-2 px-2">#</th>
                    <th className="pb-2 px-2">نماد</th>
                    <th className="pb-2 px-2">وضعیت</th>
                    <th className="pb-2 px-2">R²</th>
                    <th className="pb-2 px-2">MSE</th>
                    <th className="pb-2 px-2">MAE</th>
                    <th className="pb-2 px-2">MAPE</th>
                    <th className="pb-2 px-2">زمان</th>
                    <th className="pb-2 px-2">Run ID</th>
                  </tr>
                </thead>
                <tbody>
                  {(lastTrainAllResult.results as Array<Record<string, unknown>>)?.map((r: Record<string, unknown>, i: number) => {
                    const metrics = (r.metrics as Record<string, number>) || {};
                    return (
                      <tr key={r.symbol as string || i} className={`border-b border-surface-800/30 hover:bg-white/5 ${r.success ? "" : "opacity-50"}`}>
                        <td className="py-2.5 px-2 font-mono text-surface-500">{i + 1}</td>
                        <td className="py-2.5 px-2 font-bold text-surface-200">{String(r.symbol ?? "")}</td>
                        <td className="py-2.5 px-2">
                          {r.success ? (
                            <span className="text-accent-emerald text-[10px] px-1.5 py-0.5 rounded-full bg-accent-emerald/15">✅ موفق</span>
                          ) : (
                            <span className="text-accent-rose text-[10px] px-1.5 py-0.5 rounded-full bg-accent-rose/15">❌ {String(r.error ?? "خطا")}</span>
                          )}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-surface-300">{metrics.r2 != null ? metrics.r2.toFixed(4) : "—"}</td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">{metrics.mse != null ? metrics.mse.toFixed(4) : "—"}</td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">{metrics.mae != null ? metrics.mae.toFixed(4) : "—"}</td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">{metrics.mape != null ? metrics.mape.toFixed(2) + "%" : "—"}</td>
                        <td className="py-2.5 px-2 font-mono text-surface-400">{(r.duration_seconds as number)?.toFixed(1) ?? "—"}ث</td>
                        <td className="py-2.5 px-2 font-mono text-surface-500 text-[9px]">{(r.run_id as string)?.slice(0, 8) ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
      )}

      {/* ── Prediction Results ── */}
      {showResults && (
        <Card title="📊 نتایج آزمایش نمادها" subtitle="نتایج پیش‌بینی مدل روی نمادهای مختلف">
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-surface-400 mb-1.5 font-bold">جستجوی نماد در نتایج</label>
              <SymbolSearchInput value={symbolSearch} onChange={setSymbolSearch} />
            </div>
            <PredictionResults symbolSearch={symbolSearch} />
          </div>
        </Card>
      )}
    </div>
  );
}

// ------ Predict Tab (with Real Prediction + Feature Importance) ------------------------------------------------------------
const MOCK_MODELS = [
  { id: "linear_regression", name: "Linear Regression", task: "regression", color: "text-accent-cyan" },
  { id: "random_forest", name: "Random Forest", task: "regression", color: "text-accent-emerald" },
  { id: "xgboost", name: "XGBoost", task: "regression", color: "text-accent-amber" },
  { id: "logistic_regression", name: "Logistic Regression", task: "classification", color: "text-accent-purple" },
];

function PredictTab() {
  const allSymbols = useAllSymbols();
  const [selectedModel, setSelectedModel] = useState("xgboost");
  const [symbol, setSymbol] = useState("فولاد");
  const [predictionMode, setPredictionMode] = useState<"mock" | "real">("real");

  const { data: prediction, isLoading, error, refetch } = useQuery({
    queryKey: ["ml-predict-real", selectedModel, symbol, predictionMode],
    queryFn: async () => {
      if (predictionMode === "real") {
        const res = await apiPost<{ success: boolean; data: Record<string, unknown> }>("/ml/predict-real", {
          model_id: selectedModel,
          symbol: symbol,
        });
        if (!res?.success) throw new Error("پیش‌بینی واقعی ناموفق");
        return res.data;
      } else {
        const res = await apiPost<{ success: boolean; data: { prediction: number; confidence: number; metadata?: Record<string, unknown> } }>(
          `/ml/predict/${selectedModel}`, {}
        );
        if (!res?.success) throw new Error("Prediction failed");
        return res.data as unknown as Record<string, unknown>;
      }
    },
    enabled: false,
    retry: false,
  });

  const featureImportance = prediction?.feature_importance as Record<string, number> | undefined;

  return (
    <div className="space-y-5">
      <Card title="🔮 پیش‌بینی قیمت">
        <div className="space-y-4">
          {/* Mode toggle */}
          <div className="flex gap-2 bg-surface-800/50 rounded-lg p-1 w-fit">
            <button
              onClick={() => setPredictionMode("real")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                predictionMode === "real" ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"
              }`}
            >
              🎯 واقعی
            </button>
            <button
              onClick={() => setPredictionMode("mock")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                predictionMode === "mock" ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"
              }`}
            >
              🧪 آزمایشی
            </button>
          </div>

          {/* Model selector */}
          <label className="block text-xs text-surface-400 mb-1 font-bold">انتخاب مدل</label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {MOCK_MODELS.map(m => (
              <button key={m.id} onClick={() => setSelectedModel(m.id)}
                className={`p-3 rounded-xl text-center transition-all border ${
                  selectedModel === m.id ? "bg-primary-600/20 border-primary-600/50" : "bg-surface-800/50 border-surface-700 hover:bg-surface-800"
                }`}>
                <p className={`text-xs font-bold ${m.color}`}>{m.name}</p>
                <p className="text-[10px] text-surface-500 mt-0.5">{m.task}</p>
              </button>
            ))}
          </div>

          {/* Symbol input */}
          <div>
            <label className="block text-xs text-surface-400 mb-1.5 font-bold">نماد</label>
            <div className="flex gap-2">
              <select value={symbol} onChange={e => setSymbol(e.target.value)}
                className="flex-1 bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500">
                {allSymbols.length === 0 && <option value="فولاد">فولاد</option>}
                {allSymbols.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <button onClick={() => refetch()} disabled={isLoading}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-lg text-sm font-bold transition-all flex items-center gap-2">
                {isLoading ? <span className="material-icons animate-spin text-sm">refresh</span> : <span className="material-icons text-sm">psychology</span>}
                پیش‌بینی
              </button>
            </div>
          </div>

          {/* Result */}
          {isLoading && (
            <div className="glass-card p-6 text-center">
              <div className="animate-pulse space-y-2">
                <div className="h-8 w-32 bg-surface-700 rounded mx-auto" />
                <div className="h-4 w-48 bg-surface-700 rounded mx-auto" />
              </div>
            </div>
          )}

          {error && !isLoading && (
            <div className="glass-card p-6 text-center text-accent-rose">
              <p className="text-3xl mb-2">⚠️</p>
              <p className="text-sm">خطا در پیش‌بینی</p>
            </div>
          )}

          {prediction && !isLoading && (
            <div className="glass-card p-6">
              <div className="text-center">
                <p className="text-xs text-surface-500 mb-1">
                  {predictionMode === "real" ? "قیمت پیش‌بینی شده" : "قیمت شبیه‌سازی شده"} برای {symbol}
                </p>
                <p className="text-3xl font-black font-mono text-surface-100">
                  {typeof prediction.prediction === "number" ? prediction.prediction.toLocaleString("fa-IR") : String(prediction.prediction ?? "—")}
                </p>

                {predictionMode === "real" && !!prediction.last_price && (
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-surface-500">
                      قیمت فعلی: <span className="font-mono text-surface-300">{(prediction.last_price as number).toLocaleString("fa-IR")}</span>
                    </p>
                    {prediction.predicted_change_pct != null && (
                      <p className={`text-sm font-bold font-mono ${
                        (prediction.predicted_change_pct as number) >= 0 ? "text-accent-emerald" : "text-accent-rose"
                      }`}>
                        تغییر پیش‌بینی شده: {(prediction.predicted_change_pct as number) >= 0 ? "+" : ""}{(prediction.predicted_change_pct as number).toFixed(2)}%
                      </p>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-center gap-4 mt-3 text-sm">
                  <div>
                    <span className="text-xs text-surface-500">اطمینان: </span>
                    <span className="font-mono font-bold text-surface-200">{((prediction.confidence as number ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  {prediction.model_id ? (
                    <div>
                      <span className="text-xs text-surface-500">مدل: </span>
                      <span className="font-mono text-surface-400">{String(prediction.model_id)}</span>
                    </div>
                  ) : null}
                  {prediction.samples ? (
                    <div>
                      <span className="text-xs text-surface-500">داده: </span>
                      <span className="font-mono text-surface-400">{Number(prediction.samples).toLocaleString("fa-IR")} روز</span>
                    </div>
                  ) : null}
                </div>
              </div>

              {/* Feature importance bar chart */}
              {predictionMode === "real" && featureImportance && Object.keys(featureImportance).length > 0 && (
                <FeatureImportanceChart data={featureImportance} />
              )}
            </div>
          )}

          {!prediction && !isLoading && !error && (
            <div className="glass-card p-8 text-center text-surface-500">
              <p className="text-4xl mb-2">🔮</p>
              <p>یک مدل را انتخاب کنید و دکمه پیش‌بینی را بزنید</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------------
export default function MLPage() {
  const [tab, setTab] = useState<MLTab>("models");

  return (
    <AppLayout title="🧠 داشبورد یادگیری ماشین" subtitle="مدیریت مدل‌ها، آموزش واقعی و پیش‌بینی با داده‌های بازار">
      {/* Tab Navigation */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              tab === t.key ? "bg-primary-600 text-white shadow-lg" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}>
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "models" && <ModelsTab />}
      {tab === "compare" && <ComparisonTab />}
      {tab === "runs" && <RunsTab />}
      {tab === "train" && <TrainTab />}
      {tab === "predict" && <PredictTab />}
    </AppLayout>
  );
}
