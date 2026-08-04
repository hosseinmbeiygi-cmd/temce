"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiPost, apiGet } from "@/lib/api";
import BacktestResultsDashboard, { type BacktestResultData } from "@/components/charts/BacktestResultsDashboard";

interface MLBacktestFold {
  metrics?: Record<string, number>;
  r2?: number;
  mae?: number;
  rmse?: number;
  directional_accuracy?: number;
  train_size?: number | null;
  test_size?: number | null;
}

interface MLBacktestResult extends Partial<BacktestResultData> {
  folds?: MLBacktestFold[];
  feature_importance?: Record<string, number>;
  n_folds?: number;
  aggregate_metrics?: Record<string, number>;
  mean_r2?: number | null;
  mean_mae?: number | null;
  mean_rmse?: number | null;
  mean_directional_accuracy?: number | null;
  directional_accuracy?: number | null;
}

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

const FEATURE_GROUPS = [
  { value: "price", label: "قیمت", icon: "💵" },
  { value: "technical", label: "تکنیکال", icon: "📈" },
  { value: "trades", label: "حقیقی/حقوقی", icon: "🔄" },
  { value: "microstructure", label: "ریزساختار", icon: "🔬" },
  { value: "all", label: "همه", icon: "📊" },
];

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

export default function MLBacktestTab() {
  const { data: allSymbols = [] } = useAllSymbols();
  const [btSymbol, setBtSymbol] = useState("فولاد");
  const [btModel, setBtModel] = useState("xgboost");
  const [btSplits, setBtSplits] = useState(5);
  const [btResult, setBtResult] = useState<MLBacktestResult | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btFeatureGroups, setBtFeatureGroups] = useState<string[]>(["price", "technical"]);

  const toggleFeatureGroup = (fg: string) => {
    if (fg === "all") { setBtFeatureGroups(["all"]); return; }
    setBtFeatureGroups(prev => {
      const next = prev.includes(fg) ? prev.filter(x => x !== fg) : [...prev.filter(x => x !== "all"), fg];
      return next.length === 0 ? ["price"] : next;
    });
  };

  const handleRunBacktest = async () => {
    setBtLoading(true);
    try {
      const res = await apiPost<{ success: boolean; data: MLBacktestResult }>("/ml/backtest", {
        symbol: btSymbol,
        model_type: btModel,
        n_splits: btSplits,
        feature_groups: btFeatureGroups.includes("all")
          ? ["price", "technical", "trades", "microstructure"]
          : btFeatureGroups,
      });
      setBtResult(res?.data ?? null);
      if (res?.success) toast.success("✅ بک‌تست انجام شد");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "خطا در بک‌آزمون");
      setBtResult(null);
    }
    setBtLoading(false);
  };

  return (
    <div className="space-y-5">
      {/* ── Controls ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-[10px] text-surface-500 font-bold mb-1.5">📊 نماد</label>
          <select value={btSymbol} onChange={e => setBtSymbol(e.target.value)}
            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500">
            {allSymbols.slice(0, 200).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-[10px] text-surface-500 font-bold mb-1.5">🤖 مدل</label>
          <select value={btModel} onChange={e => setBtModel(e.target.value)}
            className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 outline-none focus:border-primary-500">
            {ALL_MODELS.map(m => <option key={m} value={m}>{MODEL_META[m]?.icon || "🔧"} {m}</option>)}
          </select>
        </div>
        <div className="glass-card p-4 rounded-2xl">
          <label className="block text-[10px] text-surface-500 font-bold mb-1.5">📐 Fold‌ها</label>
          <div className="flex gap-1">
            {[3, 5, 10].map(n => (
              <button key={n} onClick={() => setBtSplits(n)}
                className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                  btSplits === n
                    ? "bg-primary-600/30 text-primary-300"
                    : "bg-surface-800 text-surface-500 hover:text-surface-300"
                }`}>{n}</button>
            ))}
          </div>
        </div>
        <div className="glass-card p-4 rounded-2xl flex items-end">
          <button onClick={handleRunBacktest} disabled={btLoading}
            className="w-full py-3 rounded-xl text-sm font-bold bg-accent-amber/15 text-accent-amber border border-accent-amber/30 hover:bg-accent-amber/25 transition-all disabled:opacity-40 flex items-center justify-center gap-2">
            {btLoading ? (
              <><span className="material-icons animate-spin text-sm">⏳</span> در حال اجرا...</>
            ) : "🚀 اجرای بک‌تست"}
          </button>
        </div>
      </div>

      {/* ── Feature Groups ── */}
      <div className="flex flex-wrap gap-1.5">
        <span className="text-[9px] text-surface-500 self-center ml-1">🧩 گروه ویژگی:</span>
        {FEATURE_GROUPS.map(fg => (
          <button key={fg.value} onClick={() => toggleFeatureGroup(fg.value)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all border ${
              btFeatureGroups.includes(fg.value) || (fg.value === "all" && btFeatureGroups.length > 3)
                ? "bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan"
                : "bg-surface-800/50 border-surface-700/50 text-surface-400 hover:bg-surface-800"
            }`}>
            {fg.icon} {fg.label}
          </button>
        ))}
      </div>

      {/* ── Results ── */}
      {btLoading && (
        <div className="space-y-3">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      )}

      {btResult && !btLoading && (() => {
        // Handle both flat and nested (aggregate_metrics) response structures
        const agg = btResult.aggregate_metrics ?? btResult;
        const mean_r2 = agg.mean_r2 ?? btResult.mean_r2 ?? null;
        const mean_mae = agg.mean_mae ?? btResult.mean_mae ?? null;
        const mean_rmse = agg.mean_rmse ?? btResult.mean_rmse ?? null;
        const dir_acc = agg.mean_directional_accuracy ?? btResult.directional_accuracy ?? null;
        const folds = btResult.folds ?? [];

        return (
          <div className="space-y-5">
          {/* Summary Metrics Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
            <MetricCard icon="📊" label="R² میانگین" value={mean_r2 != null ? mean_r2.toFixed(4) : "—"}
              color={(mean_r2 ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"} />
            <MetricCard icon="📉" label="MAE میانگین" value={mean_mae != null ? mean_mae.toFixed(4) : "—"} />
            <MetricCard icon="📉" label="RMSE میانگین" value={mean_rmse != null ? mean_rmse.toFixed(4) : "—"} />
            <MetricCard icon="🎯" label="دقت جهت" value={dir_acc != null ? (dir_acc * 100).toFixed(1) + "%" : "—"}
              color={(dir_acc ?? 0) >= 0.5 ? "text-accent-emerald" : "text-accent-rose"} />
            <MetricCard icon="📐" label="تعداد Fold" value={`${folds.length} / ${btResult.n_folds ?? "?"}`} />
          </div>

          {/* Per-fold Breakdown Table */}
          {folds.length > 0 && (
            <Card title="📋 جزئیات Fold‌ها" subtitle={`${folds.length} fold • ${btModel} • ${btSymbol}`}>
              <div className="overflow-x-auto">
                <table className="w-full text-right text-[10px]">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 px-2">Fold</th>
                      <th className="pb-2 px-2 text-center font-mono">R²</th>
                      <th className="pb-2 px-2 text-center font-mono">MAE</th>
                      <th className="pb-2 px-2 text-center font-mono">RMSE</th>
                      <th className="pb-2 px-2 text-center">دقت جهت</th>
                      <th className="pb-2 px-2 text-center">آموزش</th>
                      <th className="pb-2 px-2 text-center">تست</th>
                    </tr>
                  </thead>
                  <tbody>
                    {folds.map((fold: MLBacktestFold, i: number) => {
                      const fm = fold.metrics ?? fold;
                      return (
                        <tr key={i} className="border-b border-surface-800/30 hover:bg-white/5">
                          <td className="py-2 px-2 font-bold text-surface-200">Fold {i + 1}</td>
                          <td className={`py-2 px-2 text-center font-mono ${(fm.r2 ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                            {fm.r2?.toFixed(4) ?? "—"}
                          </td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">{fm.mae?.toFixed(4) ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">{fm.rmse?.toFixed(4) ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-300">
                            {fm.directional_accuracy != null ? (fm.directional_accuracy * 100).toFixed(1) + "%" : "—"}
                          </td>
                          <td className="py-2 px-2 text-center font-mono text-surface-400">{fold.train_size ?? "—"}</td>
                          <td className="py-2 px-2 text-center font-mono text-surface-400">{fold.test_size ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Comprehensive Results Dashboard */}
          {btResult.equity_curve && btResult.equity_curve.length >= 2 && (
            <BacktestResultsDashboard
              result={{
                equity_curve: btResult.equity_curve,
                trades: btResult.trades || [],
                initial_capital: btResult.initial_capital ?? 0,
                final_value: btResult.final_value ?? 0,
                total_return_pct: btResult.total_return_pct ?? undefined,
                annualized_return_pct: btResult.annualized_return_pct ?? undefined,
                sharpe_ratio: btResult.sharpe_ratio ?? undefined,
                sortino_ratio: btResult.sortino_ratio ?? undefined,
                calmar_ratio: btResult.calmar_ratio ?? undefined,
                max_drawdown_pct: btResult.max_drawdown_pct ?? undefined,
                win_rate: btResult.win_rate ?? undefined,
                total_trades: btResult.total_trades ?? 0,
                winning_trades: btResult.winning_trades ?? 0,
                losing_trades: btResult.losing_trades ?? 0,
                profit_factor: btResult.profit_factor ?? undefined,
                value_at_risk_95: btResult.value_at_risk_95 ?? undefined,
                cvar_95: btResult.cvar_95 ?? undefined,
                benchmark_return_pct: btResult.benchmark_return_pct ?? undefined,
                alpha: btResult.alpha ?? undefined,
                beta: btResult.beta ?? undefined,
                up_capture: btResult.up_capture ?? undefined,
                down_capture: btResult.down_capture ?? undefined,
              }}
            />
          )}

          {/* Feature Importance */}
          {btResult.feature_importance && Object.keys(btResult.feature_importance).length > 0 && (
            <Card title="🔥 اهمیت ویژگی‌ها" subtitle={`${Object.keys(btResult.feature_importance).length} ویژگی`}>
              <div className="space-y-1.5">
                {Object.entries(btResult.feature_importance)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 15)
                  .map(([feat, val]) => (
                    <div key={feat} className="flex items-center gap-2">
                      <span className="text-[9px] text-surface-400 w-36 truncate text-right font-mono" title={feat}>{feat}</span>
                      <div className="flex-1 h-3 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
                        <div className="h-full bg-accent-amber rounded-full transition-all duration-700"
                          style={{ width: `${(val as number) * 100}%` }} />
                      </div>
                      <span className="text-[9px] font-mono text-surface-500 w-10 text-left">{(val as number * 100).toFixed(0)}%</span>
                    </div>
                  ))}
              </div>
            </Card>
          )}
          </div>
        );
      })()}

      {!btResult && !btLoading && (
        <div className="glass-card p-10 text-center text-surface-500">
          <p className="text-5xl mb-3">🧪</p>
          <p className="font-bold text-surface-400">بک‌تست Walk-Forward</p>
          <p className="text-sm mt-1">نماد، مدل و گروه ویژگی را انتخاب کنید و دکمه اجرا را بزنید</p>
        </div>
      )}
    </div>
  );
}

function MetricCard({ icon, label, value, color }: {
  icon: string; label: string; value: string; color?: string;
}) {
  return (
    <div className="glass-card p-3 text-center hover:scale-[1.02] transition-transform duration-200">
      <p className={`text-lg font-black font-mono ${color || "text-surface-100"}`}>{value}</p>
      <p className="text-[9px] text-surface-500 mt-0.5">{icon} {label}</p>
    </div>
  );
}
