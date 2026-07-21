"use client";

import { useState, useEffect, useCallback } from "react";

interface StrategyResult {
  id: string;
  symbol: string;
  entry_indicator: string;
  entry_condition: string;
  exit_indicator: string;
  exit_condition: string;
  filter1_indicator: string | null;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  score: number;
}

interface ComposeProgress {
  running: boolean;
  phase: string;
  total: number;
  tested: number;
  passed: number;
}

export default function ComposePage() {
  const [symbols, setSymbols] = useState<string[]>(["فولاد"]);
  const [symbolInput, setSymbolInput] = useState("فولاد");
  const [batchSize, setBatchSize] = useState(100000);
  const [maxBatches, setMaxBatches] = useState(5);
  const [progress, setProgress] = useState<ComposeProgress | null>(null);
  const [results, setResults] = useState<StrategyResult[]>([]);
  const [indicators, setIndicators] = useState<any[]>([]);
  const [filterEntry, setFilterEntry] = useState("");
  const [filterExit, setFilterExit] = useState("");
  const [loading, setLoading] = useState(false);

  // Load indicators on mount
  useEffect(() => {
    fetch("/api/compose/indicators")
      .then(r => r.json())
      .then(d => setIndicators(d.data || []))
      .catch(() => {});
  }, []);

  // Poll progress
  useEffect(() => {
    const interval = setInterval(() => {
      fetch("/api/compose/status")
        .then(r => r.json())
        .then(d => {
          setProgress(d.data);
          if (!d.data?.running && results.length === 0) {
            fetch("/api/compose/results?limit=100")
              .then(r => r.json())
              .then(d => setResults(d.data?.results || []));
          }
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [results.length]);

  const startGeneration = useCallback(async () => {
    setLoading(true);
    try {
      await fetch("/api/compose/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols, batch_size: batchSize, max_batches: maxBatches }),
      });
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [symbols, batchSize, maxBatches]);

  const stopGeneration = useCallback(async () => {
    await fetch("/api/compose/stop", { method: "POST" });
  }, []);

  const addSymbol = () => {
    if (symbolInput && !symbols.includes(symbolInput)) {
      setSymbols([...symbols, symbolInput]);
    }
  };

  const removeSymbol = (s: string) => {
    setSymbols(symbols.filter(x => x !== s));
  };

  const filteredResults = results.filter(r => {
    if (filterEntry && r.entry_indicator !== filterEntry) return false;
    if (filterExit && r.exit_indicator !== filterExit) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-surface-950 p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold text-surface-100 mb-6">🔬 ترکیب استراتژی — ۳۰ اندیکاتور</h1>

        {/* ── Settings Panel ── */}
        <div className="glass-card p-5 mb-6">
          <h2 className="text-base font-bold text-surface-200 mb-4">تنظیمات</h2>

          {/* Symbols */}
          <div className="mb-4">
            <label className="block text-xs text-surface-500 mb-1">نمادها</label>
            <div className="flex gap-2 mb-2">
              <input
                value={symbolInput}
                onChange={e => setSymbolInput(e.target.value)}
                className="flex-1 bg-surface-900 border border-surface-700 rounded px-3 py-2 text-sm text-surface-200"
                placeholder="نماد را تایپ کنید"
              />
              <button onClick={addSymbol} className="px-4 py-2 bg-primary-600 text-white rounded text-sm">افزودن</button>
            </div>
            <div className="flex flex-wrap gap-2">
              {symbols.map(s => (
                <span key={s} className="bg-primary-600/20 text-primary-300 px-3 py-1 rounded-full text-xs flex items-center gap-1">
                  {s}
                  <button onClick={() => removeSymbol(s)} className="text-primary-400 hover:text-primary-200">×</button>
                </span>
              ))}
            </div>
          </div>

          {/* Batch Settings */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs text-surface-500 mb-1">تعداد در هر فاز</label>
              <input type="number" value={batchSize} onChange={e => setBatchSize(Number(e.target.value))}
                className="w-full bg-surface-900 border border-surface-700 rounded px-3 py-2 text-sm text-surface-200" />
            </div>
            <div>
              <label className="block text-xs text-surface-500 mb-1">حداکثر فاز</label>
              <input type="number" value={maxBatches} onChange={e => setMaxBatches(Number(e.target.value))}
                className="w-full bg-surface-900 border border-surface-700 rounded px-3 py-2 text-sm text-surface-200" />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button onClick={startGeneration} disabled={loading || progress?.running}
              className="flex-1 bg-primary-600 text-white py-3 rounded-lg font-bold hover:bg-primary-500 disabled:opacity-50 transition-colors">
              {progress?.running ? "در حال اجرا..." : "شروع تولید"}
            </button>
            {progress?.running && (
              <button onClick={stopGeneration}
                className="px-6 py-3 bg-accent-rose/20 text-accent-rose border border-accent-rose/30 rounded-lg font-bold">
                توقف
              </button>
            )}
          </div>
        </div>

        {/* ── Progress ── */}
        {progress && (
          <div className="glass-card p-5 mb-6">
            <h2 className="text-base font-bold text-surface-200 mb-3">پیشرفت</h2>
            <div className="grid grid-cols-4 gap-4 mb-3">
              <div className="text-center">
                <p className="text-2xl font-bold text-primary-400">{progress.total || 0}</p>
                <p className="text-xs text-surface-500">کل</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-accent-amber">{progress.tested || 0}</p>
                <p className="text-xs text-surface-500">تست شده</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-accent-emerald">{progress.passed || 0}</p>
                <p className="text-xs text-surface-500">فیلتر شده</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-surface-200">{results.length}</p>
                <p className="text-xs text-surface-500">ذخیره شده</p>
              </div>
            </div>
            {progress.total > 0 && (
              <div className="w-full bg-surface-800 rounded-full h-2">
                <div className="bg-primary-500 h-2 rounded-full transition-all"
                  style={{ width: `${((progress.tested || 0) / progress.total) * 100}%` }} />
              </div>
            )}
          </div>
        )}

        {/* ── Indicators List ── */}
        <div className="glass-card p-5 mb-6">
          <h2 className="text-base font-bold text-surface-200 mb-3">اندیکاتورها ({indicators.length})</h2>
          <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-2">
            {indicators.map((ind: any) => (
              <div key={ind.id} className="bg-surface-800/50 rounded p-2 text-center">
                <p className="text-xs font-bold text-surface-200">{ind.name_fa}</p>
                <p className="text-[10px] text-surface-500">{ind.group}</p>
                <p className="text-[10px] text-primary-400">{ind.conditions?.length || 0} شرط</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Results ── */}
        {results.length > 0 && (
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-surface-200">نتایج ({filteredResults.length})</h2>
              <div className="flex gap-2">
                <select value={filterEntry} onChange={e => setFilterEntry(e.target.value)}
                  className="bg-surface-900 border border-surface-700 rounded px-2 py-1 text-xs text-surface-200">
                  <option value="">همه Entry</option>
                  {[...new Set(results.map(r => r.entry_indicator))].map(ind => (
                    <option key={ind} value={ind}>{ind}</option>
                  ))}
                </select>
                <select value={filterExit} onChange={e => setFilterExit(e.target.value)}
                  className="bg-surface-900 border border-surface-700 rounded px-2 py-1 text-xs text-surface-200">
                  <option value="">همه Exit</option>
                  {[...new Set(results.map(r => r.exit_indicator))].map(ind => (
                    <option key={ind} value={ind}>{ind}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-700">
                    <th className="py-2 px-2 text-right text-surface-400">#</th>
                    <th className="py-2 px-2 text-right text-surface-400">نماد</th>
                    <th className="py-2 px-2 text-right text-surface-400">Entry</th>
                    <th className="py-2 px-2 text-right text-surface-400">Exit</th>
                    <th className="py-2 px-2 text-right text-surface-400">Filter</th>
                    <th className="py-2 px-2 text-right text-surface-400">بازده</th>
                    <th className="py-2 px-2 text-right text-surface-400">شارپ</th>
                    <th className="py-2 px-2 text-right text-surface-400">DD</th>
                    <th className="py-2 px-2 text-right text-surface-400">Win%</th>
                    <th className="py-2 px-2 text-right text-surface-400">PF</th>
                    <th className="py-2 px-2 text-right text-surface-400">معاملات</th>
                    <th className="py-2 px-2 text-right text-surface-400">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((r, i) => (
                    <tr key={r.id || i} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                      <td className="py-2 px-2 text-surface-400">{i + 1}</td>
                      <td className="py-2 px-2 text-surface-200">{r.symbol}</td>
                      <td className="py-2 px-2 text-primary-400">{r.entry_indicator}</td>
                      <td className="py-2 px-2 text-accent-amber">{r.exit_indicator}</td>
                      <td className="py-2 px-2 text-surface-500">{r.filter1_indicator || "—"}</td>
                      <td className={`py-2 px-2 font-mono ${r.total_return_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {r.total_return_pct?.toFixed(1)}%
                      </td>
                      <td className={`py-2 px-2 font-mono ${r.sharpe_ratio >= 1 ? "text-accent-emerald" : r.sharpe_ratio >= 0 ? "text-accent-amber" : "text-accent-rose"}`}>
                        {r.sharpe_ratio?.toFixed(2)}
                      </td>
                      <td className="py-2 px-2 font-mono text-accent-rose">{r.max_drawdown_pct?.toFixed(1)}%</td>
                      <td className="py-2 px-2 font-mono">{r.win_rate?.toFixed(0)}%</td>
                      <td className="py-2 px-2 font-mono">{r.profit_factor?.toFixed(2)}</td>
                      <td className="py-2 px-2 font-mono">{r.total_trades}</td>
                      <td className="py-2 px-2 font-mono text-primary-400 font-bold">{r.score?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Export */}
            <div className="mt-4 flex justify-end">
              <a href="/api/compose/export" className="px-4 py-2 bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30 rounded text-xs font-bold">
                خروجی CSV
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
