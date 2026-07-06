"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import MiniSparkline from "@/components/MiniSparkline";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface ScreenedItem {
  symbol: string;
  name: string;
  market: string;
  industry: string;
  last_price: number;
  change_pct: number;
  volume: number;
  value: number;
  liquidity_score: number;
  power_score: number;
  structure_score: number;
  orderflow_score: number;
  trigger_score: number;
  smc_score: number;
  phase: string;
  rank: number;
  reason: string;
}

interface ScreenerResponse {
  items: ScreenedItem[];
  total: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatPrice(v: number): string {
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(0) + "K";
  return v.toLocaleString("fa-IR");
}

function pctScore(score: number): number {
  return Math.round(score * 100);
}

function scoreBg(score: number): string {
  if (score >= 0.75) return "bg-accent-emerald";
  if (score >= 0.5) return "bg-accent-amber";
  if (score >= 0.25) return "bg-accent-rose/70";
  return "bg-surface-600";
}

function scoreBadgeBg(score: number): string {
  if (score >= 0.7) return "bg-accent-emerald/15 text-accent-emerald";
  if (score >= 0.5) return "bg-accent-amber/15 text-accent-amber";
  if (score >= 0.3) return "bg-accent-rose/15 text-accent-rose";
  return "bg-surface-600/30 text-surface-400";
}

function PhaseBadge({ phase, reason }: { phase: string; reason: string }) {
  const phaseColors: Record<string, string> = {
    accumulation: "bg-accent-emerald/15 text-accent-emerald",
    distribution: "bg-accent-rose/15 text-accent-rose",
    markup: "bg-primary-600/20 text-primary-300",
    markdown: "bg-accent-rose/20 text-accent-rose",
    neutral: "bg-surface-600/30 text-surface-400",
  };
  const phaseLabels: Record<string, string> = {
    accumulation: "تجمع",
    distribution: "توزیع",
    markup: "مارکاپ",
    markdown: "مارک‌داون",
    neutral: "خنثی",
  };
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
          phaseColors[phase] || phaseColors.neutral
        }`}
      >
        {phaseLabels[phase] || phase}
      </span>
      {reason && <span className="text-[10px] text-surface-500">{reason}</span>}
    </div>
  );
}

function ScoreBar({ value, label, maxWidth = 60 }: { value: number; label: string; maxWidth?: number }) {
  const pct = Math.min(value * 100, 100);
  return (
    <div className="flex items-center gap-1.5 group relative" style={{ maxWidth }}>
      <span className="text-[9px] text-surface-500 w-4 text-left shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${scoreBg(value)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Scoring Visualization ────────────────────────────────────────────────────────────────────────────────────────────────────────────

function ScoreGrid({ item }: { item: ScreenedItem }) {
  return (
    <div className="flex flex-col gap-1 min-w-[200px]">
      <ScoreBar value={item.liquidity_score} label="Liq" />
      <ScoreBar value={item.power_score} label="Pow" />
      <ScoreBar value={item.structure_score} label="Str" />
      <ScoreBar value={item.orderflow_score} label="Flw" />
      <ScoreBar value={item.trigger_score} label="Trg" />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { key: "smc_score", label: "SMC Score" },
  { key: "change_pct", label: "تغییرات" },
  { key: "liquidity_score", label: "نقدشوندگی" },
  { key: "power_score", label: "قدرت خرید" },
  { key: "structure_score", label: "ساختار قیمت" },
  { key: "trigger_score", label: "تریگر" },
  { key: "volume", label: "حجم" },
  { key: "value", label: "ارزش" },
];

const MARKET_OPTIONS = [
  { key: "", label: "همه بازارها" },
  { key: "BOURS", label: "بورس" },
  { key: "FARA", label: "فرابورس" },
  { key: "ENERGY", label: "انرژی" },
  { key: "COMMODITY", label: "کالا" },
];

export default function ScreenerPage() {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("smc_score");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [minScore, setMinScore] = useState(0);
  const [marketFilter, setMarketFilter] = useState("");

  // ── Fetch screener data ──
  const { data: rawData, isLoading } = useQuery({
    queryKey: ["screener", sortBy, sortOrder, minScore, marketFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      params.set("limit", "100");
      if (minScore > 0) params.set("min_score", String(minScore));
      if (marketFilter) params.set("market", marketFilter);

      const res = await apiGet<{ success: boolean; data: ScreenerResponse }>(
        `/screener?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0 };
    },
    refetchInterval: 120_000,
  });

  const items = rawData?.items ?? [];

  // ── Sparklines ──
  const sparkQuery = useMemo(() => {
    const syms = items.slice(0, 50).map((i) => i.symbol);
    return syms.join(",");
  }, [items]);

  const { data: sparkMap } = useQuery({
    queryKey: ["screener-spark", sparkQuery],
    queryFn: async () => {
      if (!sparkQuery) return {};
      try {
        const res = await apiGet<{ success: boolean; data: Record<string, number[]> }>(
          `/market/sparklines?symbols=${encodeURIComponent(sparkQuery)}&limit=30`
        );
        return res?.data ?? {};
      } catch {
        return {};
      }
    },
    enabled: !!sparkQuery,
    staleTime: 120_000,
  });

  // ── Search filter (client-side) ──
  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.trim().toLowerCase();
    return items.filter(
      (i) =>
        i.symbol.toLowerCase().includes(q) ||
        i.name.toLowerCase().includes(q) ||
        i.industry.toLowerCase().includes(q)
    );
  }, [items, search]);

  // ── Stats ──
  const stats = useMemo(() => {
    const total = filtered.length;
    const highScore = filtered.filter((i) => i.smc_score >= 0.6).length;
    const avgScore =
      total > 0
        ? filtered.reduce((sum, i) => sum + i.smc_score, 0) / total
        : 0;
    const avgLiq =
      total > 0
        ? filtered.reduce((sum, i) => sum + i.liquidity_score, 0) / total
        : 0;
    return { total, highScore, avgScore, avgLiq };
  }, [filtered]);

  // ── Render ──
  return (
    <AppLayout
      title="🔍 Stock Screener"
      subtitle="غربال‌گری هوشمند با ۵ فاز Smart Money"
    >
      {/* ── Stats cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="glass-card p-3 text-center">
          <p className="text-xl font-black text-surface-100">{stats.total}</p>
          <p className="text-xs text-surface-500">نماد</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-xl font-black text-accent-emerald">{stats.highScore}</p>
          <p className="text-xs text-surface-500">SMC ≥ 60%</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-xl font-black text-surface-100">
            {(stats.avgScore * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-surface-500">میانگین SMC</p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-xl font-black text-primary-300">
            {(stats.avgLiq * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-surface-500">میانگین نقدشوندگی</p>
        </div>
      </div>

      {/* ── Filters ── */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجوی نماد، نام، صنعت..."
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56"
        />

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm focus:outline-none focus:border-primary-500"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>

        <button
          onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
          className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-surface-200 text-sm hover:bg-surface-700 transition-colors"
        >
          {sortOrder === "desc" ? "⬇ نزولی" : "⬆ صعودی"}
        </button>

        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-500">min SMC:</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={minScore * 100}
            onChange={(e) => setMinScore(Number(e.target.value) / 100)}
            className="w-20 accent-primary-500"
          />
          <span className="text-xs font-mono text-surface-300 w-8 text-left">
            {(minScore * 100).toFixed(0)}%
          </span>
        </div>

        <div className="flex gap-1 flex-wrap">
          {MARKET_OPTIONS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMarketFilter(m.key)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all ${
                marketFilter === m.key
                  ? "bg-primary-600 text-white"
                  : "bg-surface-800 text-surface-400 hover:text-surface-200"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* ── Empty ── */}
      {!isLoading && filtered.length === 0 && (
        <div className="glass-card p-12 text-center text-surface-500">
          <p className="text-5xl mb-3">🔍</p>
          <p className="font-bold">نمادی یافت نشد</p>
          <p className="text-sm mt-1">
            {search
              ? "نمادی با این نام وجود ندارد"
              : "داده‌ای برای غربال‌گری موجود نیست"}
          </p>
        </div>
      )}

      {/* ── Results ── */}
      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.slice(0, 100).map((item) => {
            const sparkData = sparkMap?.[item.symbol];
            const smcNum = pctScore(item.smc_score);
            return (
              <Link
                key={`${item.rank}-${item.symbol}`}
                href={`/symbol/${encodeURIComponent(item.symbol)}`}
                className="glass-card p-4 flex items-center gap-4 hover:bg-white/[0.03] transition-colors group cursor-pointer"
              >
                {/* Sparkline */}
                <div className="shrink-0 w-[72px]">
                  {sparkData && sparkData.length > 1 ? (
                    <MiniSparkline data={sparkData} width={72} height={24} />
                  ) : (
                    <div className="h-6 flex items-center justify-center text-[9px] text-surface-600">
                      —
                    </div>
                  )}
                </div>

                {/* Symbol + name */}
                <div className="min-w-[120px] shrink-0">
                  <p className="font-bold text-surface-100 group-hover:text-primary-300 transition-colors">
                    {item.symbol}
                  </p>
                  <p className="text-[10px] text-surface-500 truncate max-w-[140px]">
                    {item.name}
                  </p>
                  {item.industry && (
                    <p className="text-[9px] text-surface-600 mt-0.5">
                      {item.industry}
                    </p>
                  )}
                </div>

                {/* Price + change */}
                <div className="min-w-[90px] shrink-0 text-right">
                  <p className="font-mono text-sm text-surface-200">
                    {item.last_price?.toLocaleString("fa-IR")}
                  </p>
                  <p
                    className={`font-mono text-xs ${
                      item.change_pct >= 0
                        ? "text-accent-emerald"
                        : "text-accent-rose"
                    }`}
                  >
                    {item.change_pct >= 0 ? "+" : ""}
                    {item.change_pct?.toFixed(2)}%
                  </p>
                </div>

                {/* Phase scores */}
                <div className="hidden md:flex flex-col gap-0.5 min-w-[180px]">
                  <ScoreGrid item={item} />
                </div>

                {/* SMC score */}
                <div className="min-w-[60px] shrink-0 text-center">
                  <div
                    className={`text-sm font-black px-2 py-1 rounded-lg ${
                      scoreBadgeBg(item.smc_score)
                    }`}
                  >
                    {smcNum}
                  </div>
                  <p className="text-[8px] text-surface-600 mt-0.5">SMC</p>
                </div>

                {/* Phase */}
                <div className="hidden lg:block min-w-[120px] shrink-0">
                  <PhaseBadge phase={item.phase} reason={item.reason} />
                </div>

                {/* Volume */}
                <div className="hidden sm:block min-w-[70px] shrink-0 text-right">
                  <p className="font-mono text-xs text-surface-400">
                    {formatPrice(item.volume)}
                  </p>
                  <p className="text-[8px] text-surface-600">حجم</p>
                </div>

                {/* Arrow */}
                <div className="mr-auto shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="material-icons text-surface-500 text-lg">
                    chevron_left
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
