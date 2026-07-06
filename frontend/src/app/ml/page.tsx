"use client";

import { useState } from "react";
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
  symbols: string[];
  status: string;
  metrics: Record<string, number>;
}

interface TrainResponse {
  run_id: string;
  experiment_name: string;
  model_type: string;
  status: string;
  message: string;
}

type MLTab = "models" | "runs" | "train" | "predict";

const TABS: { key: MLTab; label: string; icon: string }[] = [
  { key: "models", label: "مدل‌ها", icon: "🧠" },
  { key: "runs", label: "آموزش‌ها", icon: "⚙️" },
  { key: "train", label: "آموزش جدید", icon: "🚀" },
  { key: "predict", label: "پیش‌بینی", icon: "🔮" },
];

const MODEL_TYPES = ["xgboost", "random_forest", "linear_regression", "lstm", "transformer"];
const POPULAR_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو"];

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

      {runs.map(run => (
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
                {run.symbols?.length > 0 && <span>📊 {run.symbols.join(", ")}</span>}
              </div>
            </div>
          </div>
          {run.metrics && Object.keys(run.metrics).length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-surface-800/50">
              {Object.entries(run.metrics).map(([k, v]) => (
                <span key={k} className="text-xs bg-surface-800/50 px-2 py-1 rounded-lg">
                  <span className="text-surface-500">{k}:</span>{" "}
                  <span className="font-mono text-surface-200">{typeof v === "number" ? v.toFixed(4) : String(v)}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
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

// ------ Prediction Results Table -------------------------------------------------------------------------------------------
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
            <th className="pb-2 px-2">دقت</th>
            <th className="pb-2 px-2">اطمینان</th>
            <th className="pb-2 px-2">F1</th>
            <th className="pb-2 px-2">MSE</th>
            <th className="pb-2 px-2">نمونه</th>
            <th className="pb-2 px-2">زمان(ث)</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={`${r.symbol}-${i}`} className="border-b border-surface-800/30 hover:bg-white/5">
              <td className="py-2 px-2 font-bold text-surface-200">{r.symbol}</td>
              <td className="py-2 px-2 text-surface-400">{r.model_type}</td>
              <td className="py-2 px-2 font-mono text-accent-cyan">{r.prediction.toLocaleString("fa-IR")}</td>
              <td className="py-2 px-2">
                <span className={`font-mono ${r.accuracy >= 0.8 ? "text-accent-emerald" : r.accuracy >= 0.7 ? "text-accent-amber" : "text-accent-rose"}`}>
                  {(r.accuracy * 100).toFixed(1)}%
                </span>
              </td>
              <td className="py-2 px-2 font-mono text-surface-300">{(r.confidence * 100).toFixed(0)}%</td>
              <td className="py-2 px-2 font-mono text-surface-300">{r.f1_score.toFixed(3)}</td>
              <td className="py-2 px-2 font-mono text-surface-400">{r.mse.toFixed(4)}</td>
              <td className="py-2 px-2 font-mono text-surface-400">{r.samples.toLocaleString("fa-IR")}</td>
              <td className="py-2 px-2 font-mono text-surface-400">{r.duration_seconds.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------ Train Tab ---------------------------------------------------------------------------------------------------------
function TrainTab() {
  const queryClient = useQueryClient();
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

  const trainMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      return apiPost<TrainResponse>("/ml/train", data);
    },
    retry: false,
    onSuccess: () => {
      toast.success("آموزش با موفقیت شروع شد");
      queryClient.invalidateQueries({ queryKey: ["ml-runs"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const predictAllMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => {
      return apiPost<{ success: boolean; data: { batch_id: string; results: PredictionResult[] } }>("/ml/predict-all", data);
    },
    retry: false,
    onSuccess: (res) => {
      const count = res?.data?.results?.length ?? 0;
      toast.success(`آزمایش روی ${count} نماد با موفقیت انجام شد`);
      queryClient.invalidateQueries({ queryKey: ["ml-predictions"] });
      setShowResults(true);
    },
    onError: (err: Error) => toast.error(err.message),
  });

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
      <Card title="🚀 آموزش مدل جدید">
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
            <label className="block text-xs text-surface-400 mb-1.5 font-bold">نمادها</label>
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
            <div className="flex gap-1 mt-2">
              {POPULAR_SYMBOLS.filter(s => !form.symbols.includes(s)).map(s => (
                <button key={s} onClick={() => setForm(prev => ({ ...prev, symbols: [...prev.symbols, s] }))}
                  className="text-[10px] px-2 py-0.5 bg-surface-800 text-surface-400 hover:text-surface-200 rounded-full transition-colors">+{s}</button>
              ))}
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
              ) : "شروع آموزش 🚀"}
            </button>

            <button onClick={() => predictAllMutation.mutate({
              model_type: form.model_type,
            })} disabled={predictAllMutation.isPending}
              className="px-6 py-3 bg-accent-amber/20 hover:bg-accent-amber/30 border border-accent-amber/30 text-accent-amber rounded-xl font-bold transition-all flex items-center justify-center gap-2">
              {predictAllMutation.isPending ? (
                <><span className="material-icons animate-spin text-sm">refresh</span> در حال آزمایش...</>
              ) : "🧪 آزمایش همه نمادها"}
            </button>
          </div>
        </div>
      </Card>

      {/* ── Prediction Results ── */}
      {showResults && (
        <Card title="📊 نتایج آزمایش نمادها" subtitle="نتایج پیش‌بینی مدل روی نمادهای مختلف">
          <div className="space-y-4">
            {/* Symbol Search */}
            <div>
              <label className="block text-xs text-surface-400 mb-1.5 font-bold">جستجوی نماد در نتایج</label>
              <SymbolSearchInput value={symbolSearch} onChange={setSymbolSearch} />
            </div>

            {/* Results Table */}
            <PredictionResults symbolSearch={symbolSearch} />
          </div>
        </Card>
      )}
    </div>
  );
}

// ------ Predict Tab -------------------------------------------------------------------------------------------------------
const MOCK_MODELS = [
  { id: "linear_regression", name: "Linear Regression", task: "regression", color: "text-accent-cyan" },
  { id: "random_forest", name: "Random Forest", task: "regression", color: "text-accent-emerald" },
  { id: "xgboost", name: "XGBoost", task: "regression", color: "text-accent-amber" },
  { id: "logistic_regression", name: "Logistic Regression", task: "classification", color: "text-accent-purple" },
];

function PredictTab() {
  const [selectedModel, setSelectedModel] = useState("xgboost");
  const [symbol, setSymbol] = useState("فولاد");

  const { data: prediction, isLoading, error, refetch } = useQuery({
    queryKey: ["ml-predict", selectedModel],
    queryFn: async () => {
      const res = await apiPost<{ success: boolean; data: { prediction: number; confidence: number; metadata?: Record<string, unknown> } }>(
        `/ml/predict/${selectedModel}`, {}
      );
      if (!res?.success) throw new Error("Prediction failed");
      return res.data;
    },
    enabled: false,
    retry: false,
  });

  return (
    <div className="space-y-5">
      <Card title="🔮 پیش‌بینی قیمت">
        <div className="space-y-4">
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
                {POPULAR_SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
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
            <div className="glass-card p-6 text-center">
              <p className="text-xs text-surface-500 mb-1">قیمت پیش‌بینی شده برای {symbol}</p>
              <p className="text-3xl font-black font-mono text-surface-100">
                {typeof prediction.prediction === "number" ? prediction.prediction.toLocaleString("fa-IR") : String(prediction.prediction ?? "—")}
              </p>
              <div className="flex items-center justify-center gap-4 mt-3 text-sm">
                <div>
                  <span className="text-xs text-surface-500">اطمینان: </span>
                  <span className="font-mono font-bold text-surface-200">{((prediction.confidence ?? 0) * 100).toFixed(0)}%</span>
                </div>
                {prediction.metadata?.model != null && (
                  <div>
                    <span className="text-xs text-surface-500">مدل: </span>
                    <span className="font-mono text-surface-400">{String(prediction.metadata.model)}</span>
                  </div>
                )}
              </div>
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
    <AppLayout title="🧠 داشبورد یادگیری ماشین" subtitle="مدیریت مدل‌ها، آموزش و پیش‌بینی">
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
      {tab === "runs" && <RunsTab />}
      {tab === "train" && <TrainTab />}
      {tab === "predict" && <PredictTab />}
    </AppLayout>
  );
}
