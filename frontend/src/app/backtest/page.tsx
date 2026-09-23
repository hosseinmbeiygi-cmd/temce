"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Area, AreaChart, CartesianGrid, ReferenceLine,
} from "recharts";
import {
  FlaskConical, Dices, FlaskRound, Cpu, Rocket, TrendingUp,
} from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiPost, apiGet } from "@/lib/api";
import { toJalali, gregorianToJalali, jalaliToGregorian } from "@/lib/dates";

interface CompareHistoryItem {
  id: string;
  symbol: string;
  total_strategies: number;
  successful: number;
  failed: number;
  best: string | null;
  worst: string | null;
  best_return_pct: number | null;
  worst_return_pct: number | null;
  avg_return_pct: number | null;
  notes: string | null;
  created_at: string | null;
}

interface BacktestResult {
  id: string;
  name: string;
  status: string;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  initial_capital: number;
  final_value: number;
  equity_curve: { timestamp: string; nav: number }[];
  trades: { instrument_id: string; side: string; quantity: number; price: number; pnl: number }[];
  metrics: Record<string, number>;
  completed_at: string;
}

// ── Compare Strategies (shared types & constants — module scope so no
// components are created during render) ──
interface CompareResult {
  strategy: string;
  run_id: string;
  status: string;
  error?: string;
  metrics?: {
    total_return_pct?: number;
    sharpe_ratio?: number;
    win_rate?: number;
    max_drawdown_pct?: number;
    total_trades?: number;
    annualized_return_pct?: number;
  };
}

const ALL_RADAR_COLS = [
  { key: "total_return_pct" as const, label: "بازده", invert: false },
  { key: "annualized_return_pct" as const, label: "بازده سالانه", invert: false },
  { key: "sharpe_ratio" as const, label: "شارپ", invert: false },
  { key: "win_rate" as const, label: "Win Rate", invert: false },
  { key: "max_drawdown_pct" as const, label: "Max DD", invert: true },
];

const RADAR_COLORS_BT = [
  { fill: "rgba(0, 200, 255, 0.15)", stroke: "#00C8FF" },
  { fill: "rgba(0, 230, 118, 0.15)", stroke: "#00E676" },
  { fill: "rgba(255, 214, 0, 0.15)", stroke: "#FFD600" },
  { fill: "rgba(255, 82, 82, 0.15)", stroke: "#FF5252" },
  { fill: "rgba(224, 64, 251, 0.15)", stroke: "#E040FB" },
  { fill: "rgba(0, 230, 200, 0.15)", stroke: "#00E6C8" },
  { fill: "rgba(255, 168, 0, 0.15)", stroke: "#FFA800" },
  { fill: "rgba(100, 255, 218, 0.15)", stroke: "#64FFDA" },
];

function BacktestRadarChart({ results, selectedStrategies, onStrategyClick, enabledCols, hoveredStrategy, onHover, onClearSelection }: {
  results: CompareResult[];
  selectedStrategies: string[];
  onStrategyClick: (strategy: string, e?: React.MouseEvent) => void;
  enabledCols: string[];
  hoveredStrategy: string | null;
  onHover: (strategy: string | null) => void;
  onClearSelection?: () => void;
}) {
  const radarCols = ALL_RADAR_COLS.filter(c => enabledCols.includes(c.key));

  const validResults = results.filter(r => r.status !== "failed").slice(0, 8);
  if (validResults.length < 1) return null;
  if (radarCols.length < 3) {
    return <p className="text-xs text-surface-500 text-center py-4">حداقل ۳ متریک برای نمایش رادار انتخاب کنید</p>;
  }

  // Compute ranges for normalization
  const ranges: Record<string, { min: number; max: number }> = {};
  for (const col of radarCols) {
    const vals = validResults.map(r => r.metrics?.[col.key]).filter(v => v != null) as number[];
    if (vals.length === 0) continue;
    ranges[col.key] = { min: Math.min(...vals), max: Math.max(...vals) };
  }

  const normalize = (key: string, v: number | undefined): number => {
    if (v == null) return 0;
    const r = ranges[key];
    if (!r || r.max === r.min) return 0.5;
    const raw = (v - r.min) / (r.max - r.min);
    const col = radarCols.find(c => c.key === key);
    return col?.invert ? 1 - raw : raw;
  };

  const cx = 160, cy = 160, radius = 120;
  const angleStep = (2 * Math.PI) / radarCols.length;

  const polygons = validResults.map((r, mi) => {
    const pts = radarCols.map((col, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      const val = normalize(col.key, r.metrics?.[col.key]);
      const rad = val * radius;
      return `${cx + rad * Math.cos(angle)},${cy + rad * Math.sin(angle)}`;
    });
    return { points: pts.join(" "), color: RADAR_COLORS_BT[mi % RADAR_COLORS_BT.length], label: r.strategy };
  });

  return (
    <div className="mb-6">
      <p className="text-xs text-surface-400 font-bold mb-3 text-center">📡 نمودار راداری — مقایسه بصری استراتژی‌ها</p>
      <div className="flex flex-col items-center">
        <svg width={320} height={320} viewBox="0 0 320 320" className="max-w-full">
          {Array.from({ length: 5 }, (_, li) => {
            const r = ((li + 1) / 5) * radius;
            const pts = radarCols.map((_, i) => {
              const angle = -Math.PI / 2 + i * angleStep;
              return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
            });
            return <polygon key={li} points={pts.join(" ")} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />;
          })}
          {radarCols.map((col, i) => {
            const angle = -Math.PI / 2 + i * angleStep;
            const x2 = cx + radius * Math.cos(angle);
            const y2 = cy + radius * Math.sin(angle);
            const labelX = cx + (radius + 22) * Math.cos(angle);
            const labelY = cy + (radius + 22) * Math.sin(angle);
            const anchor = angle > -0.1 && angle < Math.PI - 0.1 ? "start" : angle > Math.PI - 0.1 ? "end" : "middle";
            return (
              <g key={col.key}>
                <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
                <text x={labelX} y={labelY} textAnchor={anchor} dominantBaseline="middle"
                  fill="rgba(255,255,255,0.5)" fontSize={9} fontFamily="monospace">
                  {col.label}
                </text>
              </g>
            );
          })}
          {polygons.map((p, i) => {
            const isSelected = selectedStrategies.includes(p.label);
            const isHovered = hoveredStrategy === p.label;
            const hasSelection = selectedStrategies.length > 0;
            const isDimmed = hasSelection && !isSelected;
            const dimOpacity = isDimmed ? 0.15 : isHovered ? 1 : 0.85;
            const strokeColor = isSelected ? '#fff' : isHovered ? p.color.stroke : p.color.stroke;
            const strokeW = isSelected ? 3 : isHovered ? 2.5 : 2;
            return (
              <g key={i}
                onClick={(e) => onStrategyClick(p.label, e)}
                onMouseEnter={() => onHover(p.label)}
                onMouseLeave={() => onHover(null)}
                style={{ cursor: 'pointer' }}
              >
                <polygon
                  points={p.points}
                  fill={isSelected ? p.color.fill.replace('0.15', '0.35') : p.color.fill}
                  stroke={strokeColor}
                  strokeWidth={strokeW}
                  opacity={dimOpacity}
                  className="transition-all duration-200"
                />
                {p.points.split(" ").map((pt, pi) => {
                  const [x, y] = pt.split(",").map(Number);
                  return (
                    <circle key={pi} cx={x} cy={y}
                      r={isSelected ? 5 : isHovered ? 4 : 3}
                      fill={isSelected ? '#fff' : p.color.stroke}
                      opacity={isDimmed ? 0.2 : 0.95}
                      className="transition-all duration-200"
                    />
                  );
                })}
              </g>
            );
          })}
          <circle cx={cx} cy={cy} r={2} fill="rgba(255,255,255,0.2)" />
        </svg>
        <div className="flex flex-wrap gap-3 justify-center mt-2">
          {polygons.map((p, i) => {
            const isSelected = selectedStrategies.includes(p.label);
            return (
              <div key={i}
                onClick={(e) => onStrategyClick(p.label, e)}
                onMouseEnter={() => onHover(p.label)}
                onMouseLeave={() => onHover(null)}
                className={`flex items-center gap-1.5 cursor-pointer transition-all duration-200 px-1.5 py-0.5 rounded ${
                  isSelected ? 'bg-primary-600/20 ring-1 ring-primary-500/50' : 'hover:bg-surface-800/50'
                }`}
              >
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: p.color.stroke }} />
                <span className={`text-[10px] ${isSelected ? 'text-surface-100 font-bold' : 'text-surface-400'}`}>
                  {p.label}
                </span>
              </div>
            );
          })}
          {selectedStrategies.length > 0 && onClearSelection && (
            <button onClick={onClearSelection}
              className="text-[9px] px-2 py-0.5 rounded bg-surface-700 hover:bg-surface-600 text-surface-400 hover:text-surface-200 transition-all">
              ✕ پاک کردن انتخاب
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function BacktestPage() {
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [startDateJalali, setStartDateJalali] = useState(() => {
    const now = new Date();
    now.setFullYear(now.getFullYear() - 1);
    return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
  });
  const [endDateJalali, setEndDateJalali] = useState(() => {
    const now = new Date();
    return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
  });

  const [formData, setFormData] = useState({
    name: "بک‌تست جدید",
    symbols: ["فولاد"],
    strategyType: "moving_average_cross",
    strategyParams: {} as Record<string, unknown>,
    capital: 1000000000,
    commission_pct: 0.35,
    slippage_bps: 10,
    sizing_method: "fixed",
    sizing_value: 1000,
    stop_loss_pct: "" as string | number,
    take_profit_pct: "" as string | number,
    benchmark_symbol: "",
  });

  // Get default params for a strategy from the API data
  const getDefaultParams = (strategyName: string): Record<string, unknown> => {
    const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === strategyName);
    if (!selected?.params || !Array.isArray(selected.params)) return {};
    const defaults: Record<string, unknown> = {};
    for (const p of selected.params as Array<{ name: string; default: unknown }>) {
      if (p.name !== "instrument_id") defaults[p.name] = p.default ?? "";
    }
    return defaults;
  };

  // When strategy changes, set default params from API
  const updateStrategyParams = (strategyName: string) => {
    const defaults = getDefaultParams(strategyName);
    setFormData(prev => ({ ...prev, strategyType: strategyName, strategyParams: defaults }));
  };

  // Reset strategy params to defaults
  const resetStrategyParams = () => {
    const defaults = getDefaultParams(formData.strategyType);
    setFormData(prev => ({ ...prev, strategyParams: defaults }));
  };

  // Load symbols from instruments table
  const { data: symbolsData } = useQuery({
    queryKey: ["backtest-symbols"],
    queryFn: async () => {
      try {
        const res = await apiGet<unknown>("/instruments?page=1&page_size=2000");
        const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: { symbol: string; name: string }[] } }).data : null;
        return d?.items || [];
      } catch { return []; }
    },
  });

  const allSymbols: { symbol: string; name: string }[] = symbolsData || [];
  const filteredSymbols = symbolSearch
    ? allSymbols.filter(s => s.symbol.includes(symbolSearch) || s.name.includes(symbolSearch)).slice(0, 30)
    : allSymbols.slice(0, 30);

  const { data: strategies } = useQuery({
    queryKey: ["backtest-strategies"],
    queryFn: async () => {
      const res = await apiGet<unknown>('/backtests/strategies');
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: Record<string, unknown>[] } }).data : null;
      return d?.items || [];
    },
  });

  // Load initial strategy params once strategies data arrives — useEffect to avoid setState during render
  const [prevStrategies, setPrevStrategies] = useState(strategies);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- sync: adopt server strategies into form once
  useEffect(() => {
    if (strategies && strategies.length > 0 && strategies !== prevStrategies) {
      setPrevStrategies(strategies);
      setFormData(prev => ({ ...prev, strategyParams: getDefaultParams(prev.strategyType) }));
    }
  }, [strategies, prevStrategies]);

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: async () => {
      const res = await apiGet<unknown>('/backtests/runs');
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: Record<string, unknown>[] } }).data : null;
      return d?.items || [];
    },
    refetchInterval: 5000,
  });

  const { data: result, isLoading: loadingResult } = useQuery({
    queryKey: ["backtest-result", selectedResult?.id],
    queryFn: async () => {
      if (!selectedResult?.id) return null;
      const res = await apiGet<unknown>(`/backtests/runs/${selectedResult.id}/result`);
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: Record<string, unknown> }).data : null;
      return d;
    },
    enabled: !!selectedResult,
  });

  const queryClient = useQueryClient();
  const [showAllResults, setShowAllResults] = useState(false);

  const runMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      return await apiPost<Record<string, unknown>>('/backtests/run', data);
    },
    retry: false,
    onSuccess: () => {
      toast.success("بک‌تست با موفقیت شروع شد");
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  interface RunAllResult {
    symbol: string;
    run_id: string;
    status: string;
    metrics?: {
      total_return_pct?: number;
      sharpe_ratio?: number;
      win_rate?: number;
      max_drawdown_pct?: number;
      total_trades?: number;
      annualized_return_pct?: number;
    };
  }

  const [allResults, setAllResults] = useState<RunAllResult[]>([]);

  const runAllMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      return await apiPost<Record<string, unknown>>('/backtests/run-all', data);
    },
    retry: false,
    onSuccess: (res: unknown) => {
      const r = res as { data?: { total_symbols?: number; successful?: number; failed?: number; results?: RunAllResult[] } } | undefined;
      const total = r?.data?.total_symbols ?? 0;
      const ok = r?.data?.successful ?? 0;
      setAllResults(r?.data?.results ?? []);
      toast.success("بک‌تست روی " + ok + " از " + total + " نماد با موفقیت انجام شد");
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
      setShowAllResults(true);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // ── Compare Strategies ──
  const [showCompare, setShowCompare] = useState(false);
  const [compareResults, setCompareResults] = useState<CompareResult[]>([]);
  const [compareBest, setCompareBest] = useState<string | null>(null);
  const [compareWorst, setCompareWorst] = useState<string | null>(null);
  const [compareSymbol, setCompareSymbol] = useState("فولاد");
  const [compareSnapshotSymbol, setCompareSnapshotSymbol] = useState("فولاد");
  const [compareSnapshotDates, setCompareSnapshotDates] = useState({ start: "", end: "" });
  const [compareSortKey, setCompareSortKey] = useState<string | null>("total_return_pct");
  const [compareSortDir, setCompareSortDir] = useState<"asc" | "desc">("desc");
  const [highlightedStrategies, setHighlightedStrategies] = useState<string[]>([]);
  const [hoveredStrategy, setHoveredStrategy] = useState<string | null>(null);
  const defaultMetrics = ALL_RADAR_COLS.map(c => c.key);
  const getSavedMetrics = (): string[] => {
    try {
      const saved = localStorage.getItem("bt-radar-metrics");
      if (saved) {
        const parsed = JSON.parse(saved) as string[];
        // Only keep valid keys
        return parsed.filter(k => (defaultMetrics as string[]).includes(k));
      }
    } catch {}
    return defaultMetrics;
  };
  // SSR-safe initial state: `localStorage` doesn't exist during the server
  // render, so seeding state from getSavedMetrics() would produce different
  // HTML than the client → hydration mismatch. Start from deterministic
  // defaults and adopt the saved selection after mount.
  const [enabledRadarMetrics, setEnabledRadarMetrics] = useState<string[]>(
    defaultMetrics
  );
  useEffect(() => {
    setEnabledRadarMetrics(getSavedMetrics());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Persist metric selection to localStorage
  useEffect(() => {
    try {
      localStorage.setItem("bt-radar-metrics", JSON.stringify(enabledRadarMetrics));
    } catch {}
  }, [enabledRadarMetrics]);

  const toggleCompareSort = (key: string) => {
    setCompareSortDir(prev => compareSortKey === key ? (prev === "asc" ? "desc" : "asc") : "desc");
    setCompareSortKey(key);
  };

  const sortedCompareResults = [...compareResults].sort((a, b) => {
    if (!compareSortKey || compareSortKey === "strategy") {
      const aVal = compareSortKey ? a.strategy : "";
      const bVal = compareSortKey ? b.strategy : "";
      const cmp = aVal.localeCompare(bVal, "fa");
      return compareSortDir === "asc" ? cmp : -cmp;
    }
    const aFailed = a.status === "failed";
    const bFailed = b.status === "failed";
    if (aFailed !== bFailed) return aFailed ? 1 : -1;
    const aVal = a.metrics?.[compareSortKey as keyof typeof a.metrics] ?? -Infinity;
    const bVal = b.metrics?.[compareSortKey as keyof typeof b.metrics] ?? -Infinity;
    return compareSortDir === "asc" ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

  // Track last clicked strategy for Shift+Click range selection
  const lastClickedRef = useRef<string | null>(null);

  // Multi-select click handler: Ctrl/Cmd toggles, Shift ranges, plain replaces
  const handleStrategyClick = useCallback((strategy: string, e?: React.MouseEvent) => {
    if (e?.shiftKey) {
      // Shift+Click: range select from last clicked to this one
      const last = lastClickedRef.current;
      if (!last || last === strategy) {
        // No anchor or same strategy: treat as toggle
        setHighlightedStrategies(prev =>
          prev.includes(strategy)
            ? prev.filter(s => s !== strategy)
            : [...prev, strategy]
        );
      } else {
        // Find positions in the sorted list the user sees
        const names = sortedCompareResults.map(r => r.strategy);
        const fromIdx = names.indexOf(last);
        const toIdx = names.indexOf(strategy);
        if (fromIdx !== -1 && toIdx !== -1) {
          const start = Math.min(fromIdx, toIdx);
          const end = Math.max(fromIdx, toIdx);
          const range = names.slice(start, end + 1);
          setHighlightedStrategies(prev => {
            const merged = new Set([...prev, ...range]);
            return Array.from(merged);
          });
        }
      }
      lastClickedRef.current = strategy;
    } else if (e?.ctrlKey || e?.metaKey) {
      // Toggle: Ctrl/Cmd+Click
      setHighlightedStrategies(prev =>
        prev.includes(strategy)
          ? prev.filter(s => s !== strategy)
          : [...prev, strategy]
      );
      lastClickedRef.current = strategy;
    } else {
      // Plain click: select only this one, or deselect if already the only one
      setHighlightedStrategies(prev => {
        if (prev.length === 1 && prev[0] === strategy) return [];
        return [strategy];
      });
      lastClickedRef.current = strategy;
    }
  }, [sortedCompareResults, setHighlightedStrategies]);

  // Column definitions for the compare table
  const compareColumns = [
    { key: "strategy", label: "استراتژی", numeric: false },
    { key: "total_return_pct", label: "بازده کل", numeric: true },
    { key: "annualized_return_pct", label: "بازده سالانه", numeric: true },
    { key: "sharpe_ratio", label: "شارپ", numeric: true },
    { key: "win_rate", label: "Win Rate", numeric: true },
    { key: "max_drawdown_pct", label: "Max DD", numeric: true },
    { key: "total_trades", label: "معاملات", numeric: true },
  ];

  const getSortArrow = (key: string) => {
    if (compareSortKey !== key) return " ⇅";
    return compareSortDir === "asc" ? " ▲" : " ▼";
  };

  const compareMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      return await apiPost<Record<string, unknown>>('/backtests/compare', data);
    },
    retry: false,
    onSuccess: (res: unknown) => {
      const r = res as { data?: { results?: CompareResult[]; best?: string; worst?: string; successful?: number; total_strategies?: number } } | undefined;
      setCompareResults(r?.data?.results ?? []);
      setCompareBest(r?.data?.best ?? null);
      setCompareWorst(r?.data?.worst ?? null);
      setCompareSnapshotSymbol(compareSymbol);
      setCompareSnapshotDates({
        start: jalaliToGregorian(startDateJalali) || "",
        end: jalaliToGregorian(endDateJalali) || "",
      });
      toast.success("مقایسه " + (r?.data?.successful ?? 0) + " استراتژی انجام شد");
      setShowCompare(true);
      // Invalidate history so it refreshes
      queryClient.invalidateQueries({ queryKey: ["compare-history"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // ── Compare History ──
  const { data: compareHistory } = useQuery({
    queryKey: ["compare-history"],
    queryFn: async () => {
      const res = await apiGet<unknown>('/backtests/compare/history?page_size=20');
      const d = (res && typeof res === "object" && "data" in res) ? (res as { data?: { items?: CompareHistoryItem[] } }).data : null;
      return d?.items || [];
    },
  });

  const saveCompareMutation = useMutation({
    mutationFn: async () => {
      const completed = compareResults.filter(r => r.status !== "failed" && r.metrics?.total_return_pct != null);
      const returns = completed.map(r => r.metrics?.total_return_pct ?? 0);
      const avgReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
      const bestReturn = completed.length > 0 ? Math.max(...returns) : 0;
      const worstReturn = completed.length > 0 ? Math.min(...returns) : 0;
      const startDate = compareSnapshotDates.start || jalaliToGregorian(startDateJalali) || "";
      const endDate = compareSnapshotDates.end || jalaliToGregorian(endDateJalali) || "";
      return await apiPost('/backtests/compare/save', {
        symbol: compareSnapshotSymbol,
        total_strategies: compareResults.length,
        successful: completed.length,
        failed: compareResults.length - completed.length,
        best: compareBest,
        worst: compareWorst,
        best_return_pct: bestReturn,
        worst_return_pct: worstReturn,
        avg_return_pct: avgReturn,
        start_date: startDate,
        end_date: endDate,
        capital: formData.capital,
        results: compareResults,
      });
    },
    onSuccess: () => {
      toast.success("نتیجه مقایسه ذخیره شد");
      queryClient.invalidateQueries({ queryKey: ["compare-history"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const loadCompareHistory = async (item: CompareHistoryItem) => {
    try {
      const res = await apiGet<{ success: boolean; data?: CompareHistoryDetail }>(`/backtests/compare/history/${item.id}`);
      const detail = (res as { data?: CompareHistoryDetail })?.data;
      if (detail?.results) {
        setCompareResults(detail.results as CompareResult[]);
        setCompareBest(detail.best ?? null);
        setCompareWorst(detail.worst ?? null);
        setCompareSnapshotSymbol(detail.symbol);
        setCompareSymbol(detail.symbol);
        setShowCompare(true);
        toast.success("نتایج مقایسه " + detail.symbol + " بارگذاری شد");
      }
    } catch {
      toast.error("خطا در بارگذاری تاریخچه");
    }
  };

  interface CompareHistoryDetail {
    id: string;
    symbol: string;
    results: CompareResult[];
    best: string | null;
    worst: string | null;
  }

  function formatRials(v: number) {
    return new Intl.NumberFormat("fa-IR").format(Math.round(v));
  }

  // ── Generate HTML Report for Compare Results ──
  const generateCompareReportHtml = (): string => {
    const reportSymbol = compareSnapshotSymbol;
    const completed = compareResults.filter(r => r.status !== "failed" && r.metrics?.total_return_pct != null);
    const failed = compareResults.filter(r => r.status === "failed");
    const sortedByReturn = [...completed].sort((a, b) => (b.metrics?.total_return_pct ?? 0) - (a.metrics?.total_return_pct ?? 0));

    const barMax = Math.max(...sortedByReturn.map(r => Math.abs(r.metrics?.total_return_pct ?? 0)), 1);
    const barChartBars = sortedByReturn.map((r, i) => {
      const val = r.metrics?.total_return_pct ?? 0;
      const pct = Math.abs(val) / barMax * 100;
      const color = val >= 0 ? "#22c55e" : "#ef4444";
      const isBest = r.strategy === compareBest;
      const isWorst = r.strategy === compareWorst;
      const bg = isBest ? "rgba(34,197,94,0.08)" : isWorst ? "rgba(239,68,68,0.08)" : i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent";
      return `
        <tr style="background:${bg}">
          <td style="padding:8px 12px;font-weight:${isBest||isWorst?'700':'400'};color:${isBest?'#22c55e':isWorst?'#ef4444':'#e2e8f0'}">
            ${isBest ? '🏆 ' : isWorst ? '🫤 ' : ''}${r.strategy}
          </td>
          <td style="padding:8px 12px;text-align:right;direction:ltr">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:20px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:${color};border-radius:4px;transition:width 0.5s"></div>
              </div>
              <span style="font-family:monospace;color:${color};font-weight:700;min-width:70px;text-align:right">${val >= 0 ? '+' : ''}${val.toFixed(1)}%</span>
            </div>
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:${(r.metrics?.sharpe_ratio ?? 0) >= 1 ? '#22c55e' : (r.metrics?.sharpe_ratio ?? 0) >= 0 ? '#eab308' : '#ef4444'};text-align:center">
            ${(r.metrics?.sharpe_ratio ?? 0).toFixed(2)}
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:${(r.metrics?.win_rate ?? 0) >= 50 ? '#22c55e' : '#ef4444'};text-align:center">
            ${(r.metrics?.win_rate ?? 0).toFixed(1)}%
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:#94a3b8;text-align:center">
            ${(r.metrics?.max_drawdown_pct ?? 0).toFixed(1)}%
          </td>
          <td style="padding:8px 12px;font-family:monospace;color:#94a3b8;text-align:center">
            ${r.metrics?.total_trades ?? 0}
          </td>
        </tr>`;
    }).join("\n");

    const failedRows = failed.map(r => `
      <tr style="opacity:0.5">
        <td style="padding:8px 12px;color:#94a3b8">${r.strategy}</td>
        <td colspan="5" style="padding:8px 12px;color:#ef4444;text-align:center">❌ ${r.error || "ناموفق"}</td>
      </tr>`
    ).join("\n");

    const now = new Date();
    const dateStr = now.toLocaleDateString("fa-IR", { year: "numeric", month: "long", day: "numeric" });

    return `<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>📊 گزارش مقایسه استراتژی‌ها — ${reportSymbol}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700;900&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Vazirmatn',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:40px;line-height:1.6}
  @media print{body{padding:20px;background:#fff;color:#1e293b}.card,.table-wrap{background:#fff!important;border-color:#e2e8f0!important;box-shadow:none!important}th{color:#64748b!important}td{color:#1e293b!important}.badge{background:#f1f5f9!important;color:#1e293b!important}.metric{color:#1e293b!important}h1,h2{color:#0f172a!important}.bar-bg{background:#f1f5f9!important}.header-row{background:#f8fafc!important}.no-print{display:none!important}}
  h1{font-size:24px;font-weight:900;margin-bottom:4px;background:linear-gradient(135deg,#818cf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .subtitle{color:#64748b;font-size:13px;margin-bottom:24px}
  .header-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px 20px;border:1px solid rgba(255,255,255,0.06)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:28px}
  .card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:16px;text-align:center}
  .card .label{font-size:11px;color:#64748b;margin-bottom:4px}
  .card .value{font-size:22px;font-weight:700}
  .card .value.green{color:#22c55e}.card .value.red{color:#ef4444}.card .value.amber{color:#eab308}
  .table-wrap{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;overflow:hidden;margin-bottom:28px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{padding:10px 12px;text-align:center;color:#64748b;font-weight:700;font-size:11px;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,0.06)}
  th:first-child{text-align:right}
  td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.03)}
  .best-badge{display:inline-block;background:rgba(34,197,94,0.15);color:#22c55e;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}
  .worst-badge{display:inline-block;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}
  .footer{text-align:center;color:#475569;font-size:11px;margin-top:32px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.06)}
  @page{size:A4;margin:15mm}
</style>
</head>
<body>
  <div class="header-row">
    <div>
      <h1>📊 گزارش مقایسه استراتژی‌ها</h1>
      <p class="subtitle">نماد: ${compareSymbol} • تاریخ: ${dateStr} • ${completed.length} استراتژی</p>
    </div>
    <div style="display:flex;gap:8px">
      ${compareBest ? "<span class=\"best-badge\">🏆 بهترین: " + compareBest + "</span>" : ''}
      ${compareWorst ? "<span class=\"worst-badge\">🫤 بدترین: " + compareWorst + "</span>" : ''}
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="label">کل استراتژی‌ها</div>
      <div class="value" style="color:#e2e8f0">${compareResults.length}</div>
    </div>
    <div class="card">
      <div class="label">موفق</div>
      <div class="value green">${completed.length}</div>
    </div>
    <div class="card">
      <div class="label">ناموفق</div>
      <div class="value red">${failed.length}</div>
    </div>
    <div class="card">
      <div class="label">بهترین بازده</div>
      <div class="value ${(sortedByReturn[0]?.metrics?.total_return_pct ?? 0) >= 0 ? 'green' : 'red'}">
        ${sortedByReturn.length > 0 ? `${sortedByReturn[0].metrics?.total_return_pct?.toFixed(1)}%` : '—'}
      </div>
    </div>
    <div class="card">
      <div class="label">بدترین بازده</div>
      <div class="value ${(sortedByReturn[sortedByReturn.length-1]?.metrics?.total_return_pct ?? 0) >= 0 ? 'green' : 'red'}">
        ${sortedByReturn.length > 0 ? `${sortedByReturn[sortedByReturn.length-1].metrics?.total_return_pct?.toFixed(1)}%` : '—'}
      </div>
    </div>
    <div class="card">
      <div class="label">میانگین بازده</div>
      <div class="value" style="color:#a78bfa">
        ${completed.length > 0 ? `${(completed.reduce((s,r) => s + (r.metrics?.total_return_pct ?? 0), 0) / completed.length).toFixed(1)}%` : '—'}
      </div>
    </div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="text-align:right">استراتژی</th>
          <th style="text-align:right">بازده کل</th>
          <th>شارپ</th>
          <th>Win Rate</th>
          <th>Max DD</th>
          <th>معاملات</th>
        </tr>
      </thead>
      <tbody>
        ${barChartBars}
        ${failedRows}
      </tbody>
    </table>
  </div>

  <div style="margin-bottom:28px">
    <h2 style="font-size:16px;font-weight:700;margin-bottom:12px;color:#e2e8f0">📈 نمودار مقایسه بازده کل</h2>
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:24px;direction:ltr">
      <svg viewBox="0 0 ${Math.max(700, sortedByReturn.length * 80)} ${sortedByReturn.length * 50 + 60}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
        ${sortedByReturn.map((r, i) => {
          const val = r.metrics?.total_return_pct ?? 0;
          const absVal = Math.abs(val);
          const barMaxVal = Math.max(...sortedByReturn.map(x => Math.abs(x.metrics?.total_return_pct ?? 0)), 1);
          const barPct = (absVal / barMaxVal) * 100;
          const barColor = val >= 0 ? "#22c55e" : "#ef4444";
          const y = i * 50 + 10;
          const barHeight = 30;
          const zeroX = 100;
          const maxBarWidth = 520;
          const barWidth = (barPct / 100) * maxBarWidth;
          const isBest = r.strategy === compareBest;
          const isWorst = r.strategy === compareWorst;
          return `
            <g>
              ${isBest ? `<rect x="${zeroX - maxBarWidth - 10}" y="${y - 4}" width="${maxBarWidth + 140}" height="${barHeight + 8}" rx="6" fill="rgba(34,197,94,0.06)"/>` : ''}
              ${isWorst ? `<rect x="${zeroX - maxBarWidth - 10}" y="${y - 4}" width="${maxBarWidth + 140}" height="${barHeight + 8}" rx="6" fill="rgba(239,68,68,0.06)"/>` : ''}
              <text x="${Math.min(zeroX - 4, zeroX - 8)}" y="${y + barHeight / 2 + 4}" text-anchor="end" fill="#94a3b8" font-size="11" font-family="Vazirmatn">${r.strategy}</text>
              ${val >= 0
                ? `<rect x="${zeroX}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="${barColor}" opacity="0.85"/>
                   <text x="${zeroX + barWidth + 6}" y="${y + barHeight / 2 + 4}" fill="${barColor}" font-size="11" font-family="monospace" font-weight="700">+${val.toFixed(1)}%</text>`
                : `<rect x="${zeroX - barWidth}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="${barColor}" opacity="0.85"/>
                   <text x="${zeroX - barWidth - 6}" y="${y + barHeight / 2 + 4}" text-anchor="end" fill="${barColor}" font-size="11" font-family="monospace" font-weight="700">${val.toFixed(1)}%</text>`
              }
              ${i === 0 ? `<line x1="${zeroX}" y1="0" x2="${zeroX}" y2="${sortedByReturn.length * 50}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
                          <text x="${zeroX}" y="-6" text-anchor="middle" fill="#64748b" font-size="10">صفر</text>` : ''}
            </g>`;
        }).join("\n")}
      </svg>
    </div>
  </div>

  <div class="footer">
    <p>تولید شده توسط سامانه تحلیل بازار • ${dateStr}</p>
    <p style="margin-top:4px;font-size:10px;color:#334155">این گزارش به صورت خودکار از نتایج مقایسه استراتژی‌ها تولید شده است</p>
  </div>

  <div class="no-print" style="text-align:center;margin-top:24px">
    <button onclick="window.print()" style="background:#818cf8;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:Vazirmatn">
      🖨️ ذخیره به صورت PDF (چاپ)
    </button>
  </div>
</body>
</html>`;
  };

  const downloadCompareReport = () => {
    const html = generateCompareReportHtml();
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compare-report-${compareSnapshotSymbol}-${Date.now()}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <AppLayout
      title={
        <span className="flex items-center gap-2.5">
          <span className="grid size-10 place-items-center rounded-xl bg-primary-600/12 text-primary-700 dark:text-brand-300">
            <FlaskConical className="size-5" aria-hidden />
          </span>
          بک‌تست استراتژی
        </span>
      }
      subtitle="تست استراتژی روی تمام نمادها با داده‌های واقعی تاریخی"
    >
      {/* Quick Links to Advanced Tools */}
      <div className="mb-5 flex flex-wrap gap-2">
        <a href="/backtest/engine" className="flex items-center gap-1.5 rounded-xl bg-primary-600/12 px-3 py-1.5 text-xs font-bold text-primary-700 transition-colors hover:bg-primary-600/20 dark:text-brand-300">
          <Cpu className="size-3.5" aria-hidden /> موتور کشف استراتژی
        </a>
        <a href="/backtest/generate" className="flex items-center gap-1.5 rounded-xl bg-soft px-3 py-1.5 text-xs font-bold text-ink-2 transition-colors hover:bg-soft/80 hover:text-ink">
          <Rocket className="size-3.5" aria-hidden /> تولید خودکار استراتژی
        </a>
        <a href="/backtest/walk-forward" className="flex items-center gap-1.5 rounded-xl bg-warn/12 px-3 py-1.5 text-xs font-bold text-warn transition-colors hover:bg-warn/20">
          <TrendingUp className="size-3.5" aria-hidden /> Walk-Forward
        </a>
        <a href="/backtest/monte-carlo" className="flex items-center gap-1.5 rounded-xl bg-up/12 px-3 py-1.5 text-xs font-bold text-up transition-colors hover:bg-up/20">
          <Dices className="size-3.5" aria-hidden /> Monte Carlo
        </a>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 glass-card p-5">
          <h2 className="text-base font-bold text-surface-200 mb-4">تنظیمات بک‌تست</h2>

          <label className="block mb-2 text-sm text-surface-400 font-bold">نام</label>
          <input className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-3 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
            value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />

          <label className="block mb-2 text-sm text-surface-400 font-bold">نمادها ({formData.symbols.length} انتخاب شده)</label>
          <input type="text" value={symbolSearch} onChange={e => setSymbolSearch(e.target.value)}
            placeholder="جستجوی نماد..." className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 mb-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500" />
          <div className="flex flex-wrap gap-1 mb-3 max-h-32 overflow-y-auto">
            {filteredSymbols.map(s => (
              <button key={s.symbol} onClick={() => setFormData(prev => ({...prev, symbols: prev.symbols.includes(s.symbol) ? prev.symbols.filter(x => x !== s.symbol) : [...prev.symbols, s.symbol]}))}
                className={`px-2 py-1 text-xs rounded-full border font-bold ${formData.symbols.includes(s.symbol) ? "bg-primary-600 text-white border-primary-600" : "bg-surface-800 text-surface-300 border-surface-700 hover:border-surface-500"}`}>
                {s.symbol}
              </button>
            ))}
          </div>

          <label className="block mb-2 text-sm text-surface-400 font-bold">استراتژی</label>
          <select className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
            value={formData.strategyType} onChange={e => updateStrategyParams(e.target.value)}>
            {strategies?.map((s: Record<string, unknown>, i: number) => (
              <option key={`${s.name}-${i}`} value={String(s.name ?? "")}>{String(s.name ?? "")}</option>
            ))}
          </select>
          {/* Strategy description tooltip */}
          {(() => {
            const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === formData.strategyType);
            const desc = selected?.description as string | undefined;
            if (!desc) return null;
            return (
              <div className="mb-3 px-3 py-2 bg-surface-800/30 border border-surface-700/30 rounded-lg text-[11px] text-surface-400 leading-relaxed">
                📖 {desc}
              </div>
            );
          })()}

          {/* Strategy Params */}
          {(() => {
            const selected = (strategies ?? []).find((s: Record<string, unknown>) => s.name === formData.strategyType);
            const params = (selected?.params ?? []) as Array<{ name: string; type: string; default: unknown }>;
            const displayParams = params.filter(p => p.name !== "instrument_id");
            if (displayParams.length === 0) return null;
            return (
              <div className="mb-3 p-3 bg-surface-800/40 rounded-lg border border-surface-700/50">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-surface-400 font-bold">⚙️ پارامترهای استراتژی</label>
                  <button onClick={resetStrategyParams}
                    className="text-[10px] px-2 py-0.5 rounded bg-surface-700 hover:bg-surface-600 text-surface-400 hover:text-surface-200 transition-all">
                    ↩ ریست
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {displayParams.map((p, pi) => (
                    <div key={`${p.name}-${pi}`}>
                      <label className="block text-[10px] text-surface-500 mb-0.5">{p.name}</label>
                      <input type={p.type === "number" ? "number" : "text"} step={p.type === "number" ? "any" : undefined}
                        value={String(formData.strategyParams[p.name] ?? p.default ?? "")}
                        onChange={e => setFormData(prev => ({
                          ...prev,
                          strategyParams: { ...prev.strategyParams, [p.name]: p.type === "number" ? Number(e.target.value) : e.target.value },
                        }))}
                        className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500" />
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          <div className="grid grid-cols-2 gap-2 mb-3">
            <div>
              <label className="block mb-1 text-sm text-surface-400 font-bold">از تاریخ (شمسی)</label>
              <input type="text" dir="ltr" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
                value={startDateJalali} onChange={e => setStartDateJalali(e.target.value)} placeholder="1403/01/01" />
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalali(jalaliToGregorian(startDateJalali))}</div>
            </div>
            <div>
              <label className="block mb-1 text-sm text-surface-400 font-bold">تا تاریخ (شمسی)</label>
              <input type="text" dir="ltr" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
                value={endDateJalali} onChange={e => setEndDateJalali(e.target.value)} placeholder="1404/04/01" />
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalali(jalaliToGregorian(endDateJalali))}</div>
            </div>
          </div>

          {/* Quick Time Period Selector */}
          <div className="mb-3">
            <label className="block mb-1 text-xs text-surface-500 font-bold">بازه زمانی سریع</label>
            <div className="flex flex-wrap gap-1">
              {[
                { label: "۱ هفته", days: 7 },
                { label: "۱ ماه", days: 30 },
                { label: "۳ ماه", days: 90 },
                { label: "۶ ماه", days: 180 },
                { label: "۱ سال", days: 365 },
                { label: "۲ سال", days: 730 },
                { label: "۳ سال", days: 1095 },
              ].map(p => (
                <button key={p.days} onClick={() => {
                  const end = new Date();
                  const start = new Date();
                  start.setDate(start.getDate() - p.days);
                  setStartDateJalali(toJalali(start.getFullYear(), start.getMonth() + 1, start.getDate()));
                  setEndDateJalali(toJalali(end.getFullYear(), end.getMonth() + 1, end.getDate()));
                }} className="text-[10px] px-2 py-1 bg-surface-800 border border-surface-700 rounded text-surface-400 hover:text-surface-200 hover:border-surface-500 transition-colors">
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-3">
            <label className="block mb-2 text-sm text-surface-400 font-bold">سرمایه اولیه (ریال)</label>
            <input type="number" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
              value={formData.capital} onChange={e => setFormData({...formData, capital: Number(e.target.value)})} />
          </div>

          {/* Advanced Options */}
          <details className="mb-3 group">
            <summary className="text-xs text-surface-400 font-bold cursor-pointer hover:text-surface-200 transition-colors select-none">
              ⚙️ تنظیمات پیشرفته
            </summary>
            <div className="mt-2 p-3 bg-surface-800/40 rounded-lg border border-surface-700/50 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">کارمزد (%)</label>
                  <input type="number" step="0.01" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.commission_pct} onChange={e => setFormData({...formData, commission_pct: Number(e.target.value)})} />
                </div>
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">Slippage (bps)</label>
                  <input type="number" step="0.5" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.slippage_bps} onChange={e => setFormData({...formData, slippage_bps: Number(e.target.value)})} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">روش محاسبه تعداد</label>
                  <select className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.sizing_method} onChange={e => setFormData({...formData, sizing_method: e.target.value})}>
                    <option value="fixed">ثابت (Fixed)</option>
                    <option value="percent">درصد سرمایه (Percent)</option>
                    <option value="kelly">کلی (Kelly)</option>
                    <option value="risk_based">بر اساس ریسک (Risk)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">مقدار محاسبه</label>
                  <input type="number" step="1" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.sizing_value} onChange={e => setFormData({...formData, sizing_value: Number(e.target.value)})} />
                </div>
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">حد ضرر (٪)</label>
                  <input type="number" step="0.5" placeholder="اختیاری" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.stop_loss_pct} onChange={e => setFormData({...formData, stop_loss_pct: e.target.value})} />
                </div>
                <div>
                  <label className="block text-[10px] text-surface-500 mb-0.5">حد سود (٪)</label>
                  <input type="number" step="0.5" placeholder="اختیاری" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                    value={formData.take_profit_pct} onChange={e => setFormData({...formData, take_profit_pct: e.target.value})} />
                </div>
              </div>
              <div className="mt-3">
                <label className="block text-[10px] text-surface-500 mb-0.5">نماد مرجع (Benchmark)</label>
                <input type="text" placeholder="مثلاً شاخص كل" className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
                  value={formData.benchmark_symbol} onChange={e => setFormData({...formData, benchmark_symbol: e.target.value})} />
              </div>
            </div>
          </details>

          <div className="flex gap-2">
            <button onClick={() => runMutation.mutate({
              name: formData.name,
              symbols: formData.symbols,
              strategy_type: formData.strategyType,
              strategy_params: formData.strategyParams,
              commission_pct: formData.commission_pct / 100,
              slippage_bps: formData.slippage_bps,
              sizing_method: formData.sizing_method,
              sizing_value: formData.sizing_value,
              stop_loss_pct: formData.stop_loss_pct !== "" ? Number(formData.stop_loss_pct) : null,
              take_profit_pct: formData.take_profit_pct !== "" ? Number(formData.take_profit_pct) : null,
              benchmark_symbol: formData.benchmark_symbol || null,
              start_date: jalaliToGregorian(startDateJalali) || undefined,
              end_date: jalaliToGregorian(endDateJalali) || undefined,
              initial_capital: formData.capital,
            })} disabled={runMutation.isPending || formData.symbols.length === 0}
              className="flex-1 bg-primary-600 text-white py-2.5 rounded-lg font-bold hover:bg-primary-500 disabled:opacity-50 transition-colors">
              {runMutation.isPending ? "در حال اجرا..." : "اجرای بک‌تست"}
            </button>

            <button onClick={() => runAllMutation.mutate({
              strategy_type: formData.strategyType,
              strategy_params: formData.strategyParams,
              commission_pct: formData.commission_pct / 100,
              slippage_bps: formData.slippage_bps,
              start_date: jalaliToGregorian(startDateJalali) || undefined,
              end_date: jalaliToGregorian(endDateJalali) || undefined,
              initial_capital: formData.capital,
            })} disabled={runAllMutation.isPending}
              className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2.5 font-bold text-white shadow-[var(--shadow-card)] transition-all hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-40">
              {runAllMutation.isPending ? (
                <><FlaskConical className="size-4 animate-spin" aria-hidden /> در حال اجرا...</>
              ) : (
                <><FlaskConical className="size-4" aria-hidden /> تست همه نمادها</>
              )}
            </button>
          </div>

          {/* ── Compare Section ── */}
          <div className="mt-4 p-3 bg-accent-purple/5 border border-accent-purple/20 rounded-lg">
            <label className="block mb-2 text-sm text-accent-purple font-bold">📊 مقایسه استراتژی‌ها</label>
            <div className="flex gap-2">
              <select
                value={compareSymbol}
                onChange={e => setCompareSymbol(e.target.value)}
                className="flex-1 bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-surface-200 focus:outline-none focus:border-accent-purple"
              >
                {allSymbols.slice(0, 100).map(s => (
                  <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                ))}
              </select>
              <button onClick={() => compareMutation.mutate({
                symbol: compareSymbol,
                start_date: jalaliToGregorian(startDateJalali) || undefined,
                end_date: jalaliToGregorian(endDateJalali) || undefined,
                initial_capital: formData.capital,
              })} disabled={compareMutation.isPending}
                className="px-4 py-2.5 bg-accent-purple/30 hover:bg-accent-purple/40 border border-accent-purple/40 text-accent-purple rounded-lg font-bold transition-all whitespace-nowrap">
                {compareMutation.isPending ? (
                  <><span className="animate-spin text-sm">⚡</span>...</>
                ) : "اجرا"}
              </button>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="glass-card p-5">
            <h2 className="text-base font-bold text-surface-200 mb-4">بک‌تست‌های انجام شده</h2>
            {loadingRuns ? (
              <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}</div>
            ) : runs?.length === 0 ? (
              <p className="text-surface-500 text-sm">هنوز بک‌تستی اجرا نشده</p>
            ) : (
              <div className="space-y-2">
                {runs?.map((run: Record<string, unknown>, i: number) => (
                  <div key={String(run.id ?? i)} className="flex items-center justify-between p-3 bg-surface-800/50 rounded-lg hover:bg-surface-800 transition-colors">
                    <div>
                      <p className="font-bold text-surface-200">{String(run.name ?? "")}</p>
                      <p className="text-xs text-surface-500">{String(run.status ?? "")} — {String(run.progress_pct ?? "")}%</p>
                    </div>
                    <button onClick={() => setSelectedResult({ id: String(run.id) } as BacktestResult)}
                      className="text-primary-400 text-sm font-bold hover:text-primary-300">مشاهده نتیجه</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {loadingResult ? (
            <Skeleton className="h-96 w-full rounded-2xl" />
          ) : result ? (
            <div className="space-y-4">
              {/* Metrics */}
              <div className="glass-card p-5">
                <h2 className="text-base font-bold text-surface-200 mb-4">نتیجه: {String(result.name ?? "")}</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {[
                    { label: "بازده کل", value: `${String(result.total_return_pct ?? "")}%`, color: Number(result.total_return_pct) >= 0 ? "text-accent-emerald" : "text-accent-rose" },
                    { label: "بازده سالانه", value: `${String(result.annualized_return_pct ?? "")}%`, color: "text-surface-200" },
                    { label: "شارپ", value: Number(result.sharpe_ratio || 0).toFixed(2), color: Number(result.sharpe_ratio) >= 1 ? "text-accent-emerald" : "text-accent-amber" },
                    { label: "Max DD", value: `${String(result.max_drawdown_pct ?? "")}%`, color: "text-accent-rose" },
                    { label: "Win Rate", value: `${String(result.win_rate ?? "")}%`, color: Number(result.win_rate) >= 50 ? "text-accent-emerald" : "text-accent-rose" },
                    { label: "معاملات", value: String(result.total_trades ?? ""), color: "text-surface-200" },
                    { label: "سرمایه اولیه", value: `${formatRials(Number(result.initial_capital) || 0)}`, color: "text-surface-200" },
                    { label: "ارزش نهایی", value: `${formatRials(Number(result.final_value) || 0)}`, color: Number(result.final_value) >= Number(result.initial_capital) ? "text-accent-emerald" : "text-accent-rose" },
                    ...((result as Record<string, unknown>).data_quality ? [{
                      label: "کیفیت داده",
                      value: `${((result as Record<string, unknown>).data_quality as Record<string, unknown>)?.quality_score ?? 0}`,
                      color: Number(((result as Record<string, unknown>).data_quality as Record<string, unknown>)?.quality_score ?? 0) >= 0.8 ? "text-accent-emerald" : "text-accent-amber",
                    }] : []),
                    ...((result as Record<string, unknown>).alpha != null ? [{
                      label: "آلفا",
                      value: Number((result as Record<string, unknown>).alpha).toFixed(2),
                      color: Number((result as Record<string, unknown>).alpha) >= 0 ? "text-accent-emerald" : "text-accent-rose",
                    }] : []),
                    ...((result as Record<string, unknown>).beta != null ? [{
                      label: "بتا",
                      value: Number((result as Record<string, unknown>).beta).toFixed(2),
                      color: "text-surface-200",
                    }] : []),
                  ].map(item => (
                    <div key={item.label} className="bg-surface-800/50 rounded-lg p-3 text-center">
                      <p className="text-xs text-surface-500 mb-1">{item.label}</p>
                      <p className={`text-sm font-bold font-mono ${item.color}`}>{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Equity Curve Chart ── */}
              {(() => {
                const raw = result as Record<string, unknown>;
                const equityCurve = raw.equity_curve as Array<{ timestamp: string; nav: number }> | undefined;
                if (!equityCurve || equityCurve.length < 2) return null;
                const equityData = equityCurve.map((ep, i) => ({
                  index: i,
                  nav: ep.nav,
                  date: typeof ep.timestamp === "string" ? ep.timestamp.slice(0, 10) : "",
                }));
                const initCapital = Number(raw.initial_capital) || 1;
                const minNav = Math.min(...equityData.map(d => d.nav));
                const maxNav = Math.max(...equityData.map(d => d.nav));
                const range = maxNav - minNav || 1;
                const yMin = minNav - range * 0.05;
                const yMax = maxNav + range * 0.05;
                const finalReturn = ((equityData[equityData.length - 1]?.nav ?? initCapital) / initCapital - 1) * 100;
                const isPositive = finalReturn >= 0;

                return (
                  <div className="glass-card p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-base font-bold text-surface-200">📈 منحنی سرمایه</h3>
                        <p className="text-[11px] text-surface-500 mt-0.5">
                          {equityData.length} روز معاملاتی
                        </p>
                      </div>
                      <div className={`text-lg font-bold font-mono ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {isPositive ? "+" : ""}{finalReturn.toFixed(1)}%
                      </div>
                    </div>
                    <div className="w-full h-[280px]" dir="ltr">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={equityData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                          <defs>
                            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity={0.3} />
                              <stop offset="95%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                          <XAxis
                            dataKey="index"
                            tick={false}
                            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                          />
                          <YAxis
                            domain={[yMin, yMax]}
                            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                            tickFormatter={(v: number) => Math.round(v).toLocaleString("en-US")}
                            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                            width={80}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "#1e293b",
                              border: "1px solid rgba(255,255,255,0.1)",
                              borderRadius: 8,
                              fontSize: 12,
                              color: "#e2e8f0",
                            }}
                            formatter={(value: unknown) => [formatRials(Number(value) || 0), "ارزش پرتفوی"]}
                            labelFormatter={(i: unknown) => {
                              const idx = Number(i);
                              const d = equityData[idx];
                              return d ? "روز " + (idx + 1) + " — " + d.date : "روز " + (idx + 1);
                            }}
                          />
                          <ReferenceLine
                            y={initCapital}
                            stroke="rgba(255,255,255,0.2)"
                            strokeDasharray="4 4"
                            label={{
                              value: "سرمایه اولیه",
                              fill: "#64748b",
                              fontSize: 10,
                              position: "right",
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="nav"
                            stroke={isPositive ? "#22c55e" : "#ef4444"}
                            strokeWidth={2}
                            fill="url(#equityGradient)"
                            dot={false}
                            activeDot={{ r: 4, strokeWidth: 1, stroke: "#e2e8f0" }}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex justify-between mt-3 text-[10px] text-surface-500 border-t border-surface-800/50 pt-3">
                      <span>🔵 ارزش اولیه: {formatRials(initCapital)}</span>
                      <span>🟣 حداکثر: {formatRials(maxNav)}</span>
                      <span>🔴 حداقل: {formatRials(minNav)}</span>
                      <span>🟢 ارزش نهایی: {formatRials(equityData[equityData.length - 1]?.nav ?? initCapital)}</span>
                    </div>
                  </div>
                );
              })()}

              {/* ── Drawdown Chart ── */}
              {(() => {
                const raw = result as Record<string, unknown>;
                const equityCurve = raw.equity_curve as Array<{ timestamp: string; nav: number }> | undefined;
                if (!equityCurve || equityCurve.length < 2) return null;
                let peak = equityCurve[0].nav;
                const drawdownData = equityCurve.map((ep, i) => {
                  if (ep.nav > peak) peak = ep.nav;
                  const dd = peak > 0 ? ((ep.nav - peak) / peak) * 100 : 0;
                  return {
                    index: i,
                    drawdown: dd,
                    date: typeof ep.timestamp === "string" ? ep.timestamp.slice(0, 10) : "",
                  };
                });
                const maxDD = Math.min(...drawdownData.map(d => d.drawdown));
                return (
                  <div className="glass-card p-5 mt-4">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-base font-bold text-surface-200">📉 افت سرمایه</h3>
                        <p className="text-[11px] text-surface-500 mt-0.5">حداکثر افت: {maxDD.toFixed(2)}%</p>
                      </div>
                    </div>
                    <div className="w-full h-[180px]" dir="ltr">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={drawdownData} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                          <defs>
                            <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                          <XAxis dataKey="index" tick={false} axisLine={{ stroke: "rgba(255,255,255,0.1)" }} />
                          <YAxis
                            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
                            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                            width={50}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "#1e293b",
                              border: "1px solid rgba(255,255,255,0.1)",
                              borderRadius: 8,
                              fontSize: 12,
                              color: "#e2e8f0",
                            }}
                            formatter={(value: unknown) => [`${Number(value).toFixed(2)}%`, "افت سرمایه"]}
                            labelFormatter={(i: unknown) => {
                              const idx = Number(i);
                              const d = drawdownData[idx];
                              return d ? "روز " + (idx + 1) + " — " + d.date : "روز " + (idx + 1);
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="drawdown"
                            stroke="#ef4444"
                            strokeWidth={1.5}
                            fill="url(#ddGradient)"
                            dot={false}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                );
              })()}
            </div>
          ) : null}

          {/* ── Compare Strategies Results ── */}
          {showCompare && compareResults.length > 0 && (
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-surface-200">📊 مقایسه استراتژی‌ها</h2>
                <div className="flex items-center gap-3">
                  {compareBest && compareWorst && (
                    <div className="flex gap-3 text-[10px]">
                      <span className="px-2 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald font-bold">
                        🏆 بهترین: {compareBest}
                      </span>
                      <span className="px-2 py-0.5 rounded-full bg-accent-rose/15 text-accent-rose font-bold">
                        🫤 بدترین: {compareWorst}
                      </span>
                    </div>
                  )}
                  <button onClick={downloadCompareReport}
                    className="px-3 py-1.5 text-[11px] bg-accent-purple/20 hover:bg-accent-purple/30 border border-accent-purple/30 text-accent-purple rounded-lg font-bold transition-all whitespace-nowrap flex items-center gap-1">
                    📄 گزارش
                  </button>
                  <button onClick={() => saveCompareMutation.mutate()} disabled={saveCompareMutation.isPending}
                    className="px-3 py-1.5 text-[11px] bg-accent-emerald/20 hover:bg-accent-emerald/30 border border-accent-emerald/30 text-accent-emerald rounded-lg font-bold transition-all whitespace-nowrap flex items-center gap-1">
                    {saveCompareMutation.isPending ? "..." : "💾 ذخیره"}
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-surface-200">{compareResults.length}</p>
                  <p className="text-xs text-surface-500">کل استراتژی‌ها</p>
                </div>
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-accent-emerald">
                    {compareResults.filter(r => r.status !== "failed").length}
                  </p>
                  <p className="text-xs text-surface-500">موفق</p>
                </div>
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-accent-rose">
                    {compareResults.filter(r => r.status === "failed").length}
                  </p>
                  <p className="text-xs text-surface-500">ناموفق</p>
                </div>
              </div>
              {/* Metric checkboxes */}
              <div className="mb-4">
                <p className="text-[10px] text-surface-500 font-bold mb-2">📐 انتخاب متریک‌های رادار</p>
                <div className="flex flex-wrap gap-2">
                  {ALL_RADAR_COLS.map(col => {
                    const enabled = enabledRadarMetrics.includes(col.key);
                    return (
                      <label key={col.key}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg cursor-pointer transition-all text-[10px] font-bold ${
                          enabled
                            ? 'bg-primary-600/20 text-primary-300 ring-1 ring-primary-500/40'
                            : 'bg-surface-800/50 text-surface-500 hover:bg-surface-700/50'
                        }`}>
                        <input type="checkbox" checked={enabled}
                          onChange={() => {
                            setEnabledRadarMetrics(prev =>
                              enabled
                                ? prev.filter(k => k !== col.key)
                                : [...prev, col.key]
                            );
                          }}
                          className="sr-only" />
                        <div className={`w-2.5 h-2.5 rounded border flex items-center justify-center transition-all ${
                          enabled ? 'bg-primary-500 border-primary-500' : 'border-surface-600 bg-transparent'
                        }`}>
                          {enabled && <span className="text-[7px] text-white leading-none">✓</span>}
                        </div>
                        {col.label}
                      </label>
                    );
                  })}
                </div>
              </div>
              {/* Radar chart */}
              <BacktestRadarChart
                results={compareResults}
                selectedStrategies={highlightedStrategies}
                onStrategyClick={handleStrategyClick}
                enabledCols={enabledRadarMetrics}
                hoveredStrategy={hoveredStrategy}
                onHover={setHoveredStrategy}
                onClearSelection={() => {
                  setHighlightedStrategies([]);
                  lastClickedRef.current = null;
                }}
              />

              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      {compareColumns.map(col => (
                        <th key={col.key}
                          onClick={() => toggleCompareSort(col.key)}
                          className={`pb-2 px-2 select-none cursor-pointer hover:text-surface-200 transition-colors ${compareSortKey === col.key ? "text-primary-400" : ""}`}>
                          {col.label}<span className="text-[10px] opacity-50">{getSortArrow(col.key)}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedCompareResults.map(r => {
                      const m = r.metrics;          const isBest = r.strategy === compareBest;
          const isWorst = r.strategy === compareWorst;
          const failed = r.status === "failed";                      const isRowSelected = highlightedStrategies.includes(r.strategy);
                      let rowBg = "";
                      if (isRowSelected) rowBg = "bg-primary-600/10";
                      else if (isBest) rowBg = "bg-accent-emerald/5";
                      else if (isWorst) rowBg = "bg-accent-rose/5";
                      return (
                        <tr key={r.strategy}
                          onClick={(e) => handleStrategyClick(r.strategy, e)}
                          className={`border-b transition-colors ${
                            isRowSelected ? 'border-primary-500/60' : 'border-surface-800/30 hover:bg-white/5'
                          } ${rowBg} ${failed ? "opacity-50" : ""} cursor-pointer`}>
                          <td className="py-2 px-2 font-bold relative group">
                            <span className={`${isBest ? "text-accent-emerald" : isWorst ? "text-accent-rose" : "text-surface-200"} cursor-help`}>
                              {isBest && "🏆 "}{isWorst && "🫤 "}{r.strategy}
                            </span>
                            {(() => {
                              const desc = (strategies ?? []).find((s: Record<string, unknown>) => s.name === r.strategy)?.description as string | undefined;
                              if (!desc) return null;
                              return (
                                <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-10">
                                  <div className="bg-surface-700 text-surface-300 text-[10px] rounded-lg px-3 py-2 shadow-lg max-w-[260px] leading-relaxed whitespace-normal">
                                    📖 {desc}
                                  </div>
                                </div>
                              );
                            })()}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.total_return_pct != null ? (m.total_return_pct >= 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.total_return_pct != null ? `${m.total_return_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.annualized_return_pct != null ? `${m.annualized_return_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.sharpe_ratio != null ? (m.sharpe_ratio >= 1 ? "text-accent-emerald" : m.sharpe_ratio >= 0 ? "text-accent-amber" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : "—"}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.win_rate != null ? (m.win_rate >= 50 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.win_rate != null ? `${m.win_rate.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.total_trades != null ? m.total_trades : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Compare History ── */}
          {compareHistory && compareHistory.length > 0 && (
            <div className="glass-card p-5">
              <h2 className="text-base font-bold text-surface-200 mb-4">📚 تاریخچه مقایسه‌ها</h2>
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {(compareHistory as CompareHistoryItem[]).slice(0, 10).map(item => {
                  const hasReturn = item.avg_return_pct != null;
                  return (
                    <button key={item.id} onClick={() => loadCompareHistory(item)}
                      className="w-full flex items-center justify-between p-3 bg-surface-800/40 hover:bg-surface-800 rounded-lg transition-colors text-right">
                      <div className="flex items-center gap-3">
                        <span className="text-surface-500 text-lg">📊</span>
                        <div>
                          <p className="text-sm font-bold text-surface-200">{item.symbol}</p>
                          <p className="text-[10px] text-surface-500">
                            {item.total_strategies} استراتژی • {item.successful} موفق • {item.failed} ناموفق
                            {item.created_at && ` • ${new Date(item.created_at).toLocaleDateString("fa-IR")}`}
                          </p>
                        </div>
                      </div>
                      <div className="text-left">
                        {hasReturn ? (
                          <>
                            <p className={`text-xs font-bold font-mono ${item.avg_return_pct! >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                              {item.avg_return_pct!.toFixed(1)}%
                            </p>
                            <p className="text-[9px] text-surface-600">میانگین</p>
                          </>
                        ) : (
                          <span className="text-xs text-surface-600">—</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Run All Results ── */}
          {showAllResults && (
            <div className="glass-card p-5">
              <h2 className="text-base font-bold text-surface-200 mb-4">📊 نتیجه تست همه نمادها</h2>

              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-3 mb-4">
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-surface-200">{allResults.length}</p>
                  <p className="text-xs text-surface-500">کل</p>
                </div>
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-accent-emerald">
                    {allResults.filter(r => r.status !== "failed").length}
                  </p>
                  <p className="text-xs text-surface-500">موفق</p>
                </div>
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-accent-rose">
                    {allResults.filter(r => r.status === "failed").length}
                  </p>
                  <p className="text-xs text-surface-500">ناموفق</p>
                </div>
                <div className="bg-surface-800/50 rounded-lg p-3 text-center">
                  <p className="text-lg font-bold text-accent-cyan">
                    {allResults.reduce((sum, r) => sum + (r.metrics?.total_trades ?? 0), 0)}
                  </p>
                  <p className="text-xs text-surface-500">کل معاملات</p>
                </div>
              </div>

              {/* Per-Symbol Results Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700">
                      <th className="pb-2 px-2">نماد</th>
                      <th className="pb-2 px-2">وضعیت</th>
                      <th className="pb-2 px-2">بازده کل</th>
                      <th className="pb-2 px-2">بازده سالانه</th>
                      <th className="pb-2 px-2">شارپ</th>
                      <th className="pb-2 px-2">Win Rate</th>
                      <th className="pb-2 px-2">Max DD</th>
                      <th className="pb-2 px-2">معاملات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allResults.map(r => {
                      const m = r.metrics;
                      const failed = r.status === "failed";
                      return (
                        <tr key={r.symbol} className={`border-b border-surface-800/30 hover:bg-white/5 ${failed ? "opacity-50" : ""}`}>
                          <td className="py-2 px-2 font-bold text-surface-200">{r.symbol}</td>
                          <td className="py-2 px-2">
                            {failed ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-rose/15 text-accent-rose">خطا</span>
                            ) : (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald">✓</span>
                            )}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.total_return_pct != null ? (m.total_return_pct >= 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.total_return_pct != null ? `${m.total_return_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.annualized_return_pct != null ? `${m.annualized_return_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.sharpe_ratio != null ? (m.sharpe_ratio >= 1 ? "text-accent-emerald" : m.sharpe_ratio >= 0 ? "text-accent-amber" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : "—"}
                          </td>
                          <td className={`py-2 px-2 font-mono ${!failed && m?.win_rate != null ? (m.win_rate >= 50 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500"}`}>
                            {!failed && m?.win_rate != null ? `${m.win_rate.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">
                            {!failed && m?.total_trades != null ? m.total_trades : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
