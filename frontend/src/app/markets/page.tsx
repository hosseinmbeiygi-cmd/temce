"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { apiGet, extractArray } from "@/lib/api";

interface Snapshot {
  symbol: string;
  name: string;
  price_last: number;
  price_last_change_pct: number;
  trade_value: number;
  trade_volume: number;
  sector: string;
  market: string;
}

interface MarketSummary {
  total_instruments: number;
  gainers: number;
  losers: number;
  total_value: number;
  total_volume: number;
  avg_change_pct: number;
}

export default function MarketsPage() {
  const [tab, setTab] = useState<"overview" | "gainers" | "losers" | "active" | "sectors">("overview");

  const { data: overview } = useQuery({
    queryKey: ["market-overview"],
    queryFn: async () => apiGet<unknown>("/market/overview"),
    refetchInterval: 30000,
  });

  const summary: MarketSummary | null =
    (overview && typeof overview === "object" && "data" in overview)
      ? (overview as { data?: MarketSummary }).data ?? null : null;

  const { data: heatmapData, isLoading: loadingHeatmap } = useQuery({
    queryKey: ["market-heatmap"],
    queryFn: async () => apiGet<unknown>("/market/heatmap"),
    refetchInterval: 30000,
  });

  const snapshots: Snapshot[] = (heatmapData && typeof heatmapData === "object" && "data" in heatmapData)
    ? extractArray((heatmapData as { data?: unknown }).data) as Snapshot[]
    : [];

  // ── Batch sparkline data for top symbols ──
  const topSymbolsForSpark = useMemo(() => {
    const top = [...snapshots]
      .sort((a, b) => (Math.abs(b.price_last_change_pct || 0)) - (Math.abs(a.price_last_change_pct || 0)))
      .slice(0, 20)
      .map(s => s.symbol);
    return top.join(",");
  }, [snapshots]);

  const { data: sparkMap } = useQuery({
    queryKey: ["markets-spark", topSymbolsForSpark],
    queryFn: async () => {
      if (!topSymbolsForSpark) return {};
      try {
        const res = await apiGet<{ success: boolean; data: Record<string, number[]> }>(
          `/market/sparklines?symbols=${encodeURIComponent(topSymbolsForSpark)}&limit=30`
        );
        return res?.data ?? {};
      } catch { return {}; }
    },
    enabled: !!topSymbolsForSpark,
    staleTime: 120_000,
  });

  // Sparkline helper
  function SparklineForSymbol(symbol: string): React.ReactNode {
    const data = sparkMap?.[symbol];
    if (data && data.length > 1) return <MiniSparkline data={data} width={64} height={22} />;
    return null;
  }

  // Compute sectors
  const sectorMap = new Map<string, { count: number; totalChange: number; totalValue: number }>();
  for (const s of snapshots) {
    const sec = s.sector || "نامشخص";
    const existing = sectorMap.get(sec) || { count: 0, totalChange: 0, totalValue: 0 };
    existing.count++;
    existing.totalChange += s.price_last_change_pct || 0;
    existing.totalValue += s.trade_value || 0;
    sectorMap.set(sec, existing);
  }
  const sectors = Array.from(sectorMap.entries()).map(([name, data]) => ({
    name,
    count: data.count,
    avgChange: data.totalChange / data.count,
    totalValue: data.totalValue,
  })).sort((a, b) => b.totalValue - a.totalValue);

  // Sort snapshots
  const gainers = [...snapshots].filter(s => (s.price_last_change_pct || 0) > 0).sort((a, b) => (b.price_last_change_pct || 0) - (a.price_last_change_pct || 0));
  const losers = [...snapshots].filter(s => (s.price_last_change_pct || 0) < 0).sort((a, b) => (a.price_last_change_pct || 0) - (b.price_last_change_pct || 0));
  const mostActive = [...snapshots].sort((a, b) => (b.trade_value || 0) - (a.trade_value || 0));

  const displayList = tab === "gainers" ? gainers : tab === "losers" ? losers : tab === "active" ? mostActive : [];

  function formatValue(v: number): string {
    if (v >= 1e12) return (v / 1e12).toFixed(1) + "T";
    if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    return v.toLocaleString("fa-IR");
  }

  return (
    <AppLayout title="بازارها" subtitle="نمای کلی بازار سرمایه">
      {/* ------ Summary Cards ------ */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-surface-100">{summary.total_instruments}</div>
            <div className="text-xs text-surface-500">کل نمادها</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-accent-emerald">{summary.gainers}</div>
            <div className="text-xs text-surface-500">سبز (رشد)</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-accent-rose">{summary.losers}</div>
            <div className="text-xs text-surface-500">قرمز (کاهش)</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className={`text-2xl font-bold ${summary.avg_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
              {summary.avg_change_pct >= 0 ? "+" : ""}{summary.avg_change_pct.toFixed(2)}%
            </div>
            <div className="text-xs text-surface-500">میانگین تغییر</div>
          </div>
        </div>
      )}

      {/* ------ Tabs ------ */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {[
          { key: "overview", label: "نمای کلی" },
          { key: "gainers", label: "بیشترین رشد" },
          { key: "losers", label: "بیشترین کاهش" },
          { key: "active", label: "پرمعامله" },
          { key: "sectors", label: "صنایع" },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as typeof tab)}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${tab === t.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ------ Content ------ */}          {loadingHeatmap ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6, 7, 8].map(i => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : tab === "overview" ? (
        <div className="grid sm:grid-cols-2 gap-4">
          {/* Top gainers mini */}
          <div className="glass-card p-4">
            <h3 className="font-bold text-accent-emerald text-sm mb-3">بیشترین رشد</h3>
            <div className="space-y-1">
              {gainers.slice(0, 5).map(s => (
                <div key={s.symbol} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-surface-800/50">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-surface-200 font-mono">{s.symbol}</span>
                    {SparklineForSymbol(s.symbol)}
                  </div>
                  <span className="text-sm font-bold text-accent-emerald font-mono">+{(s.price_last_change_pct || 0).toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>
          {/* Top losers mini */}
          <div className="glass-card p-4">
            <h3 className="font-bold text-accent-rose text-sm mb-3">بیشترین کاهش</h3>
            <div className="space-y-1">
              {losers.slice(0, 5).map(s => (
                <div key={s.symbol} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-surface-800/50">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-surface-200 font-mono">{s.symbol}</span>
                    {SparklineForSymbol(s.symbol)}
                  </div>
                  <span className="text-sm font-bold text-accent-rose font-mono">{(s.price_last_change_pct || 0).toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : tab === "sectors" ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectors.map(s => (
            <div key={s.name} className="glass-card p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-surface-200 text-sm">{s.name}</h3>
                <span className="text-xs text-surface-500">{s.count} نماد</span>
              </div>
              <div className={`text-lg font-bold font-mono ${s.avgChange >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                {s.avgChange >= 0 ? "+" : ""}{s.avgChange.toFixed(2)}%
              </div>
              <div className="text-xs text-surface-500 mt-1">ارزش: {formatValue(s.totalValue)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="bg-surface-800/80 border-b border-surface-700">
                <th className="px-4 py-3 font-bold text-surface-300">#</th>
                <th className="px-4 py-3 font-bold text-surface-300">نماد</th>
                <th className="px-4 py-3 font-bold text-surface-300">نام</th>
                <th className="px-4 py-3 font-bold text-surface-300">قیمت</th>
                <th className="px-4 py-3 font-bold text-surface-300">تغییر</th>
                <th className="px-4 py-3 font-bold text-surface-300">حجم</th>
                <th className="px-4 py-3 font-bold text-surface-300">ارزش</th>
              </tr>
            </thead>
            <tbody>
              {displayList.slice(0, 50).map((s, i) => (
                <tr key={s.symbol} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                  <td className="px-4 py-2.5 text-surface-500 font-mono">{i + 1}</td>
                  <td className="px-4 py-2.5 font-bold text-surface-200 font-mono">{s.symbol}</td>
                  <td className="px-4 py-2.5 text-surface-400 text-xs">{s.name}</td>
                  <td className="px-4 py-2.5 font-mono text-surface-200">{(s.price_last || 0).toLocaleString("fa-IR")}</td>
                  <td className={`px-4 py-2.5 font-mono font-bold ${(s.price_last_change_pct || 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {(s.price_last_change_pct || 0) >= 0 ? "+" : ""}{(s.price_last_change_pct || 0).toFixed(2)}%
                  </td>
                  <td className="px-4 py-2.5 font-mono text-surface-400 text-xs">{formatValue(s.trade_volume || 0)}</td>
                  <td className="px-4 py-2.5 font-mono text-surface-400 text-xs">{formatValue(s.trade_value || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppLayout>
  );
}
