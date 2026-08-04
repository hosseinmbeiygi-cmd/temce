"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, Cell, ReferenceLine, Area, AreaChart,
} from "recharts";
import { Card } from "@/components/ui/Card";
import ChartContainer from "@/components/charts/ChartContainer";
import EquityCurveChart from "@/components/charts/EquityCurveChart";
import DrawdownChart from "@/components/charts/DrawdownChart";

// ── Types ──────────────────────────────────────────────────────────────

export interface BacktestResultData {
  equity_curve?: { timestamp: string; nav: number }[];
  trades?: { instrument_id?: string; side?: string; quantity?: number; price?: number; pnl?: number }[];
  metrics?: Record<string, number>;
  initial_capital?: number;
  final_value?: number;
  total_return_pct?: number;
  annualized_return_pct?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  max_drawdown_pct?: number;
  win_rate?: number;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  profit_factor?: number;
  value_at_risk_95?: number;
  cvar_95?: number;
  benchmark_return_pct?: number;
  alpha?: number;
  beta?: number;
  up_capture?: number;
  down_capture?: number;
  name?: string;
  completed_at?: string;
}

interface BacktestResultsDashboardProps {
  result: BacktestResultData;
}

// ── Helpers ─────────────────────────────────────────────────────────────

function fmt(val: number | undefined | null, decimals = 2): string {
  if (val == null || isNaN(val)) return "—";
  return val.toFixed(decimals);
}

function pct(val: number | undefined | null): string {
  if (val == null || isNaN(val)) return "—";
  return (val >= 0 ? "+" : "") + val.toFixed(2) + "%";
}

function colorFor(val: number | undefined | null, higherIsBetter = true): string {
  if (val == null || isNaN(val)) return "text-surface-400";
  if (higherIsBetter) return val >= 0 ? "text-accent-emerald" : "text-accent-rose";
  return val <= 0 ? "text-accent-emerald" : "text-accent-rose";
}

function formatRials(v: number) {
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + "T";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + "B";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  return v.toLocaleString("fa-IR");
}

// ── Metric Card ─────────────────────────────────────────────────────────

function MetricCard({ icon, label, value, color, subtitle, tooltip }: {
  icon: string; label: string; value: string; color?: string; subtitle?: string; tooltip?: string;
}) {
  return (
    <div className="glass-card p-3 text-center hover:scale-[1.02] transition-transform duration-200 group relative">
      <p className={`text-lg font-black font-mono ${color || "text-surface-100"}`}>{value}</p>
      <p className="text-[9px] text-surface-500 mt-0.5">{icon} {label}</p>
      {subtitle && <p className="text-[8px] text-surface-600 mt-0.5">{subtitle}</p>}
      {tooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
          <div className="bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 shadow-2xl text-[10px] text-surface-400 text-right">
            {tooltip}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Monthly Returns Heatmap ────────────────────────────────────────────

function MonthlyReturnsHeatmap({ equityCurve }: { equityCurve: { timestamp: string; nav: number }[] }) {
  const monthlyData = useMemo(() => {
    if (!equityCurve || equityCurve.length < 2) return [];
    
    // Group by year-month
    const monthly: Record<string, { firstNav: number; lastNav: number; count: number }> = {};
    
    // First, find first and last nav per month
    for (let i = 0; i < equityCurve.length; i++) {
      const ep = equityCurve[i];
      const date = ep.timestamp?.slice(0, 7) || "unknown";
      if (!monthly[date]) {
        monthly[date] = { firstNav: ep.nav, lastNav: ep.nav, count: 1 };
      } else {
        monthly[date].lastNav = ep.nav;
        monthly[date].count++;
      }
    }
    
    return Object.entries(monthly)
      .filter(([, v]) => v.firstNav > 0)
      .map(([key, val]) => ({
        month: key,
        return: ((val.lastNav - val.firstNav) / val.firstNav) * 100,
        days: val.count,
      }))
      .sort((a, b) => a.month.localeCompare(b.month));
  }, [equityCurve]);

  if (monthlyData.length < 2) return null;

  // Organize by year
  const byYear: Record<string, { month: string; shortMonth: string; return: number; days: number }[]> = {};
  for (const d of monthlyData) {
    const year = d.month.slice(0, 4);
    if (!byYear[year]) byYear[year] = [];
    const monthNum = d.month.slice(5, 7);
    const monthNames = ["ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"];
    const shortMonthNames = ["ژان", "فور", "مار", "آور", "مه", "ژوئن", "ژوئیه", "اوت", "سپ", "اکت", "نوام", "دس"];
    byYear[year].push({
      ...d,
      shortMonth: shortMonthNames[parseInt(monthNum) - 1] || monthNum,
      month: monthNames[parseInt(monthNum) - 1] || monthNum,
    });
  }

  const maxAbs = Math.max(...monthlyData.map(d => Math.abs(d.return)), 1);

  return (
    <Card title="📅 بازده ماهانه" subtitle="بازده هر ماه به درصد">
      <div className="overflow-x-auto">
        <div className="flex gap-4 min-w-[300px]">
          {Object.entries(byYear).map(([year, months]) => (
            <div key={year}>
              <p className="text-[10px] font-bold text-surface-400 mb-2 text-center">{year}</p>
              <div className="grid grid-cols-1 gap-1">
                {months.map(m => {
                  const intensity = Math.abs(m.return) / maxAbs;
                  const isPositive = m.return >= 0;
                  const r = isPositive ? 0 : 239;
                  const g = isPositive ? Math.round(180 - intensity * 130) : Math.round(68 - intensity * 40);
                  const b = isPositive ? Math.round(80 - intensity * 50) : Math.round(68 - intensity * 40);
                  const bg = `rgb(${r}, ${g}, ${b})`;
                  return (
                    <div
                      key={m.month}
                      className="relative group px-3 py-2 rounded-lg text-center cursor-default min-w-[70px] transition-transform hover:scale-105"
                      style={{ backgroundColor: bg, opacity: 0.3 + intensity * 0.7 }}
                    >
                      <p className="text-[9px] text-surface-400">{m.shortMonth}</p>
                      <p className={`text-xs font-black font-mono ${isPositive ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {m.return >= 0 ? "+" : ""}{m.return.toFixed(1)}%
                      </p>
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                        <div className="bg-surface-900 border border-surface-700 rounded-xl px-3 py-2 shadow-2xl text-[10px] text-surface-200 whitespace-nowrap">
                          {m.month} {year}: {m.return.toFixed(2)}% ({m.days} روز)
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ── Trade Distribution (PNL Histogram) ─────────────────────────────────

function TradeDistribution({ trades }: { trades: { pnl?: number }[] }) {
  const histogram = useMemo(() => {
    if (!trades || trades.length < 2) return [];
    const pnls = trades.map(t => t.pnl ?? 0).filter(p => !isNaN(p));
    if (pnls.length < 2) return [];
    
    const maxAbs = Math.max(Math.abs(Math.min(...pnls)), Math.abs(Math.max(...pnls)), 1);
    const bins = 20;
    const step = (maxAbs * 2) / bins;
    const bucket: Record<string, { range: string; count: number; positive: boolean; avg: number }> = {};
    
    for (let i = 0; i < bins; i++) {
      const low = -maxAbs + i * step;
      const high = low + step;
      const key = `${low.toFixed(0)}-${high.toFixed(0)}`;
      bucket[key] = { range: key, count: 0, positive: low >= 0, avg: (low + high) / 2 };
    }
    
    for (const p of pnls) {
      const idx = Math.min(Math.floor((p + maxAbs) / step), bins - 1);
      const k = Object.keys(bucket)[idx];
      if (k && bucket[k]) bucket[k].count++;
    }
    
    return Object.values(bucket);
  }, [trades]);

  if (histogram.length < 2) return null;

  return (
    <Card title="📊 توزیع سود/زیان معاملات" subtitle={`${trades.length} معامله`}>
      <ChartContainer height={180}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={histogram} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.1)" vertical={false} />
            <XAxis
              dataKey="range"
              hide
              tick={{ fontSize: 8, fill: "#64748b" }}
            />
            <YAxis hide />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
                    style={{ background: "rgba(15, 23, 42, 0.96)", border: "1px solid rgba(71, 85, 105, 0.5)" }}>
                    <p className="font-bold text-surface-200 mb-1">سود/زیان: {d.avg.toFixed(0)} ریال</p>
                    <p className="text-surface-400">{d.count} معامله</p>
                  </div>
                );
              }}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]} maxBarSize={20}>
              {histogram.map((entry, idx) => (
                <Cell key={idx} fill={entry.positive ? "rgba(34,197,94,0.7)" : "rgba(239,68,68,0.7)"} />
              ))}
            </Bar>
            <ReferenceLine y={0} stroke="rgba(148,163,184,0.2)" />
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}

// ── Rolling Sharpe (simulated from equity curve) ───────────────────────

function RollingSharpe({ equityCurve }: { equityCurve: { timestamp: string; nav: number }[] }) {
  const rollingData = useMemo(() => {
    if (!equityCurve || equityCurve.length < 60) return [];
    const window = 63; // ~3 trading months
    
    const data: { index: number; sharpe: number; date: string }[] = [];
    for (let i = window; i < equityCurve.length; i++) {
      const returns = [];
      for (let j = i - window + 1; j <= i; j++) {
        const prev = equityCurve[j - 1]?.nav || 1;
        const curr = equityCurve[j]?.nav || 1;
        returns.push((curr - prev) / prev);
      }
      const mean = returns.reduce((s, v) => s + v, 0) / returns.length;
      const variance = returns.reduce((s, v) => s + (v - mean) ** 2, 0) / returns.length;
      const std = Math.sqrt(variance);
      const sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0;
      
      data.push({
        index: i,
        sharpe,
        date: equityCurve[i]?.timestamp?.slice(0, 10) || "",
      });
    }
    return data;
  }, [equityCurve]);

  if (rollingData.length < 5) return null;

  const maxSharpe = Math.max(...rollingData.map(d => Math.abs(d.sharpe)), 0.1);

  return (
    <Card title="🔄 Rolling Sharpe (۳ ماهه)" subtitle="شارپ گردان در پنجره ۶۳ روزه">
      <ChartContainer height={180}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rollingData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="sharpeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 4" stroke="rgba(100,116,139,0.12)" vertical={false} />
            <XAxis dataKey="index" hide />
            <YAxis
              stroke="#64748b"
              fontSize={9}
              tickFormatter={v => v.toFixed(1)}
              width={35}
              domain={[-(maxSharpe * 0.5), maxSharpe]}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)" }}
            />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
                    style={{ background: "rgba(15, 23, 42, 0.96)", border: "1px solid rgba(71, 85, 105, 0.5)" }}>
                    <p className="text-surface-500 text-[10px]">{d.date}</p>
                    <p className={`font-bold font-mono mt-1 ${d.sharpe >= 1 ? "text-accent-emerald" : d.sharpe >= 0 ? "text-accent-amber" : "text-accent-rose"}`}>
                      Sharpe: {d.sharpe.toFixed(2)}
                    </p>
                  </div>
                );
              }}
              cursor={{ stroke: "rgba(148,163,184,0.3)", strokeDasharray: "3 3", strokeWidth: 1 }}
            />
            <ReferenceLine y={0} stroke="rgba(148,163,184,0.25)" strokeDasharray="3 3" />
            <ReferenceLine y={1} stroke="rgba(34,197,94,0.2)" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="sharpe"
              stroke="#a78bfa"
              strokeWidth={2}
              fill="url(#sharpeGrad)"
              dot={false}
              activeDot={{ r: 4, fill: "#a78bfa", stroke: "rgba(15,23,42,0.9)", strokeWidth: 2 }}
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}

// ── Cumulative Returns Distribution ────────────────────────────────────

function CumulativeReturns({ equityCurve }: { equityCurve: { timestamp: string; nav: number }[] }) {
  const returnsData = useMemo(() => {
    if (!equityCurve || equityCurve.length < 5) return [];
    const data = [];
    for (let i = 1; i < equityCurve.length; i += Math.max(1, Math.floor(equityCurve.length / 30))) {
      const prev = equityCurve[i - 1]?.nav || 1;
      const curr = equityCurve[i]?.nav || 1;
      data.push({
        index: i,
        return: ((curr - prev) / prev) * 100,
      });
    }
    return data;
  }, [equityCurve]);

  if (returnsData.length < 5) return null;

  return (
    <Card title="📈 بازده روزانه" subtitle={`${returnsData.length} روز نمونه`}>
      <ChartContainer height={160}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={returnsData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.1)" vertical={false} />
            <XAxis dataKey="index" hide />
            <YAxis
              stroke="#64748b"
              fontSize={9}
              tickFormatter={v => `${v.toFixed(1)}%`}
              width={45}
              tickLine={false}
              axisLine={{ stroke: "rgba(100, 116, 139, 0.15)" }}
            />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-xl px-4 py-3 shadow-2xl text-xs border backdrop-blur-xl"
                    style={{ background: "rgba(15, 23, 42, 0.96)", border: "1px solid rgba(71, 85, 105, 0.5)" }}>
                    <p className={`font-bold font-mono ${d.return >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {d.return >= 0 ? "+" : ""}{d.return.toFixed(2)}%
                    </p>
                  </div>
                );
              }}
            />
            <ReferenceLine y={0} stroke="rgba(148,163,184,0.2)" />
            <Bar dataKey="return" radius={[2, 2, 0, 0]} maxBarSize={8}>
              {returnsData.map((entry, idx) => (
                <Cell key={idx} fill={entry.return >= 0 ? "rgba(34,197,94,0.7)" : "rgba(239,68,68,0.7)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </Card>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────

export default function BacktestResultsDashboard({ result }: BacktestResultsDashboardProps) {
  // Stable references so downstream useMemo hooks don't re-run every render
  // (result.equity_curve || [] creates a fresh array on each render otherwise).
  const equityCurve = useMemo(() => result.equity_curve || [], [result]);
  const trades = useMemo(() => result.trades || [], [result]);

  // Convert equity curve to positions format for EquityCurveChart
  const positionsData = useMemo(() => {
    if (!equityCurve.length) return [];
    return equityCurve.map(ep => ({ market_value: ep.nav }));
  }, [equityCurve]);

  // Convert to drawdown format
  const drawdownData = useMemo(() => {
    if (!equityCurve.length) return [];
    let peak = equityCurve[0]?.nav || 1;
    return equityCurve.map((ep, i) => {
      if (ep.nav > peak) peak = ep.nav;
      const dd = peak > 0 ? ((ep.nav - peak) / peak) * 100 : 0;
      return { index: i, drawdown: dd, date: ep.timestamp?.slice(0, 10) };
    });
  }, [equityCurve]);

  // Compute derived metrics
  const derivedMetrics = useMemo(() => {
    const d = result;
    const winPct = d.win_rate != null ? d.win_rate : (d.winning_trades != null && d.total_trades != null && d.total_trades > 0
      ? (d.winning_trades / d.total_trades) * 100 : 0);
    const profitFactor = d.profit_factor;
    
    return { winPct, profitFactor };
  }, [result]);

  // Risk metrics for display
  const riskMetrics = [
    { icon: "📈", label: "بازده کل", value: pct(result.total_return_pct), color: colorFor(result.total_return_pct), 
      tooltip: "درصد بازده کل سرمایه در طول دوره بک‌تست" },
    { icon: "📊", label: "بازده سالانه", value: pct(result.annualized_return_pct), color: colorFor(result.annualized_return_pct),
      tooltip: "بازده سالانه شده بر اساس CAGR" },
    { icon: "🎯", label: "نسبت شارپ", value: fmt(result.sharpe_ratio), color: result.sharpe_ratio != null && result.sharpe_ratio >= 1 ? "text-accent-emerald" : result.sharpe_ratio != null && result.sharpe_ratio >= 0 ? "text-accent-amber" : "text-accent-rose",
      tooltip: "بازده اضافی به ازای هر واحد ریسک. >۱ عالی، ۰.۵-۱ خوب، <۰.۵ ضعیف" },
    { icon: "🛡️", label: "نسبت سورتینو", value: fmt(result.sortino_ratio), color: result.sortino_ratio != null && result.sortino_ratio >= 1 ? "text-accent-emerald" : "text-accent-amber",
      tooltip: "مشابه شارپ اما فقط ریسک نزولی را در نظر می‌گیرد" },
    { icon: "📉", label: "حداکثر Drawdown", value: fmt(result.max_drawdown_pct) + "%", color: colorFor(result.max_drawdown_pct, false),
      tooltip: "بیشترین افت سرمایه از اوج تا کف" },
    { icon: "⚖️", label: "نسبت کالمار", value: fmt(result.calmar_ratio), color: result.calmar_ratio != null && result.calmar_ratio >= 1 ? "text-accent-emerald" : "text-accent-amber",
      tooltip: "نسبت بازده سالانه به حداکثر Drawdown" },
    { icon: "✅", label: "Win Rate", value: fmt(derivedMetrics.winPct) + "%", color: derivedMetrics.winPct >= 50 ? "text-accent-emerald" : "text-accent-rose",
      tooltip: "درصد معاملات برنده" },
    { icon: "💹", label: "Profit Factor", value: derivedMetrics.profitFactor != null ? fmt(derivedMetrics.profitFactor) : "—", 
      color: derivedMetrics.profitFactor != null && derivedMetrics.profitFactor >= 2 ? "text-accent-emerald" : derivedMetrics.profitFactor != null && derivedMetrics.profitFactor >= 1 ? "text-accent-amber" : "text-accent-rose",
      tooltip: "نسبت سود کل به زیان کل. >۲ عالی، >۱ سودده" },
    { icon: "🔄", label: "معاملات", value: String(result.total_trades ?? 0), color: "text-surface-100",
      subtitle: `${result.winning_trades ?? 0} برد / ${result.losing_trades ?? 0} باخت`,
      tooltip: "تعداد کل معاملات انجام شده" },
    { icon: "🔵", label: "VaR (۹۵%)", value: result.value_at_risk_95 != null ? fmt(result.value_at_risk_95) + "%" : "—",
      color: result.value_at_risk_95 != null && result.value_at_risk_95 > -5 ? "text-accent-emerald" : "text-accent-rose",
      tooltip: "Value at Risk 95%: حداکثر ضرر مورد انتظار در ۹۵٪ موارد" },
    { icon: "🔴", label: "CVaR (۹۵%)", value: result.cvar_95 != null ? fmt(result.cvar_95) + "%" : "—",
      color: result.cvar_95 != null && result.cvar_95 > -8 ? "text-accent-emerald" : "text-accent-rose",
      tooltip: "Conditional VaR: میانگین ضرر در بدترین ۵٪ موارد" },
    { icon: "💰", label: "سرمایه نهایی", value: formatRials(result.final_value ?? 0), color: (result.final_value ?? 0) >= (result.initial_capital ?? 0) ? "text-accent-emerald" : "text-accent-rose",
      subtitle: `اولیه: ${formatRials(result.initial_capital ?? 0)}`,
      tooltip: "ارزش نهایی پرتفوی در پایان دوره" },
  ];

  // Alpha/Beta section
  const hasBenchmark = result.benchmark_return_pct != null;

  return (
    <div className="space-y-5">
      {/* ── Risk Metrics Grid ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {riskMetrics.map((m, i) => (
          <MetricCard key={i} {...m} />
        ))}
      </div>

      {/* ── Alpha/Beta (if benchmark exists) ── */}
      {hasBenchmark && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <MetricCard icon="📊" label="بازده بنچمارک" value={pct(result.benchmark_return_pct)} color={colorFor(result.benchmark_return_pct)} />
          <MetricCard icon="📈" label="آلفا" value={fmt(result.alpha)} color={result.alpha != null && result.alpha >= 0 ? "text-accent-emerald" : "text-accent-rose"}
            tooltip="بازده اضافی نسبت به بنچمارک" />
          <MetricCard icon="📉" label="بتا" value={fmt(result.beta)} color={result.beta != null && result.beta < 1.2 ? "text-accent-emerald" : "text-accent-amber"}
            tooltip="حساسیت به بازار. <۱ کمریسک، >۱ پُرریسک" />
          <MetricCard icon="🔼" label="Up Capture" value={fmt(result.up_capture)} color="text-accent-emerald"
            tooltip="درصد مشارکت در بازارهای صعودی" />
          <MetricCard icon="🔽" label="Down Capture" value={fmt(result.down_capture)} color={result.down_capture != null && result.down_capture < 100 ? "text-accent-emerald" : "text-accent-rose"}
            tooltip="درصد مشارکت در بازارهای نزولی" />
        </div>
      )}

      {/* ── Main Charts Row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Equity Curve */}
        <Card title="📈 منحنی سرمایه" subtitle={`${equityCurve.length} روز معاملاتی`}>
          {positionsData.length >= 2 ? (
            <EquityCurveChart positions={positionsData} height={280} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-surface-500 text-sm">
              داده کافی برای نمایش منحنی سرمایه وجود ندارد
            </div>
          )}
        </Card>

        {/* Drawdown */}
        <Card title="📉 نمودار Drawdown" subtitle={`حداکثر: ${fmt(result.max_drawdown_pct)}%`}>
          {drawdownData.length >= 2 ? (
            <DrawdownChart data={drawdownData} height={280} />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-surface-500 text-sm">
              داده کافی برای نمایش Drawdown وجود ندارد
            </div>
          )}
        </Card>
      </div>

      {/* ── Secondary Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <MonthlyReturnsHeatmap equityCurve={equityCurve} />
        <RollingSharpe equityCurve={equityCurve} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <TradeDistribution trades={trades} />
        <CumulativeReturns equityCurve={equityCurve} />
      </div>

      {/* ── Trades Table Summary ── */}
      {trades.length > 0 && (
        <Card title="📋 خلاصه معاملات" subtitle={`${trades.length} معامله`}>
          <div className="overflow-x-auto max-h-[250px] overflow-y-auto">
            <table className="w-full text-right text-[10px]">
              <thead className="sticky top-0 bg-surface-900">
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 px-2">#</th>
                  <th className="pb-2 px-2">سمت</th>
                  <th className="pb-2 px-2 text-center">تعداد</th>
                  <th className="pb-2 px-2 text-center font-mono">قیمت</th>
                  <th className="pb-2 px-2 text-center font-mono">سود/زیان</th>
                </tr>
              </thead>
              <tbody>
                {trades.slice(-50).reverse().map((t, i) => {
                  const pnl = t.pnl ?? 0;
                  return (
                    <tr key={i} className="border-b border-surface-800/30 hover:bg-white/5 transition-colors">
                      <td className="py-1.5 px-2 text-surface-500">{trades.length - i}</td>
                      <td className="py-1.5 px-2">
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          t.side === "buy" || t.side === "long" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                        }`}>
                          {t.side === "buy" || t.side === "long" ? "خرید" : "فروش"}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-center font-mono text-surface-300">{t.quantity ?? "—"}</td>
                      <td className="py-1.5 px-2 text-center font-mono text-surface-300">{t.price?.toLocaleString("fa-IR") ?? "—"}</td>
                      <td className={`py-1.5 px-2 text-center font-mono ${pnl >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {pnl >= 0 ? "+" : ""}{formatRials(Math.abs(Math.round(pnl)))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
