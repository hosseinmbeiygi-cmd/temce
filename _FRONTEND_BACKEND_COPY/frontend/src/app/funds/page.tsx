"use client";

import { Suspense, useState, useMemo, useEffect, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import FundCard from "@/components/FundCard";
import FundDetailDrawer from "@/components/FundDetailDrawer";
import FundCompareModal from "@/components/FundCompareModal";
import BubbleHeatmap from "@/components/BubbleHeatmap";
import ArbitrageTable from "@/components/ArbitrageTable";
import DataDensityToggle from "@/components/DataDensityToggle";
import { apiGet } from "@/lib/api";
import {
  FUND_GROUPS,
  SECTOR_SUBGROUPS,
  detectFundGroup,
  detectFundSubgroup,
  getGroupDef,
  calcBubble,
  type FundGroup,
  type SectorSubgroup,
} from "@/lib/fund-categories";
import { scoringEngine, type Fund } from "@/lib/fund-analysis";

interface FundsResponse {
  total: number;
  limit: number;
  offset: number;
  items: Fund[];
  type_counts?: Record<string, number>;
  market_counts?: Record<string, number>;
}

function formatNum(v: number): string {
  if (!v) return "\u2014";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function FundsPageContent() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("score");
  const [groupFilter, setGroupFilter] = useState<FundGroup | "all">("all");
  const [sectorSubFilter, setSectorSubFilter] = useState<SectorSubgroup | "all">("all");
  const [marketFilter, setMarketFilter] = useState("\u0647\u0645\u0647");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [densityMode, setDensityMode] = useState<"compact" | "pro">("compact");
  const [tab, setTab] = useState<"list" | "bubble" | "arbitrage">("list");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);
  const [drawerFund, setDrawerFund] = useState<Fund | null>(null);

  const searchParams = useSearchParams();
  useEffect(() => {
    const t = searchParams?.get("type");
    if (t) {
      const typeMap: Record<string, FundGroup> = {
        "\u0633\u0647\u0627\u0645\u06cc": "equity",
        "\u062f\u0631\u0622\u0645\u062f \u062b\u0627\u0628\u062a": "fixed_income",
        "\u0645\u062e\u0637\u0644\u062a": "mixed",
        "\u0637\u0644\u0627": "gold",
        "\u0627\u0647\u0631\u0645\u06cc": "leveraged",
        "\u0628\u062e\u0634\u06cc": "sector",
        "\u0634\u0627\u062e\u0635\u06cc": "index",
      };
      setGroupFilter(typeMap[t] || "all");
    }
  }, [searchParams]);

  const { data: fundsData, isLoading } = useQuery({
    queryKey: ["funds"],
    queryFn: async (): Promise<FundsResponse> => {
      const params = new URLSearchParams();
      params.set("limit", "500");
      if (marketFilter !== "\u0647\u0645\u0647") params.set("market", marketFilter === "\u0628\u0648\u0631\u0633 \u062a\u0647\u0631\u0627\u0646" ? "tse" : "ime");
      const res = await apiGet<FundsResponse>(`/funds?${params.toString()}`);
      return res ?? { total: 0, limit: 500, offset: 0, items: [] };
    },
    refetchInterval: 120_000,
    staleTime: 30_000,
  });

  const funds = fundsData?.items ?? [];

  const enrichedFunds = useMemo(() => {
    return funds.map((f) => {
      const group = detectFundGroup(f.name, f.fund_type);
      const subgroup = detectFundSubgroup(f.name, group);
      const scores = scoringEngine(f);
      return { ...f, _group: group, _subgroup: subgroup, _score: scores.total };
    });
  }, [funds]);

  const groupCounts = useMemo(() => {
    const counts: Record<string, number> = { all: enrichedFunds.length };
    for (const f of enrichedFunds) {
      counts[f._group] = (counts[f._group] || 0) + 1;
    }
    return counts;
  }, [enrichedFunds]);

  const sectorSubCounts = useMemo(() => {
    if (groupFilter !== "sector") return {};
    const counts: Record<string, number> = { all: enrichedFunds.filter((f) => f._group === "sector").length };
    for (const f of enrichedFunds.filter((f) => f._group === "sector")) {
      counts[f._subgroup || "other_sector"] = (counts[f._subgroup || "other_sector"] || 0) + 1;
    }
    return counts;
  }, [enrichedFunds, groupFilter]);

  const filtered = useMemo(() => {
    let list = enrichedFunds;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((f) => f.symbol.toLowerCase().includes(q) || f.name.toLowerCase().includes(q) || (f.isin && f.isin.toLowerCase().includes(q)));
    }
    if (groupFilter !== "all") list = list.filter((f) => f._group === groupFilter);
    if (groupFilter === "sector" && sectorSubFilter !== "all") list = list.filter((f) => f._subgroup === sectorSubFilter);
    const sorted = [...list].sort((a, b) => {
      switch (sortBy) {
        case "score": return b._score - a._score;
        case "change": return b.nav_change_pct - a.nav_change_pct;
        case "volume": return b.trade_volume - a.trade_volume;
        case "value": return b.trade_value - a.trade_value;
        case "market_value": return b.market_value - a.market_value;
        case "shares": return b.shares_count - a.shares_count;
        case "bubble": return (calcBubble(b.price_last, b.nav) ?? 0) - (calcBubble(a.price_last, a.nav) ?? 0);
        case "name": return a.name.localeCompare(b.name, "fa");
        default: return b.nav - a.nav;
      }
    });
    return sorted;
  }, [enrichedFunds, search, groupFilter, sectorSubFilter, sortBy]);

  const displaySymbols = useMemo(() => filtered.slice(0, 200), [filtered]);
  const navSymbols = useMemo(() => displaySymbols.map((f) => f.symbol), [displaySymbols]);
  const { data: navHistory } = useQuery({
    queryKey: ["funds-nav-history", navSymbols.join(",")],
    queryFn: async () => {
      if (!navSymbols.length) return {} as Record<string, { date: string; nav: number; source?: string }[]>;
      try {
        const res = await apiGet<{ symbols?: Record<string, { date: string; nav: number; source?: string }[]> }>(`/funds/nav-history?symbols=${encodeURIComponent(navSymbols.join(","))}&limit=60`);
        return res?.symbols ?? {};
      } catch { return {}; }
    },
    staleTime: 120_000,
  });

  const navSparkMap = useMemo(() => {
    const result: Record<string, { date: string; nav: number }[]> = {};
    for (const [sym, points] of Object.entries(navHistory ?? {})) {
      const cleaned = (points ?? []).map((p) => ({ date: p.date, nav: Number(p.nav) })).filter((p) => Number.isFinite(p.nav) && p.nav > 0 && p.date);
      if (cleaned.length > 1) result[sym] = cleaned.slice(-30);
    }
    return result;
  }, [navHistory]);

  const stats = useMemo(() => {
    if (!filtered.length) return null;
    const positive = filtered.filter((f) => f.nav_change_pct > 0).length;
    const totalAum = filtered.reduce((s, f) => s + f.market_value, 0);
    const totalVolume = filtered.reduce((s, f) => s + f.trade_volume, 0);
    const avgScore = filtered.reduce((s, f) => s + f._score, 0) / filtered.length;
    const highBubble = filtered.filter((f) => { const b = calcBubble(f.price_last, f.nav); return b !== null && b > 5; }).length;
    const discounted = filtered.filter((f) => { const b = calcBubble(f.price_last, f.nav); return b !== null && b < -2; }).length;
    return { count: filtered.length, positive, negative: filtered.length - positive, totalAum, totalVolume, avgScore: Math.round(avgScore), highBubble, discounted };
  }, [filtered]);

  const selectedFunds = useMemo(() => enrichedFunds.filter((f) => selected.has(f.symbol)), [enrichedFunds, selected]);

  const toggleSelect = useCallback((symbol: string) => {
    setSelected((prev) => { const next = new Set(prev); if (next.has(symbol)) next.delete(symbol); else if (next.size < 4) next.add(symbol); return next; });
  }, []);

  const removeFromCompare = useCallback((symbol: string) => {
    setSelected((prev) => { const next = new Set(prev); next.delete(symbol); if (next.size < 2) setCompareOpen(false); return next; });
  }, []);

  const closeCompare = useCallback(() => { setCompareOpen(false); setSelected(new Set()); }, []);
  const currentGroupDef = groupFilter !== "all" ? getGroupDef(groupFilter) : null;

  const ALL_LABEL = "\u0647\u0645\u0647";
  const TSE_LABEL = "\u0628\u0648\u0631\u0633 \u062a\u0647\u0631\u0627\u0646";
  const IME_LABEL = "\u0628\u0648\u0631\u0633 \u06a9\u0627\u0644\u0627";
  const ALL_MARKETS = "\u0647\u0645\u0647 \u0628\u0627\u0632\u0627\u0631\u0647\u0627";

  return (
    <AppLayout
      title={<span className="flex items-center gap-2">{"\uD83C\uDFE6"} {"\u0635\u0646\u062F\u0648\u0642\u200C\u0647\u0627\u06CC \u0633\u0631\u0645\u0627\u06CC\u0647\u200C\u06AF\u0630\u0627\u0631\u06CC"}{currentGroupDef && <span className={`text-sm px-2 py-0.5 rounded-full font-bold ${currentGroupDef.color} ${currentGroupDef.textColor}`}>{currentGroupDef.icon} {currentGroupDef.label}</span>}</span>}
      subtitle={`${"\u062a\u0645\u0627\u0645 \u0635\u0646\u062F\u0648\u0642\u200C\u0647\u0627\u06CC \u0628\u0648\u0631\u0633 \u062a\u0647\u0631\u0627\u0646 \u0648 \u0628\u0648\u0631\u0633 \u06a9\u0627\u0644\u0627 \u2014 \u062a\u062d\u0644\u06cc\u0644 \u0647\u0648\u0634\u0645\u0646\u062F"} ${enrichedFunds.length} ${"\u0635\u0646\u062F\u0648\u0642"}`}
    >
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
          <div className="glass-card p-3 text-center"><p className="text-xl font-black text-ink">{stats.count}</p><p className="text-[9px] text-ink-3">{"\u0635\u0646\u062F\u0648\u0642"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-xl font-black text-emerald-400">{stats.positive}</p><p className="text-[9px] text-ink-3">{"\u0645\u0633\u0628\u062a"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-xl font-black text-rose-400">{stats.negative}</p><p className="text-[9px] text-ink-3">{"\u0645\u0646\u0641\u06cc"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-lg font-black font-mono text-primary-300">{formatNum(stats.totalAum)}</p><p className="text-[9px] text-ink-3">{"\u0627\u0631\u0632\u0634 \u06a9\u0644"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-lg font-black font-mono text-ink">{formatNum(stats.totalVolume)}</p><p className="text-[9px] text-ink-3">{"\u062d\u062c\u0645 \u06a9\u0644"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-xl font-black font-mono text-primary-300">{stats.avgScore}</p><p className="text-[9px] text-ink-3">{"\u0627\u0645\u062a\u06cc\u0627\u0632 \u0645\u06cc\u0627\u0646\u06af\u06cc\u0646"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-xl font-black text-amber-400">{stats.highBubble}</p><p className="text-[9px] text-ink-3">{"\u062d\u0628\u0627\u0628 \u0628\u0627\u0644\u0627"}</p></div>
          <div className="glass-card p-3 text-center"><p className="text-xl font-black text-emerald-400">{stats.discounted}</p><p className="text-[9px] text-ink-3">{"\u062a\u062e\u0641\u06cc\u0641\u062f\u0627\u0631"}</p></div>
        </div>
      )}

      <div className="flex items-center gap-3 mb-3">
        <div className="relative flex-1 max-w-sm">
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-3 material-icons text-sm">search</span>
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={"\u062c\u0633\u062a\u062c\u0648\u06cc \u0646\u0627\u0645\u060c \u0646\u0645\u0627\u062f\u060c ISIN..."} className="w-full pr-9 pl-3 py-2 bg-soft border border-line rounded-xl text-ink text-sm focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/30 transition-all" />
          {search && <button onClick={() => setSearch("")} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink transition-colors"><span className="material-icons text-sm">close</span></button>}
        </div>
        <div className="flex bg-soft rounded-lg border border-line p-0.5">
          <button onClick={() => setTab("list")} className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 ${tab === "list" ? "bg-primary-600 text-white shadow" : "text-ink-3 hover:text-ink"}`} title={"\u0641\u0647\u0631\u0633\u062a \u0635\u0646\u062f\u0648\u0642\u200C\u0647\u0627"}>
            <span className="material-icons text-xs">view_list</span> فهرست
          </button>
          <button onClick={() => setTab("bubble")} className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 ${tab === "bubble" ? "bg-primary-600 text-white shadow" : "text-ink-3 hover:text-ink"}`} title={"\u0645\u0627\u0646\u06cc\u062a\u0648\u0631 \u062d\u0628\u0627\u0628"}>
            <span className="material-icons text-xs">bubble_chart</span> حباب
          </button>
          <button onClick={() => setTab("arbitrage")} className={`px-2.5 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 ${tab === "arbitrage" ? "bg-primary-600 text-white shadow" : "text-ink-3 hover:text-ink"}`} title={"\u0641\u0631\u0635\u062a\u200C\u0647\u0627\u06cc \u0622\u0631\u0628\u06cc\u062a\u0631\u0627\u0698"}>
            <span className="material-icons text-xs">sync_alt</span> آربیتراژ
          </button>
        </div>
        {tab === "list" && (
          <>
            <div className="flex bg-soft rounded-lg border border-line p-0.5">
              <button onClick={() => setViewMode("list")} className={`p-1.5 rounded-md transition-all ${viewMode === "list" ? "bg-primary-600 text-white" : "text-ink-3 hover:text-ink"}`} title={"\u0646\u0645\u0627\u06cc \u0644\u06cc\u0633\u062a"}><span className="material-icons text-sm">view_list</span></button>
              <button onClick={() => setViewMode("grid")} className={`p-1.5 rounded-md transition-all ${viewMode === "grid" ? "bg-primary-600 text-white" : "text-ink-3 hover:text-ink"}`} title={"\u0646\u0645\u0627\u06cc \u0634\u0628\u06a9\u0647\u200c\u0627\u06cc"}><span className="material-icons text-sm">grid_view</span></button>
            </div>
            <DataDensityToggle mode={densityMode} onChange={setDensityMode} />
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-2">
        {tab !== "list" && (
          <button onClick={() => setTab("list")} className="px-2.5 py-1 rounded-lg text-[10px] font-bold bg-soft text-ink-3 hover:text-ink border border-line mb-1">
            ‎← بازگشت به فهرست
          </button>
        )}
        <button onClick={() => { setGroupFilter("all"); setSectorSubFilter("all"); }} className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all ${groupFilter === "all" ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20" : "bg-soft text-ink-3 hover:text-ink border border-line"}`}>
          {ALL_LABEL} ({groupCounts.all || 0})
        </button>
        {FUND_GROUPS.filter((g) => (groupCounts[g.id] || 0) > 0).map((g) => (
          <button key={g.id} onClick={() => { setGroupFilter(g.id); setSectorSubFilter("all"); }} className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all ${groupFilter === g.id ? `${g.color} ${g.textColor} shadow-lg` : "bg-soft text-ink-3 hover:text-ink border border-line"}`}>
            {g.icon} {g.label} ({groupCounts[g.id] || 0})
          </button>
        ))}
      </div>

      {groupFilter === "sector" && Object.keys(sectorSubCounts).length > 1 && (
        <div className="flex flex-wrap gap-1 mb-2">
          <span className="text-[9px] text-ink-3 self-center ml-1">{"\u0632\u06cc\u0631\u06af\u0631\u0648\u0647:"}</span>
          <button onClick={() => setSectorSubFilter("all")} className={`px-2 py-0.5 rounded-md text-[9px] font-bold transition-all ${sectorSubFilter === "all" ? "bg-orange-500/20 text-orange-300" : "bg-soft text-ink-3 hover:text-ink border border-line"}`}>
            {"\u0647\u0645\u0647 \u0628\u062e\u0634\u06cc"}
          </button>
          {SECTOR_SUBGROUPS.filter((sg) => (sectorSubCounts[sg.id] || 0) > 0).map((sg) => (
            <button key={sg.id} onClick={() => setSectorSubFilter(sg.id)} className={`px-2 py-0.5 rounded-md text-[9px] font-bold transition-all ${sectorSubFilter === sg.id ? "bg-orange-500/20 text-orange-300" : "bg-soft text-ink-3 hover:text-ink border border-line"}`}>
              {sg.icon} {sg.label} ({sectorSubCounts[sg.id] || 0})
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="px-2.5 py-1.5 bg-soft border border-line rounded-lg text-ink text-[11px] focus:outline-none focus:border-primary-500">
          <option value="score">{"\uD83C\uDFC6 \u0627\u0645\u062a\u06cc\u0627\u0632"}</option>
          <option value="change">{"\uD83D\uDCC8 \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a"}</option>
          <option value="volume">{"\uD83D\uDCCA \u062d\u062c\u0645"}</option>
          <option value="value">{"\uD83D\uDCB0 \u0627\u0631\u0632\u0634 \u0645\u0639\u0627\u0645\u0644\u0627\u062a"}</option>
          <option value="market_value">{"\uD83C\uDFE6 \u0627\u0631\u0632\u0634 \u0628\u0627\u0632\u0627\u0631"}</option>
          <option value="bubble">{"\uD83E\uDEE7 \u062d\u0628\u0627\u0628 P/NAV"}</option>
          <option value="shares">{"\uD83D\uDCE6 \u062a\u0639\u062f\u0627\u062f \u0648\u0627\u062d\u062f"}</option>
          <option value="name">{"\uD83D\uDD24 \u0646\u0627\u0645"}</option>
        </select>

        {marketFilter !== ALL_LABEL && (
          <select value={marketFilter} onChange={(e) => setMarketFilter(e.target.value)} className="px-2.5 py-1.5 bg-soft border border-line rounded-lg text-ink text-[11px] focus:outline-none focus:border-primary-500">
            <option value={ALL_LABEL}>{ALL_MARKETS}</option>
            <option value={TSE_LABEL}>{TSE_LABEL}</option>
            <option value={IME_LABEL}>{IME_LABEL}</option>
          </select>
        )}

        <div className="mr-auto flex items-center gap-2">
          <button onClick={() => setCompareOpen(true)} disabled={selected.size < 2} onDragOver={(e) => { if (e.dataTransfer.types.includes("text/symbol")) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } }} onDrop={(e) => { const s = e.dataTransfer.getData("text/symbol"); if (s) toggleSelect(s); }} className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1 ${selected.size >= 2 ? "bg-primary-600 text-white hover:bg-primary-500 shadow-lg shadow-primary-600/20" : "bg-soft text-ink-500 cursor-not-allowed border border-line"}`}>
            <span className="material-icons text-xs">compare_arrows</span>
            {"\u0645\u0642\u0627\u06cc\u0633\u0647"}
            {selected.size > 0 && <span className="text-[8px] bg-black/20 px-1.5 py-0.5 rounded-full">{selected.size}</span>}
          </button>
          {selected.size > 0 && <button onClick={() => setSelected(new Set())} className="text-[9px] text-ink-3 hover:text-rose-400 transition-colors">{"\u067e\u0627\u06a9 \u06a9\u0631\u062f\u0646"}</button>}
          <span className="text-[10px] text-ink-3 font-mono">{filtered.length} {"\u0635\u0646\u062F\u0648\u0642"}</span>
        </div>
      </div>

{isLoading && tab === "list" && <div className="space-y-2">{[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}</div>}

      {isLoading && tab !== "list" && (
        <div className="space-y-3">
          <Skeleton className="h-44 w-full rounded-2xl" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        </div>
      )}

      {tab === "list" && !isLoading && filtered.length === 0 && (
        <div className="glass-card p-12 text-center text-ink-3">
          <p className="text-5xl mb-3">{"\uD83C\uDFE6"}</p>
          <p className="font-bold text-ink">{"\u0635\u0646\u062F\u0648\u0642\u06CC \u06cc\u0627\u0641\u062a \u0646\u0634\u062F"}</p>
          <p className="text-sm mt-1">{search ? "\u0635\u0646\u062F\u0648\u0642\u06cc \u0628\u0627 \u0627\u06cc\u0646 \u0645\u0634\u062e\u0635\u0627\u062a \u0648\u062c\u0648\u062f \u0646\u062f\u0627\u0631\u062f" : "\u062f\u0627\u062f\u0647\u200C\u0627\u06cc \u0627\u0632 \u0635\u0646\u062F\u0648\u0642\u200C\u0647\u0627 \u0645\u0648\u062C\u0648\u062F \u0646\u06cc\u0633\u062A"}</p>
        </div>
      )}

      {tab === "list" && !isLoading && filtered.length > 0 && (
        <div className={densityMode === "pro" ? "space-y-2" : "space-y-1.5"}>
          {filtered.map((fund) => (
            <div key={fund.symbol} className="relative group/card" draggable onDragStart={(e) => { e.dataTransfer.setData("text/symbol", fund.symbol); e.dataTransfer.effectAllowed = "copy"; }}>
              <FundCard fund={fund} navPoints={navSparkMap[fund.symbol]} isSelected={selected.has(fund.symbol)} onSelect={toggleSelect} view={viewMode} />
              <button onClick={() => setDrawerFund(fund)} className="absolute top-2 left-2 z-10 opacity-0 group-hover/card:opacity-100 transition-opacity bg-primary-600/80 hover:bg-primary-600 text-white text-[9px] px-2 py-1 rounded-lg backdrop-blur-sm" title={"\u0646\u0645\u0627\u06cc \u0633\u0631\u06cc\u0639"}>
                <span className="material-icons text-xs align-middle">visibility</span> {"\u0633\u0631\u06cc\u0639"}
              </button>
            </div>
          ))}
        </div>
      )}

      {tab === "bubble" && (
        <div className="space-y-4">
          <BubbleHeatmap
            funds={funds}
            activeGroup={groupFilter}
            onPickGroup={(g) => { setGroupFilter(g); setTab("list"); }}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {["leveraged", "gold", "fixed_income"].map((g) => {
              const groupFunds = enrichedFunds.filter((f) => f._group === g).slice(0, 5);
              if (!groupFunds.length) return null;
              return (
                <div key={g} className="glass-card p-3">
                  <p className="text-[11px] font-black text-ink mb-2">{FUND_GROUPS.find((x) => x.id === g)?.label}</p>
                  <div className="space-y-1">
                    {groupFunds.map((f) => {
                      const b = calcBubble(f.price_last, f.nav);
                      return (
                        <button key={f.symbol} onClick={() => setDrawerFund(f)} className="w-full flex items-center justify-between text-[10px] hover:bg-soft/40 rounded px-1 py-0.5">
                          <span className="font-mono font-bold">{f.symbol}</span>
                          <span className={`font-mono ${b === null ? "text-ink-3" : b > 0 ? "text-rose-300" : "text-emerald-300"}`}>
                            {b === null ? "—" : `${b > 0 ? "+" : ""}${b.toFixed(2)}٪`}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "arbitrage" && (
        <ArbitrageTable funds={funds} onPick={(sym) => {
          const f = enrichedFunds.find((x) => x.symbol === sym);
          if (f) setDrawerFund(f);
        }} />
      )}

      <div className="mt-6 p-3 glass-card text-center">
        <p className="text-[9px] text-ink-3/60 leading-relaxed">
          {"\u26A0\uFE0F \u0627\u06cc\u0646 \u062a\u062d\u0644\u06cc\u0644 \u062e\u0648\u062F\u06a9\u0627\u0631 \u0648 \u0635\u0631\u0641\u0627\u064B \u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06CC \u0627\u0633\u062a\u060C \u062a\u0648\u0635\u06cc\u0647 \u0645\u0627\u0644\u06CC \u0631\u0633\u0645\u06CC \u0645\u062d\u0633\u0648\u0628 \u0646\u0645\u06cc\u200c\u0634\u0648\u062F \u0648 \u0645\u0633\u0626\u0648\u0644\u06cc\u062a \u062a\u0635\u0645\u06cc\u0645 \u0633\u0631\u0645\u0627\u06cc\u0647\u200c\u06AF\u0630\u0627\u0631\u06CC \u0628\u0631 \u0639\u0647\u062F\u0647 \u06a9\u0627\u0631\u0628\u0631 \u0627\u0633\u062a. \u0645\u0634\u0627\u0648\u0631\u0647 \u0631\u0633\u0645\u06CC \u0646\u06cc\u0627\u0632\u0645\u0646\u062F \u0645\u062c\u0648\u0632 \u0645\u062c\u0648\u0627\u0632 \u0633\u0627\u0632\u0645\u0627\u0646 \u0628\u0648\u0631\u0633 \u0648 \u0627\u0648\u0631\u0627\u0642 \u0628\u0647\u0627\u062F\u0631 \u0627\u0633\u062a."}
        </p>
      </div>

      {drawerFund && <FundDetailDrawer fund={drawerFund} onClose={() => setDrawerFund(null)} />}
      {compareOpen && selectedFunds.length >= 2 && <FundCompareModal funds={selectedFunds} onClose={closeCompare} onRemove={removeFromCompare} />}
    </AppLayout>
  );
}

export default function FundsPage() {
  return (
    <Suspense fallback={<AppLayout title={"\uD83C\uDFE6 \u0635\u0646\u062F\u0648\u0642\u200C\u0647\u0627\u06CC \u0633\u0631\u0645\u0627\u06CC\u0647\u200C\u06AF\u0630\u0627\u0631\u06CC"}><Skeleton className="h-64 w-full rounded-2xl" /></AppLayout>}>
      <FundsPageContent />
    </Suspense>
  );
}
