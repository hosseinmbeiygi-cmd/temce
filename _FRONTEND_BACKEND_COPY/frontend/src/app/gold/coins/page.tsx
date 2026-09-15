"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownUp,
  Coins as CoinsIcon,
  Crown,
  Filter,
  Gem,
  Search,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { getSnapshot, subscribeGoldWS } from "@/lib/goldApi";
import type { AssetBlock, Decision, Snapshot } from "@/types/gold";

// ── Helpers (kept local — no shared utils to avoid coupling) ──────────────

const FA = "fa-IR";

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return n.toLocaleString(FA, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return sign + n.toFixed(digits) + "٪";
}

type BubbleBand = { bg: string; text: string; ring: string; label: string };

function bubbleBand(pct: number | null): BubbleBand {
  if (pct === null) return { bg: "bg-zinc-800/40", text: "text-zinc-500", ring: "ring-zinc-700", label: "—" };
  if (pct < 5) return { bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "ring-emerald-700/30", label: "بدون حباب" };
  if (pct < 12) return { bg: "bg-lime-500/10", text: "text-lime-300", ring: "ring-lime-700/30", label: "حباب کم" };
  if (pct < 22) return { bg: "bg-amber-500/10", text: "text-amber-300", ring: "ring-amber-700/30", label: "حباب متوسط" };
  return { bg: "bg-rose-500/10", text: "text-rose-300", ring: "ring-rose-700/30", label: "حباب شدید" };
}

type SortKey = "name" | "price" | "fair" | "bubble" | "implied";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "name", label: "نام" },
  { key: "price", label: "قیمت" },
  { key: "fair", label: "ارزش ذاتی" },
  { key: "bubble", label: "حباب" },
  { key: "implied", label: "دلار ضمنی" },
];

// ── Sub-components ──────────────────────────────────────────────────────

function CoinBigCard({ a }: { a: AssetBlock }) {
  const b = bubbleBand(a.bubble_pct);
  const direction = a.bubble_pct === null ? "neutral" : a.bubble_pct < 5 ? "buy" : a.bubble_pct < 22 ? "watch" : "avoid";
  return (
    <div className={`relative rounded-2xl ring-1 ${b.ring} ${b.bg} p-5 backdrop-blur transition hover:scale-[1.01]`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Crown className={`w-4 h-4 ${b.text}`} />
          <div className="text-sm font-semibold text-zinc-100">{a.display_name}</div>
        </div>
        <div className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ring-current/20 ${b.text}`}>{b.label}</div>
      </div>
      <div className="text-3xl font-black text-zinc-100 tabular-nums mb-1">{fmt(a.market_price)}</div>
      <div className="text-[10px] text-zinc-500 mb-3 flex items-center justify-between">
        <span>ذاتی: {fmt(a.fair_value)}</span>
        <span>USD: {fmt(a.implied_usd, 0)}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 border-t border-zinc-800/60 pt-3">
        <div>
          <div className="text-[10px] text-zinc-500">حباب</div>
          <div className={`text-lg font-bold tabular-nums ${b.text}`}>{fmtPct(a.bubble_pct)}</div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500">سیگنال</div>
          <div className={`text-sm font-semibold ${direction === "buy" ? "text-emerald-300" : direction === "watch" ? "text-amber-300" : direction === "avoid" ? "text-rose-300" : "text-zinc-500"}`}>
            {direction === "buy" ? "خرید تدریجی" : direction === "watch" ? "نظارت" : direction === "avoid" ? "صبر" : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function CoinsTable({ rows }: { rows: AssetBlock[] }) {
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40">
      <table className="w-full text-sm">
        <thead className="text-[10px] text-zinc-500 bg-zinc-900/70">
          <tr>
            <th className="text-right py-2 px-3 font-medium">نماد</th>
            <th className="text-right py-2 px-3 font-medium">نام</th>
            <th className="text-right py-2 px-3 font-medium">قیمت بازار</th>
            <th className="text-right py-2 px-3 font-medium">ارزش ذاتی</th>
            <th className="text-right py-2 px-3 font-medium">حباب</th>
            <th className="text-right py-2 px-3 font-medium">USD ضمنی</th>
            <th className="text-right py-2 px-3 font-medium">سیگنال</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => {
            const b = bubbleBand(a.bubble_pct);
            const signal = a.bubble_pct === null
              ? { text: "—", cls: "text-zinc-500" }
              : a.bubble_pct < 5
                ? { text: "خرید", cls: "text-emerald-300" }
                : a.bubble_pct < 12
                  ? { text: "خرید تدریجی", cls: "text-lime-300" }
                  : a.bubble_pct < 22
                    ? { text: "نظارت", cls: "text-amber-300" }
                    : { text: "صبر", cls: "text-rose-300" };
            return (
              <tr key={a.symbol} className="border-t border-zinc-800/40 hover:bg-zinc-800/20 transition">
                <td className="py-2.5 px-3 text-zinc-300 font-mono text-[11px]">{a.symbol}</td>
                <td className="py-2.5 px-3 text-zinc-100">{a.display_name}</td>
                <td className="py-2.5 px-3 text-zinc-100 tabular-nums font-semibold">{fmt(a.market_price)}</td>
                <td className="py-2.5 px-3 text-zinc-400 tabular-nums">{fmt(a.fair_value)}</td>
                <td className={`py-2.5 px-3 tabular-nums font-bold ${b.text}`}>{fmtPct(a.bubble_pct)}</td>
                <td className="py-2.5 px-3 text-zinc-400 tabular-nums">{fmt(a.implied_usd, 0)}</td>
                <td className={`py-2.5 px-3 text-xs font-semibold ${signal.cls}`}>{signal.text}</td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className="py-6 text-center text-zinc-500 text-xs">موردی یافت نشد.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function CoinsSummary({ snap }: { snap: Snapshot }) {
  const coins = Object.values(snap.coins);
  const n = coins.length;
  const avgBubble = n > 0 ? coins.reduce((s, c) => s + (c.bubble_pct ?? 0), 0) / n : 0;
  const healthy = coins.filter((c) => c.bubble_pct !== null && c.bubble_pct < 5).length;
  const overheated = coins.filter((c) => c.bubble_pct !== null && c.bubble_pct >= 22).length;
  return (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <SummaryTile icon={CoinsIcon} label="تعداد سکه" value={fmt(n)} tone="neutral" />
      <SummaryTile
        icon={Sparkles}
        label="میانگین حباب"
        value={fmtPct(avgBubble)}
        tone={avgBubble < 5 ? "good" : avgBubble < 12 ? "warn" : "bad"}
      />
      <SummaryTile icon={TrendingUp} label="بدون حباب" value={fmt(healthy)} tone="good" />
      <SummaryTile icon={TrendingDown} label="حباب شدید" value={fmt(overheated)} tone={overheated > 0 ? "bad" : "neutral"} />
    </section>
  );
}

function SummaryTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "neutral";
}) {
  const toneCls = {
    good: "text-emerald-300",
    warn: "text-amber-300",
    bad: "text-rose-300",
    neutral: "text-zinc-100",
  }[tone];
  return (
    <div className="rounded-xl bg-zinc-900/40 ring-1 ring-zinc-800/60 p-4 flex items-center gap-3">
      <Icon className={`w-5 h-5 ${toneCls}`} />
      <div>
        <div className="text-[10px] text-zinc-500">{label}</div>
        <div className={`text-lg font-bold tabular-nums ${toneCls}`}>{value}</div>
      </div>
    </div>
  );
}

function DecisionBadge({ decision }: { decision: Decision }) {
  const map: Record<Decision, { label: string; cls: string }> = {
    GREEN: { label: "سبز — ورود", cls: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30" },
    YELLOW: { label: "زرد — احتیاط", cls: "bg-amber-500/15 text-amber-300 ring-amber-500/30" },
    RED: { label: "قرمز — صبر", cls: "bg-rose-500/15 text-rose-300 ring-rose-500/30" },
  };
  const m = map[decision];
  return <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold ring-1 ${m.cls}`}>{m.label}</span>;
}

// ── Page ───────────────────────────────────────────────────────────────

export default function GoldCoinsPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: getSnapshot,
    refetchInterval: 60_000,
    staleTime: 55_000,
  });

  const [view, setView] = useState<"cards" | "table">("cards");
  const [query, setQuery] = useState("");
  const [bubbleFilter, setBubbleFilter] = useState<"all" | "low" | "mid" | "high">("all");
  const [sortKey, setSortKey] = useState<SortKey>("bubble");
  const [sortDesc, setSortDesc] = useState(false);

  useEffect(() => {
    const unsub = subscribeGoldWS(() => refetch());
    return unsub;
  }, [refetch]);

  const rows = useMemo(() => {
    if (!data) return [] as AssetBlock[];
    let items = Object.values(data.coins);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      items = items.filter((a) => a.display_name.toLowerCase().includes(q) || a.symbol.toLowerCase().includes(q));
    }
    if (bubbleFilter !== "all") {
      const bands = { low: [0, 5], mid: [5, 22], high: [22, 1e9] } as const;
      const [lo, hi] = bands[bubbleFilter];
      items = items.filter((a) => a.bubble_pct !== null && a.bubble_pct >= lo && a.bubble_pct < hi);
    }
    items = [...items].sort((a, b) => {
      const dir = sortDesc ? -1 : 1;
      switch (sortKey) {
        case "name": return dir * a.display_name.localeCompare(b.display_name);
        case "price": return dir * ((a.market_price ?? 0) - (b.market_price ?? 0));
        case "fair": return dir * ((a.fair_value ?? 0) - (b.fair_value ?? 0));
        case "bubble": return dir * ((a.bubble_pct ?? -1e9) - (b.bubble_pct ?? -1e9));
        case "implied": return dir * ((a.implied_usd ?? 0) - (b.implied_usd ?? 0));
      }
    });
    return items;
  }, [data, query, bubbleFilter, sortKey, sortDesc]);

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-zinc-500 text-sm">در حال بارگذاری سکه‌ها...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Gem className="w-5 h-5 text-amber-400" /> سکه‌های پایش‌شده
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            حباب، ارزش ذاتی و سیگنال — بر اساس آخرین اسنپ‌شبت ({new Date(data.snapshot_at).toLocaleString(FA)})
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DecisionBadge decision={data.score.decision} />
          <span className="text-xs text-zinc-500">امتیاز:</span>
          <span className="text-sm font-bold text-zinc-200 tabular-nums">{data.score.total}/100</span>
        </div>
      </header>

      {/* Summary tiles */}
      <CoinsSummary snap={data} />

      {/* Toolbar */}
      <section className="flex flex-wrap items-center gap-2 bg-zinc-900/40 ring-1 ring-zinc-800/60 rounded-xl p-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-zinc-500 absolute right-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجو در نام یا نماد..."
            className="w-full bg-zinc-950/60 border border-zinc-800/60 rounded-lg pr-9 pl-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-amber-500/40"
          />
        </div>

        <div className="flex items-center gap-1 text-xs">
          <Filter className="w-4 h-4 text-zinc-500" />
          {(["all", "low", "mid", "high"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setBubbleFilter(f)}
              className={`px-2.5 py-1 rounded-md transition ${
                bubbleFilter === f ? "bg-amber-500/20 text-amber-300" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {f === "all" ? "همه" : f === "low" ? "بدون حباب" : f === "mid" ? "متوسط" : "شدید"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 text-xs">
          <ArrowDownUp className="w-4 h-4 text-zinc-500" />
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="bg-zinc-950/60 border border-zinc-800/60 rounded-md px-2 py-1 text-zinc-200"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>مرتب‌سازی: {o.label}</option>
            ))}
          </select>
          <button
            onClick={() => setSortDesc((d) => !d)}
            className="px-2 py-1 rounded-md text-zinc-400 hover:text-zinc-200"
            title="معکوس"
          >
            {sortDesc ? "↓" : "↑"}
          </button>
        </div>

        <div className="flex items-center gap-1 text-xs">
          {(["cards", "table"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2.5 py-1 rounded-md ${
                view === v ? "bg-amber-500/20 text-amber-300" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {v === "cards" ? "کارت" : "جدول"}
            </button>
          ))}
        </div>
      </section>

      {/* Content */}
      {view === "cards" ? (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {rows.map((a) => <CoinBigCard key={a.symbol} a={a} />)}
          {rows.length === 0 && (
            <div className="col-span-full text-center text-zinc-500 text-sm py-12">
              موردی با این فیلتر یافت نشد.
            </div>
          )}
        </section>
      ) : (
        <CoinsTable rows={rows} />
      )}
    </div>
  );
}