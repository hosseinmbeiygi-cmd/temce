"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface ProfileStats {
  total_profiles: number;
  with_eps: number;
  with_profit: number;
  with_margin: number;
  with_loss: number;
  with_capital: number;
  avg_eps: number;
  avg_gross_margin: number;
}

interface SignalStats {
  total_signals: number;
  buy_count: number;
  dont_buy_count: number;
  risk_reject_count: number;
  score_reject_count: number;
  avg_final_score: number;
  max_final_score: number;
  correct_outcomes: number;
  tracked_outcomes: number;
}

interface ScoreBucket {
  bucket: string;
  cnt: number;
}

interface RecentSignal {
  symbol: string;
  final_score: number;
  decision: string;
  current_price: number;
  stop_loss_price: number;
  generated_at: string;
  score_fundamental: number;
  score_valuation: number;
  score_institutional: number;
  score_technical: number;
  score_macro: number;
}

interface IndustryStat {
  industry: string;
  cnt: number;
}

interface SystemStatus {
  last_populate: string | null;
  last_cycle: string | null;
  last_buy_signals: number;
  last_error: string | null;
}

interface MonitorData {
  profiles: ProfileStats;
  signals: SignalStats;
  score_distribution: ScoreBucket[];
  recent_signals: RecentSignal[];
  top_industries: IndustryStat[];
  system: SystemStatus;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmtNum(n: number): string {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString("fa-IR");
}

function fmtPct(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fa-IR", {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-accent-emerald";
  if (score >= 60) return "text-primary-300";
  if (score >= 40) return "text-accent-amber";
  if (score >= 20) return "text-accent-rose";
  return "text-surface-500";
}

function scoreBg(score: number): string {
  if (score >= 80) return "bg-accent-emerald/15";
  if (score >= 60) return "bg-primary-600/20";
  if (score >= 40) return "bg-accent-amber/15";
  if (score >= 20) return "bg-accent-rose/15";
  return "bg-surface-800/50";
}

function decisionBadge(dec: string): { label: string; cls: string } {
  switch (dec) {
    case "خرید": return { label: "BUY", cls: "bg-accent-emerald/15 text-accent-emerald" };
    case "نخرید": return { label: "NO", cls: "bg-surface-600/30 text-surface-400" };
    case "رد_ریسک": return { label: "RISK", cls: "bg-accent-rose/15 text-accent-rose" };
    case "رد_نمره": return { label: "SCORE", cls: "bg-accent-amber/15 text-accent-amber" };
    default: return { label: dec || "—", cls: "bg-surface-800/50 text-surface-500" };
  }
}

// ── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({ title, value, sub, accent = false }: {
  title: string; value: string; sub?: string; accent?: boolean;
}) {
  return (
    <div className={`glass-card p-4 ${accent ? "border-primary-500/30" : "border-surface-700/50"}`}>
      <div className="text-[10px] text-surface-500 mb-1 tracking-wide">{title}</div>
      <div className={`text-2xl font-black ${accent ? "text-primary-300" : "text-surface-100"}`}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-surface-600 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Score Bar ───────────────────────────────────────────────────────────────

function ScoreBar({ label, value, maxWidth = 120 }: { label: string; value: number; maxWidth?: number }) {
  const pct = Math.min(value, 100);
  return (
    <div className="flex items-center gap-2" style={{ maxWidth }}>
      <span className="text-[10px] text-surface-500 w-8 text-right shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${value >= 80 ? "bg-accent-emerald" : value >= 60 ? "bg-primary-500" : value >= 40 ? "bg-accent-amber" : "bg-accent-rose"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-surface-400 w-8 text-left">{pct.toFixed(0)}</span>
    </div>
  );
}

// ── Industry Badge ──────────────────────────────────────────────────────────

function IndustryBadge({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = (count / max) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-primary-500/60" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-surface-300 min-w-[80px] text-right">{name}</span>
      <span className="text-[10px] font-mono text-surface-500 w-6 text-left">{count}</span>
    </div>
  );
}

// ── Mini Donut ──────────────────────────────────────────────────────────────

function MiniDonut({ value, size = 40, stroke = 5 }: { value: number; size?: number; stroke?: number }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.min(value, 100) / 100);
  const color = value >= 80 ? "#10b981" : value >= 60 ? "#818cf8" : value >= 40 ? "#f59e0b" : "#f43f5e";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e293b" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
    </svg>
  );
}

// ── Score Distribution Chart ────────────────────────────────────────────────

function ScoreDistChart({ data }: { data: ScoreBucket[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-surface-500 text-xs">
        No signals generated yet
      </div>
    );
  }
  const maxCnt = Math.max(...data.map(d => d.cnt), 1);
  const colors: Record<string, string> = {
    "80-100": "bg-accent-emerald", "60-80": "bg-primary-500",
    "40-60": "bg-accent-amber", "20-40": "bg-accent-rose/70",
    "0-20": "bg-surface-600", no_score: "bg-surface-800",
  };
  return (
    <div className="flex items-end gap-3 h-40 pt-4">
      {data.map(d => {
        const h = (d.cnt / maxCnt) * 100;
        return (
          <div key={d.bucket} className="flex-1 flex flex-col items-center gap-1">
            <span className="text-[9px] font-mono text-surface-400">{d.cnt}</span>
            <div className="w-full rounded-t-md relative group" style={{ height: `${Math.max(h, 4)}%` }}>
              <div className={`absolute inset-0 rounded-t-md ${colors[d.bucket] || "bg-surface-700"} opacity-80 group-hover:opacity-100 transition-opacity`} />
            </div>
            <span className="text-[8px] text-surface-600">{d.bucket}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function Screener110MonitorPage() {
  const [refreshing, setRefreshing] = useState(false);

  const { data: raw, isLoading, error, refetch } = useQuery({
    queryKey: ["screener110-monitor"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: MonitorData }>("/screener110/monitor");
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const data = raw;

  const handleRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setTimeout(() => setRefreshing(false), 500);
  };

  // ── Accuracy calc ──
  const accuracy = useMemo(() => {
    if (!data?.signals) return null;
    const { correct_outcomes, tracked_outcomes } = data.signals;
    if (tracked_outcomes === 0) return null;
    return ((correct_outcomes / tracked_outcomes) * 100).toFixed(1);
  }, [data]);

  return (
    <AppLayout
      title="Screener110 — Monitoring Dashboard"
      subtitle="Manitoring and analytics for the 110-column CANSLIM screener model"
    >
      {/* ── Header actions ── */}
      <div className="flex items-center gap-3 mb-5">
        <button
          onClick={handleRefresh}
          disabled={isLoading || refreshing}
          className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-300 hover:bg-surface-700 hover:text-surface-100 transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <span className={`material-icons text-sm ${refreshing ? "animate-spin" : ""}`}>
            refresh
          </span>
          Refresh
        </button>
        <Link
          href="/screener"
          className="px-4 py-2 bg-surface-800 border border-surface-700 rounded-xl text-xs font-bold text-surface-300 hover:bg-surface-700 hover:text-surface-100 transition-all"
        >
          Smart Money Screener
        </Link>
        <span className="text-[10px] text-surface-600 mr-auto">
          Auto-refresh every 60s
        </span>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="glass-card h-24" />)}
          </div>
          <div className="glass-card h-48" />
          <div className="glass-card h-64" />
        </div>
      )}

      {/* ── Error ── */}
      {error && !isLoading && (
        <div className="glass-card p-8 text-center border border-accent-rose/30">
          <span className="material-icons text-4xl text-accent-rose mb-3 block">error_outline</span>
          <p className="text-sm text-accent-rose mb-1">Failed to load monitoring data</p>
          <p className="text-xs text-surface-500">Check API connection and try again.</p>
        </div>
      )}

      {!isLoading && !error && data && (
        <>
          {/* ═══════════════ SECTION 1: Profile Stats ═══════════════ */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-icons text-primary-400 text-lg">storage</span>
              <span className="text-sm font-bold text-surface-300">Screener Profiles</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard title="TOTAL PROFILES" value={data.profiles.total_profiles.toLocaleString("en-US")} sub="from symbols table" />
              <StatCard title="WITH EPS" value={data.profiles.with_eps.toLocaleString("en-US")} sub={data.profiles.total_profiles > 0 ? `${((data.profiles.with_eps / data.profiles.total_profiles) * 100).toFixed(0)}% coverage` : undefined} />
              <StatCard title="WITH NET PROFIT" value={fmtNum(data.profiles.with_profit)} sub={`avg: ${fmtNum(data.profiles.avg_eps)}`} accent />
              <StatCard title="WITH GROSS MARGIN" value={data.profiles.with_margin.toLocaleString("en-US")} sub={data.profiles.avg_gross_margin > 0 ? `avg: ${fmtPct(data.profiles.avg_gross_margin)}` : undefined} />
            </div>
            {/* Profile fill bars */}
            <div className="mt-3 glass-card p-4">
              <div className="text-xs font-bold text-surface-400 mb-3">Data Coverage</div>
              <div className="space-y-2">
                {[
                  { label: "EPS", val: data.profiles.with_eps / Math.max(data.profiles.total_profiles, 1) * 100 },
                  { label: "Net Profit", val: data.profiles.with_profit / Math.max(data.profiles.total_profiles, 1) * 100 },
                  { label: "Gross Margin", val: data.profiles.with_margin / Math.max(data.profiles.total_profiles, 1) * 100 },
                  { label: "Registered Capital", val: data.profiles.with_capital / Math.max(data.profiles.total_profiles, 1) * 100 },
                ].map(item => (
                  <div key={item.label} className="flex items-center gap-3">
                    <span className="text-[10px] text-surface-500 w-24 shrink-0">{item.label}</span>
                    <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${item.val >= 50 ? "bg-accent-emerald" : item.val >= 20 ? "bg-accent-amber" : "bg-surface-600"}`}
                        style={{ width: `${item.val}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-surface-400 w-10 text-right">{item.val.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ═══════════════ SECTION 2: Signals Stats ═══════════════ */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-icons text-accent-cyan text-lg">signal_cellular_alt</span>
              <span className="text-sm font-bold text-surface-300">Signals & Decisions</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard title="TOTAL SIGNALS" value={data.signals.total_signals.toLocaleString("en-US")} sub="generated by model" />
              <StatCard title="BUY SIGNALS" value={data.signals.buy_count.toLocaleString("en-US")} sub={data.signals.total_signals > 0 ? `${((data.signals.buy_count / Math.max(data.signals.total_signals, 1)) * 100).toFixed(0)}% of total` : undefined} accent />
              <StatCard title="AVG FINAL SCORE" value={data.signals.avg_final_score.toFixed(1)} sub={`max: ${data.signals.max_final_score.toFixed(1)}`} />
              <StatCard title="ACCURACY" value={accuracy ? `${accuracy}%` : "—"} sub={data.signals.tracked_outcomes > 0 ? `${data.signals.tracked_outcomes} tracked` : "no tracking yet"} />
            </div>

            {/* Score Distribution */}
            <div className="mt-3 glass-card p-4">
              <div className="text-xs font-bold text-surface-400 mb-3">Final Score Distribution</div>
              <ScoreDistChart data={data.score_distribution} />
            </div>
          </div>

          {/* ═══════════════ SECTION 3: Recent Signals ═══════════════ */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-icons text-accent-amber text-lg">history</span>
              <span className="text-sm font-bold text-surface-300">Recent Signals</span>
              <span className="text-[10px] text-surface-600 mr-auto">
                {data.recent_signals.length > 0 ? "Last 20 signals" : "No signals yet — run the model first"}
              </span>
            </div>

            {data.recent_signals.length === 0 ? (
              <div className="glass-card p-8 text-center">
                <span className="material-icons text-5xl text-surface-600 mb-2 block">signal_cellular_alt</span>
                <p className="text-sm text-surface-500">No signals have been generated yet</p>
                <p className="text-xs text-surface-600 mt-1">Execute a model cycle via POST /screener110/run-cycle</p>
              </div>
            ) : (
              <div className="glass-card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-surface-700/50">
                        <th className="text-right p-3 text-surface-500 font-bold">Symbol</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Score</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Decision</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Price</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Stop Loss</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Scores (F/V/I/T/M)</th>
                        <th className="text-right p-3 text-surface-500 font-bold">Generated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_signals.map((s, i) => {
                        const badge = decisionBadge(s.decision);
                        return (
                          <tr key={`${s.symbol}-${i}`} className="border-b border-surface-800/50 hover:bg-surface-800/30 transition-colors">
                            <td className="p-3">
                              <Link href={`/symbol/${encodeURIComponent(s.symbol)}`} className="font-bold text-surface-200 hover:text-primary-300 transition-colors">
                                {s.symbol}
                              </Link>
                            </td>
                            <td className="p-3">
                              <span className={`font-black font-mono ${scoreColor(s.final_score || 0)}`}>
                                {s.final_score?.toFixed(1) ?? "—"}
                              </span>
                            </td>
                            <td className="p-3">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${badge.cls}`}>
                                {badge.label}
                              </span>
                            </td>
                            <td className="p-3 font-mono text-surface-300">
                              {s.current_price?.toLocaleString("fa-IR") ?? "—"}
                            </td>
                            <td className="p-3 font-mono text-accent-rose">
                              {s.stop_loss_price?.toLocaleString("fa-IR") ?? "—"}
                            </td>
                            <td className="p-3">
                              <div className="flex gap-1 text-[9px]">
                                <span className={s.score_fundamental ? "text-accent-amber" : "text-surface-600"}>
                                  {s.score_fundamental?.toFixed(0) ?? "—"}
                                </span>
                                <span className="text-surface-600">/</span>
                                <span className={s.score_valuation ? "text-primary-300" : "text-surface-600"}>
                                  {s.score_valuation?.toFixed(0) ?? "—"}
                                </span>
                                <span className="text-surface-600">/</span>
                                <span className={s.score_institutional ? "text-accent-emerald" : "text-surface-600"}>
                                  {s.score_institutional?.toFixed(0) ?? "—"}
                                </span>
                                <span className="text-surface-600">/</span>
                                <span className={s.score_technical ? "text-accent-cyan" : "text-surface-600"}>
                                  {s.score_technical?.toFixed(0) ?? "—"}
                                </span>
                                <span className="text-surface-600">/</span>
                                <span className={s.score_macro ? "text-accent-rose" : "text-surface-600"}>
                                  {s.score_macro?.toFixed(0) ?? "—"}
                                </span>
                              </div>
                            </td>
                            <td className="p-3 text-surface-500 text-[9px] whitespace-nowrap">
                              {fmtDate(s.generated_at)}
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

          {/* ═══════════════ SECTION 4: System Status ═══════════════ */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-icons text-surface-500 text-lg">monitor_heart</span>
              <span className="text-sm font-bold text-surface-300">System Status</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="glass-card p-4 border border-surface-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-2 h-2 rounded-full ${data.system.last_populate ? "bg-accent-emerald" : "bg-surface-600"}`} />
                  <span className="text-[10px] text-surface-500 font-bold">Last Populate</span>
                </div>
                <div className="text-sm text-surface-200 font-mono">
                  {fmtDate(data.system.last_populate)}
                </div>
                {!data.system.last_populate && (
                  <div className="text-[10px] text-surface-600 mt-1">Never run</div>
                )}
              </div>
              <div className="glass-card p-4 border border-surface-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-2 h-2 rounded-full ${data.system.last_cycle ? "bg-accent-emerald" : "bg-surface-600"}`} />
                  <span className="text-[10px] text-surface-500 font-bold">Last Model Cycle</span>
                </div>
                <div className="text-sm text-surface-200 font-mono">
                  {fmtDate(data.system.last_cycle)}
                </div>
                {data.system.last_buy_signals > 0 && (
                  <div className="text-[10px] text-accent-emerald mt-1">
                    {data.system.last_buy_signals} buy signals
                  </div>
                )}
                {!data.system.last_cycle && (
                  <div className="text-[10px] text-surface-600 mt-1">Never run</div>
                )}
              </div>
              <div className="glass-card p-4 border border-surface-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-2 h-2 rounded-full ${data.system.last_error ? "bg-accent-rose" : "bg-accent-emerald"}`} />
                  <span className="text-[10px] text-surface-500 font-bold">Last Error</span>
                </div>
                {data.system.last_error ? (
                  <div className="text-xs text-accent-rose font-mono break-all">{data.system.last_error}</div>
                ) : (
                  <div className="text-sm text-surface-400">No errors</div>
                )}
              </div>
            </div>
          </div>

          {/* ═══════════════ SECTION 5: Top Industries ═══════════════ */}
          {data.top_industries.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <span className="material-icons text-surface-500 text-lg">domain</span>
                <span className="text-sm font-bold text-surface-300">Top Industries by Coverage</span>
              </div>
              <div className="glass-card p-4">
                <div className="space-y-2">
                  {data.top_industries.map(ind => (
                    <IndustryBadge key={ind.industry} name={ind.industry} count={ind.cnt} max={data.top_industries[0]?.cnt || 1} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════ SECTION 6: Quick Actions ═══════════════ */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-icons text-surface-500 text-lg">bolt</span>
              <span className="text-sm font-bold text-surface-300">Quick Actions</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Link href="/signals" className="glass-card p-4 border border-surface-700/50 hover:border-primary-500/30 transition-all group flex items-center gap-3">
                <span className="material-icons text-3xl text-primary-400 group-hover:text-primary-300">list_alt</span>
                <div>
                  <div className="text-sm font-bold text-surface-200 group-hover:text-surface-100">All Signals</div>
                  <div className="text-[10px] text-surface-500">View multi-market signals dashboard</div>
                </div>
                <span className="material-icons text-surface-600 mr-auto">arrow_back</span>
              </Link>
              <Link href="/screener" className="glass-card p-4 border border-surface-700/50 hover:border-accent-emerald/30 transition-all group flex items-center gap-3">
                <span className="material-icons text-3xl text-accent-emerald group-hover:text-accent-emerald/80">search</span>
                <div>
                  <div className="text-sm font-bold text-surface-200 group-hover:text-surface-100">Screener</div>
                  <div className="text-[10px] text-surface-500">Smart Money 5-phase stock screener</div>
                </div>
                <span className="material-icons text-surface-600 mr-auto">arrow_back</span>
              </Link>
            </div>
          </div>

          {/* ── Footer ── */}
          <div className="text-[10px] text-surface-600 text-center py-4 border-t border-surface-800/50">
            Screener110 Monitoring v1.0 — Data refreshes automatically every 60 seconds
          </div>
        </>
      )}
    </AppLayout>
  );
}
