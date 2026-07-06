"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiPost, apiGet, extractArray } from "@/lib/api";
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

  // Load initial strategy params once strategies data arrives
  useEffect(() => {
    if (strategies && strategies.length > 0) {
      setFormData(prev => ({ ...prev, strategyParams: getDefaultParams(prev.strategyType) }));
    }
  }, [strategies]);

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
      toast.success(`بک‌تست روی ${ok} از ${total} نماد با موفقیت انجام شد`);
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
      setShowAllResults(true);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // ── Compare Strategies ──
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

  const [showCompare, setShowCompare] = useState(false);
  const [compareResults, setCompareResults] = useState<CompareResult[]>([]);
  const [compareBest, setCompareBest] = useState<string | null>(null);
  const [compareWorst, setCompareWorst] = useState<string | null>(null);
  const [compareSymbol, setCompareSymbol] = useState("فولاد");
  const [compareSnapshotSymbol, setCompareSnapshotSymbol] = useState("فولاد");
  const [compareSnapshotDates, setCompareSnapshotDates] = useState({ start: "", end: "" });
  const [compareSortKey, setCompareSortKey] = useState<string | null>("total_return_pct");
  const [compareSortDir, setCompareSortDir] = useState<"asc" | "desc">("desc");

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
    if (aFailed !== bFailed) return aFailed ? 1 : -1; // failed last
    const aVal = a.metrics?.[compareSortKey as keyof typeof a.metrics] ?? -Infinity;
    const bVal = b.metrics?.[compareSortKey as keyof typeof b.metrics] ?? -Infinity;
    return compareSortDir === "asc" ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

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
        start: jalaliToGregorian(startDateJalali),
        end: jalaliToGregorian(endDateJalali),
      });
      toast.success(`مقایسه ${r?.data?.successful ?? 0} استراتژی انجام شد`);
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
      const startDate = compareSnapshotDates.start || jalaliToGregorian(startDateJalali);
      const endDate = compareSnapshotDates.end || jalaliToGregorian(endDateJalali);
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
        toast.success(`نتایج مقایسه ${detail.symbol} بارگذاری شد`);
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
      ${compareBest ? `<span class="best-badge">🏆 بهترین: ${compareBest}</span>` : ''}
      ${compareWorst ? `<span class="worst-badge">🫤 بدترین: ${compareWorst}</span>` : ''}
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
          const xPos = val >= 0 ? zeroX : zeroX - barWidth;
          const labelX = val >= 0 ? zeroX - 8 : zeroX + maxBarWidth + 8;
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
    <AppLayout title="بک‌تست استراتژی" subtitle="تست استراتژی روی داده‌های واقعی تاریخی">
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
                  {displayParams.map(p => (
                    <div key={p.name}>
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
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalali(jalaliToGregorian(startDateJalali) || "2024-01-01")}</div>
            </div>
            <div>
              <label className="block mb-1 text-sm text-surface-400 font-bold">تا تاریخ (شمسی)</label>
              <input type="text" dir="ltr" className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-200 focus:outline-none focus:border-primary-500"
                value={endDateJalali} onChange={e => setEndDateJalali(e.target.value)} placeholder="1404/04/01" />
              <div className="text-[10px] text-surface-600 mt-1">{gregorianToJalali(jalaliToGregorian(endDateJalali) || "2025-01-01")}</div>
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
              start_date: jalaliToGregorian(startDateJalali),
              end_date: jalaliToGregorian(endDateJalali),
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
              start_date: jalaliToGregorian(startDateJalali),
              end_date: jalaliToGregorian(endDateJalali),
              initial_capital: formData.capital,
            })} disabled={runAllMutation.isPending}
              className="px-4 py-2.5 bg-accent-amber/20 hover:bg-accent-amber/30 border border-accent-amber/30 text-accent-amber rounded-lg font-bold transition-all flex items-center gap-1.5">
              {runAllMutation.isPending ? (
                <><span className="animate-spin text-sm">⚡</span> در حال اجرا...</>
              ) : "🧪 تست همه نمادها"}
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
                start_date: jalaliToGregorian(startDateJalali),
                end_date: jalaliToGregorian(endDateJalali),
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
                ].map(item => (
                  <div key={item.label} className="bg-surface-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-surface-500 mb-1">{item.label}</p>
                    <p className={`text-sm font-bold font-mono ${item.color}`}>{item.value}</p>
                  </div>
                ))}
              </div>
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
                      const m = r.metrics;
                      const isBest = r.strategy === compareBest;
                      const isWorst = r.strategy === compareWorst;
                      const failed = r.status === "failed";
                      return (
                        <tr key={r.strategy}
                          className={`border-b border-surface-800/30 hover:bg-white/5 transition-colors ${isBest ? "bg-accent-emerald/5" : isWorst ? "bg-accent-rose/5" : ""} ${failed ? "opacity-50" : ""}`}>
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
