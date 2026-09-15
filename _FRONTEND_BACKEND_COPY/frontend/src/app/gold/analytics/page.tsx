"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getScoreHistory, getSnapshotHistory } from "@/lib/goldApi";

const SYMBOLS = [
  { value: "IR_COIN_EMAMI", label: "سکه امامی", color: "#f59e0b" },
  { value: "IR_COIN_HALF", label: "نیم سکه", color: "#84cc16" },
  { value: "IR_COIN_QUARTER", label: "ربع سکه", color: "#10b981" },
  { value: "IR_GOLD_18K", label: "طلای ۱۸ عیار", color: "#3b82f6" },
];

export default function GoldAnalyticsPage() {
  const [days, setDays] = useState(7);
  const [compareSymbols, setCompareSymbols] = useState<string[]>(["IR_COIN_EMAMI"]);

  const { data: scoreHist } = useQuery({
    queryKey: ["gold", "analytics", "score", days],
    queryFn: () => getScoreHistory(days),
    refetchInterval: 60_000,
  });

  const toggleSymbol = (sym: string) => {
    setCompareSymbols((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym],
    );
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-zinc-100">📊 تحلیل تاریخی</h2>
        <div className="flex gap-1">
          {[1, 7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg transition ${
                days === d
                  ? "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40"
                  : "bg-zinc-800/60 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {d} روز
            </button>
          ))}
        </div>
      </div>

      {/* Score over time */}
      <section className="rounded-2xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-6">
        <h3 className="text-sm font-semibold text-zinc-300 mb-3">نمودار امتیاز در زمان</h3>
        <ScoreChart points={scoreHist?.data?.items ?? []} />
      </section>

      {/* Compare assets */}
      <section className="rounded-2xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-6">
        <h3 className="text-sm font-semibold text-zinc-300 mb-3">مقایسه حباب دارایی‌ها</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {SYMBOLS.map((s) => {
            const active = compareSymbols.includes(s.value);
            return (
              <button
                key={s.value}
                onClick={() => toggleSymbol(s.value)}
                className={`text-xs px-3 py-1.5 rounded-lg transition flex items-center gap-2 ${
                  active ? "ring-1 ring-amber-500/40" : "ring-1 ring-zinc-800"
                }`}
                style={{
                  background: active ? `${s.color}20` : "rgba(39, 39, 42, 0.6)",
                  color: active ? s.color : "#a1a1aa",
                }}
              >
                <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                {s.label}
              </button>
            );
          })}
        </div>
        <div className="space-y-3">
          {compareSymbols.map((sym) => (
            <AssetBubbleChart key={sym} symbol={sym} days={days} color={SYMBOLS.find((s) => s.value === sym)?.color || "#f59e0b"} />
          ))}
        </div>
      </section>

      {/* Hot/Cold map */}
      <section className="rounded-2xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-6">
        <h3 className="text-sm font-semibold text-zinc-300 mb-3">نقشه داغ/سرد صندوق‌ها</h3>
        <FundsHeatmap />
      </section>
    </div>
  );
}

function ScoreChart({ points }: { points: Array<{ score_at: string; total: number; decision: string; hard_stop_active: boolean }> }) {
  if (points.length < 2) {
    return <div className="text-zinc-500 text-sm text-center py-8">داده کافی نیست (حداقل ۲ نقطه لازم است)</div>;
  }

  const w = 1200;
  const h = 280;
  const padX = 40;
  const padY = 30;

  // band regions
  const greenY = h - padY - (80 / 100) * (h - 2 * padY);
  const yellowY = h - padY - (55 / 100) * (h - 2 * padY);
  const redY = h - padY - 0;

  const x = (i: number) => padX + (i / (points.length - 1)) * (w - 2 * padX);
  const y = (v: number) => h - padY - (Math.max(0, Math.min(100, v)) / 100) * (h - 2 * padY);

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.total)}`).join(" ");

  // color per point
  const dots = points.map((p, i) => {
    const color = p.decision === "GREEN" ? "#10b981" : p.decision === "YELLOW" ? "#f59e0b" : "#f43f5e";
    return <circle key={i} cx={x(i)} cy={y(p.total)} r="3.5" fill={color} />;
  });

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Decision bands */}
        <rect x={padX} y={padY} width={w - 2 * padX} height={greenY - padY} fill="#10b981" fillOpacity="0.05" />
        <rect x={padX} y={greenY} width={w - 2 * padX} height={yellowY - greenY} fill="#f59e0b" fillOpacity="0.05" />
        <rect x={padX} y={yellowY} width={w - 2 * padX} height={redY - yellowY} fill="#f43f5e" fillOpacity="0.05" />

        {/* Grid + labels */}
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line
              x1={padX}
              x2={w - padX}
              y1={y(v)}
              y2={y(v)}
              stroke="#27272a"
              strokeWidth="0.5"
            />
            <text x={padX - 5} y={y(v) + 3} fill="#71717a" fontSize="10" textAnchor="end">
              {v}
            </text>
          </g>
        ))}

        {/* Line */}
        <path d={path} fill="none" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" />

        {/* Dots */}
        {dots}

        {/* Time labels */}
        <text x={padX} y={h - 6} fill="#71717a" fontSize="10">
          {new Date(points[0].score_at).toLocaleString("fa-IR", { month: "2-digit", day: "2-digit", hour: "2-digit" })}
        </text>
        <text x={w - padX} y={h - 6} fill="#71717a" fontSize="10" textAnchor="end">
          {new Date(points[points.length - 1].score_at).toLocaleString("fa-IR", { month: "2-digit", day: "2-digit", hour: "2-digit" })}
        </text>
      </svg>
    </div>
  );
}

function AssetBubbleChart({ symbol, days, color }: { symbol: string; days: number; color: string }) {
  const { data: hist } = useQuery({
    queryKey: ["gold", "analytics", "bubble", symbol, days],
    queryFn: () => getSnapshotHistory(symbol, days),
    refetchInterval: 60_000,
  });

  const points = (hist?.data?.items ?? []).map((p) => ({
    date: (p.snapshot_at || "").slice(0, 16).replace("T", " "),
    value: p.bubble_pct ?? 0,
  }));

  if (points.length < 2) {
    return <div className="text-xs text-zinc-500">{symbol}: داده کافی نیست</div>;
  }

  const w = 1200;
  const h = 120;
  const padX = 30;
  const padY = 15;
  const values = points.map((p) => p.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const range = max - min || 1;
  const x = (i: number) => padX + (i / (points.length - 1)) * (w - 2 * padX);
  const y = (v: number) => h - padY - ((v - min) / range) * (h - 2 * padY);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.value)}`).join(" ");
  const area = `${path} L ${x(points.length - 1)} ${h - padY} L ${x(0)} ${h - padY} Z`;

  return (
    <div>
      <div className="text-xs text-zinc-400 mb-1">
        حباب امروز: <span className="font-mono text-zinc-100">{points[points.length - 1].value.toFixed(2)}٪</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id={`grad-${symbol}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#grad-${symbol})`} />
        <path d={path} fill="none" stroke={color} strokeWidth="2" />
      </svg>
    </div>
  );
}

function FundsHeatmap() {
  const { data: snap } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: async () => (await import("@/lib/goldApi")).getSnapshot(),
    refetchInterval: 60_000,
  });

  if (!snap) return <div className="text-zinc-500 text-sm">در حال بارگذاری...</div>;
  if (snap.funds.length === 0) {
    return <div className="text-zinc-500 text-sm text-center py-4">صندوقی موجود نیست</div>;
  }

  // محاسبه heat: bubble + BPR
  const funds = snap.funds.map((f) => {
    let heat: "hot" | "warm" | "cold" = "cold";
    if (f.bubble_pct > 3 || f.bpr < 1) heat = "hot"; // اشباع خرید یا فروش
    else if (f.bubble_pct > 1.5 || f.bpr < 1.5) heat = "warm";
    return { ...f, heat };
  });

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
      {funds.map((f) => {
        const colors = {
          hot: "from-rose-500/30 to-rose-600/10 ring-rose-500/40 text-rose-200",
          warm: "from-amber-500/30 to-amber-600/10 ring-amber-500/40 text-amber-200",
          cold: "from-emerald-500/30 to-emerald-600/10 ring-emerald-500/40 text-emerald-200",
        }[f.heat];
        const label = { hot: "پرریسک", warm: "محتاط", cold: "فرصت" }[f.heat];
        return (
          <div key={f.symbol} className={`rounded-lg bg-gradient-to-br ${colors} ring-1 p-3 text-center`}>
            <div className="text-xs font-semibold mb-1">{f.fund_name}</div>
            <div className="text-2xl font-bold tabular-nums">{f.bubble_pct.toFixed(1)}٪</div>
            <div className="text-[10px] opacity-70 mt-1">{label}</div>
            <div className="text-[10px] opacity-60 mt-0.5">BPR {f.bpr.toFixed(2)}</div>
          </div>
        );
      })}
    </div>
  );
}
