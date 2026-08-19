"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────

interface PaperDashboard {
  initial_capital: number;
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  win_rate: number;
  wins: number;
  losses: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  equity: number;
  updated_at: string;
}

interface PaperTrade {
  id: string;
  signal_snapshot_id: string | null;
  symbol: string;
  name: string;
  market: string;
  timeframe: string;
  source: string;
  confidence: number | null;
  score: number | null;
  entry_price: number;
  stop_loss_price: number | null;
  target1_price: number | null;
  target2_price: number | null;
  quantity: number;
  capital_allocated: number;
  opened_at: string;
  entry_notes: string | null;
  status: string;
  exit_price: number | null;
  exit_reason: string | null;
  closed_at: string | null;
  exit_notes: string | null;
  pnl: number | null;
  pnl_pct: number | null;
  holding_days: number | null;
}

interface PaperSignal {
  id: string;
  batch_id: string;
  generated_at: string;
  symbol: string;
  name: string;
  market: string;
  direction: string;
  timeframe: string;
  source: string;
  entry_zone: string | null;
  stop_loss: string | null;
  targets: string | null;
  risk_reward: string | null;
  position_sizing: string | null;
  confirmation_condition: string | null;
  reason: string | null;
  invalidation: string | null;
  trailing_stop: string | null;
  price: number | null;
  change_pct: number | null;
  score: number | null;
  strength: number | null;
  confidence: number | null;
  full_signal: Record<string, unknown> | null;
}

interface EquityPoint {
  date: string;
  equity: number;
  cash: number;
  open_value: number;
  realized_pnl: number;
  open_positions: number;
  total_closed: number;
}

interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── Helpers ────────────────────────────────────────────────────────

function formatNum(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(0) + "K";
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

function pnlColor(v: number | null | undefined): string {
  if (v == null || v === 0) return "text-surface-400";
  return v > 0 ? "text-accent-emerald" : "text-accent-rose";
}

function marketLabel(m: string): string {
  const map: Record<string, string> = {
    stock: "سهام",
    gold: "طلا",
    currency: "ارز",
    crypto: "کریپتو",
    commodity: "کالا",
    ime: "کالا (IME)",
    option: "اختیار",
  };
  return map[m] || m;
}

function directionLabel(d: string): string {
  return d === "buy" ? "خرید" : d === "sell" ? "فروش" : "نگهداری";
}

function exitReasonLabel(r: string | null): string {
  switch (r) {
    case "target_hit": return "هدف تأمین شد";
    case "stop_loss": return "حد ضرر";
    case "max_hold": return "پایان دوره نگهداری";
    case "signal_outcome": return "نتیجه سیگنال";
    case "manual": return "دستی";
    default: return r || "—";
  }
}

// ── Main Page ──────────────────────────────────────────────────────

export default function PaperTradingPage() {
  const [tab, setTab] = useState<"trades" | "signals">("trades");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [openModal, setOpenModal] = useState<PaperSignal | null>(null);
  const [closeTrade, setCloseTrade] = useState<PaperTrade | null>(null);
  const pageSize = 50;

  // ── Dashboard ──
  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ["paper-dashboard"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: PaperDashboard }>("/paper-trading/dashboard");
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
  });

  // ── Equity curve ──
  const { data: equity } = useQuery({
    queryKey: ["paper-equity"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: EquityPoint[] }>("/paper-trading/equity?limit=90");
      return res?.data ?? [];
    },
    refetchInterval: 60_000,
  });

  // ── Trades ──
  const { data: tradesData, isLoading: tradesLoading, refetch: refetchTrades } = useQuery({
    queryKey: ["paper-trades", statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await apiGet<{ success: boolean; data: Paginated<PaperTrade> }>(
        `/paper-trading/trades?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0, page: 1, page_size: pageSize, total_pages: 1 };
    },
  });

  // ── Signal journal ──
  const { data: signalsData, isLoading: signalsLoading } = useQuery({
    queryKey: ["paper-signals", page],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: Paginated<PaperSignal> }>(
        `/paper-trading/signals?page=${page}&page_size=${pageSize}`
      );
      return res?.data ?? { items: [], total: 0, page: 1, page_size: pageSize, total_pages: 1 };
    },
    enabled: tab === "signals",
  });

  const trades = tradesData?.items ?? [];
  const signals = signalsData?.items ?? [];

  // ── Equity sparkline ──
  const equityPath = useMemo(() => {
    if (!equity || equity.length < 2) return "";
    const min = Math.min(...equity.map((e) => e.equity));
    const max = Math.max(...equity.map((e) => e.equity));
    const range = max - min || 1;
    const W = 800, H = 120;
    return equity
      .map((e, i) => {
        const x = (i / (equity.length - 1)) * W;
        const y = H - ((e.equity - min) / range) * (H - 8) - 4;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [equity]);

  const handleOpenTrade = async () => {
    if (!openModal) return;
    const res = await apiPost<{ success: boolean; data: PaperTrade; error?: { message?: string } }>(
      "/paper-trading/trades",
      {
        snapshot_id: openModal.id,
        capital_allocated: 1_000_000,
      }
    );
    if (res?.success) {
      setOpenModal(null);
      refetchTrades();
    } else {
      alert(res?.error?.message || "خطا در باز کردن معامله");
    }
  };

  const handleCloseTrade = async () => {
    if (!closeTrade) return;
    const res = await apiPost<{ success: boolean; data: PaperTrade; error?: { message?: string } }>(
      `/paper-trading/trades/${closeTrade.id}/close`,
      { exit_reason: "manual" }
    );
    if (res?.success) {
      setCloseTrade(null);
      refetchTrades();
    } else {
      alert(res?.error?.message || "خطا در بستن معامله");
    }
  };

  return (
    <AppLayout
      title="📒 معاملات آزمایشی (Paper Trading)"
      subtitle="شبیه‌سازی سود/زیان بر اساس سیگنال‌های تولیدی — همه سیگنال‌ها روزانه ثبت می‌شوند"
    >
      <div className="max-w-7xl mx-auto space-y-5">
        {/* ── Dashboard cards ── */}
        {dashLoading && !dashboard ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
          </div>
        ) : dashboard ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">سرمایه اولیه</p>
              <p className="text-lg font-black font-mono text-surface-100 mt-1">{formatNum(dashboard.initial_capital)}</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">سرمایه فعلی</p>
              <p className={`text-lg font-black font-mono mt-1 ${pnlColor(dashboard.equity - dashboard.initial_capital)}`}>
                {formatNum(dashboard.equity)}
              </p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">سود/زیان کل</p>
              <p className={`text-lg font-black font-mono mt-1 ${pnlColor(dashboard.total_pnl)}`}>
                {dashboard.total_pnl >= 0 ? "+" : ""}{formatNum(dashboard.total_pnl)}
              </p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">نرخ برد</p>
              <p className="text-lg font-black font-mono text-primary-300 mt-1">{dashboard.win_rate.toFixed(1)}%</p>
              <p className="text-[9px] text-surface-600">برد {dashboard.wins} / باخت {dashboard.losses}</p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">فاکتور سود</p>
              <p className={`text-lg font-black font-mono mt-1 ${dashboard.profit_factor >= 1 ? "text-accent-emerald" : "text-accent-rose"}`}>
                {dashboard.profit_factor >= 999 ? "∞" : dashboard.profit_factor.toFixed(2)}
              </p>
            </div>
            <div className="glass-card p-3 text-center">
              <p className="text-[10px] text-surface-500">معاملات</p>
              <p className="text-lg font-black font-mono text-surface-100 mt-1">{dashboard.total_trades.toLocaleString("fa-IR")}</p>
              <p className="text-[9px] text-surface-600">باز {dashboard.open_trades} • بسته {dashboard.closed_trades}</p>
            </div>
          </div>
        ) : null}

        {/* ── Equity curve ── */}
        <Card title="📈 منحنی سرمایه" subtitle="ارزش روزانه حساب آزمایشی">
          {equity && equity.length >= 2 ? (
            <div>
              <svg viewBox="0 0 800 120" className="w-full h-28" preserveAspectRatio="none">
                <line x1="0" y1="60" x2="800" y2="60" stroke="#ffffff10" strokeWidth="1" strokeDasharray="4 4" />
                <path d={equityPath} fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div className="flex justify-between text-[9px] text-surface-600 mt-1">
                <span>{equity[0]?.date}</span>
                <span>{equity[equity.length - 1]?.date}</span>
              </div>
            </div>
          ) : (
            <p className="text-surface-500 text-sm text-center py-8">
              هنوز داده‌ای برای منحنی سرمایه ثبت نشده — جاب روزانه بعد از بسته شدن بازار آن را می‌سازد.
            </p>
          )}
        </Card>

        {/* ── Tabs ── */}
        <div className="flex gap-2">
          <button
            onClick={() => { setTab("trades"); setPage(1); }}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              tab === "trades" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            📋 دفتر معاملات ({dashboard?.total_trades?.toLocaleString("fa-IR") || "—"})
          </button>
          <button
            onClick={() => { setTab("signals"); setPage(1); }}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              tab === "signals" ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            📓 ژورنال سیگنال‌ها
          </button>
        </div>

        {tab === "trades" && (
          <>
            {/* Filters */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-surface-500">وضعیت:</span>
              {(["all", "open", "closed"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => { setStatusFilter(s); setPage(1); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    statusFilter === s ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}
                >
                  {s === "all" ? "همه" : s === "open" ? "باز" : "بسته"}
                </button>
              ))}
              <div className="flex-1" />
              <Link href="/signals/dashboard" className="text-xs text-surface-500 hover:text-surface-200 transition-colors">
                ← داشبورد سیگنال‌ها
              </Link>
            </div>

            {/* Trades table */}
            <Card title="معاملات شبیه‌سازی شده">
              {tradesLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12 w-full rounded-lg" />)}
                </div>
              ) : trades.length === 0 ? (
                <div className="text-center py-12 text-surface-500">
                  <p className="text-4xl mb-3">📭</p>
                  <p>هنوز معامله‌ای ثبت نشده</p>
                  <p className="text-xs mt-2 text-surface-600">
                    سیگنال‌های خرید از ژورنال، معامله باز می‌کنند — جاب روزانه آن را خودکار انجام می‌دهد
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-right text-xs">
                    <thead>
                      <tr className="text-surface-500 border-b border-surface-700">
                        <th className="pb-2 px-2">نماد</th>
                        <th className="pb-2 px-2">بازار</th>
                        <th className="pb-2 px-2">ورود</th>
                        <th className="pb-2 px-2">خروج</th>
                        <th className="pb-2 px-2">تعداد</th>
                        <th className="pb-2 px-2">سود/زیان</th>
                        <th className="pb-2 px-2">بازدهی</th>
                        <th className="pb-2 px-2">وضعیت</th>
                        <th className="pb-2 px-2">عملیات</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((t) => (
                        <tr key={t.id} className="border-b border-surface-800/30 hover:bg-white/[0.03] transition-colors">
                          <td className="py-2 px-2">
                            <p className="font-bold text-surface-100">{t.symbol}</p>
                            <p className="text-[9px] text-surface-600 truncate max-w-[120px]">{t.name}</p>
                          </td>
                          <td className="py-2 px-2 text-surface-400">{marketLabel(t.market)}</td>
                          <td className="py-2 px-2 font-mono text-surface-300">{formatNum(t.entry_price)}</td>
                          <td className="py-2 px-2 font-mono text-surface-300">
                            {t.exit_price ? formatNum(t.exit_price) : <span className="text-surface-600">—</span>}
                          </td>
                          <td className="py-2 px-2 font-mono text-surface-400">{formatNum(t.quantity)}</td>
                          <td className={`py-2 px-2 font-mono font-bold ${pnlColor(t.pnl)}`}>
                            {t.pnl != null ? (t.pnl >= 0 ? "+" : "") + formatNum(t.pnl) : "—"}
                          </td>
                          <td className={`py-2 px-2 font-mono ${pnlColor(t.pnl_pct)}`}>
                            {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct.toFixed(2)}%` : "—"}
                          </td>
                          <td className="py-2 px-2">
                            {t.status === "open" ? (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber">باز</span>
                            ) : (
                              <div>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-700 text-surface-300">بسته</span>
                                <p className="text-[9px] text-surface-600 mt-0.5">{exitReasonLabel(t.exit_reason)}</p>
                              </div>
                            )}
                          </td>
                          <td className="py-2 px-2">
                            {t.status === "open" && (
                              <button
                                onClick={() => setCloseTrade(t)}
                                className="text-[10px] px-2 py-1 rounded-lg bg-accent-rose/10 text-accent-rose hover:bg-accent-rose/20 transition-colors"
                              >
                                بستن
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Pagination */}
              {tradesData && tradesData.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-800">
                  <p className="text-xs text-surface-500">
                    {tradesData.total.toLocaleString("fa-IR")} معامله • صفحه {page} از {tradesData.total_pages}
                  </p>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 transition-all"
                    >
                      قبلی
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(tradesData.total_pages, p + 1))}
                      disabled={page >= tradesData.total_pages}
                      className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 transition-all"
                    >
                      بعدی
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </>
        )}

        {tab === "signals" && (
          <Card title="ژورنال روزانه سیگنال‌ها" subtitle="تمام سیگنال‌های تولیدی با جزئیات کامل ذخیره می‌شوند">
            {signalsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-14 w-full rounded-lg" />)}
              </div>
            ) : signals.length === 0 ? (
              <div className="text-center py-12 text-surface-500">
                <p className="text-4xl mb-3">📓</p>
                <p>هنوز سیگنالی ثبت نشده — جاب روزانه ساعت ۲۱ آن را از موتور سیگنال می‌گیرد</p>
              </div>
            ) : (
              <div className="space-y-2">
                {signals.map((s) => (
                  <div key={s.id} className="flex items-center gap-3 p-3 rounded-xl bg-surface-800/30 hover:bg-surface-800/60 border border-surface-700/30 transition-all">
                    <div className="min-w-[110px]">
                      <p className="font-bold text-surface-100 text-sm">{s.symbol}</p>
                      <p className="text-[9px] text-surface-600 truncate max-w-[120px]">{s.name}</p>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                      s.direction === "buy"
                        ? "bg-accent-emerald/15 text-accent-emerald"
                        : s.direction === "sell"
                        ? "bg-accent-rose/15 text-accent-rose"
                        : "bg-surface-700 text-surface-400"
                    }`}>
                      {directionLabel(s.direction)}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-700/60 text-surface-400">{marketLabel(s.market)}</span>
                    {s.timeframe && <span className="text-[9px] text-surface-600">{s.timeframe}</span>}
                    <div className="flex-1" />
                    <div className="text-left">
                      {s.price != null && (
                        <p className="font-mono text-xs text-surface-300">{formatNum(s.price)}</p>
                      )}
                      {s.confidence != null && (
                        <p className="text-[9px] text-primary-300">اطمینان {Math.round(s.confidence * 100)}%</p>
                      )}
                    </div>
                    <button
                      onClick={() => setOpenModal(s)}
                      disabled={s.direction !== "buy"}
                      className={`text-[10px] px-2.5 py-1.5 rounded-lg transition-all ${
                        s.direction === "buy"
                          ? "bg-primary-600/20 text-primary-300 hover:bg-primary-600/30"
                          : "bg-surface-800 text-surface-600 cursor-not-allowed"
                      }`}
                    >
                      باز کردن معامله
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* ── Open-trade modal ── */}
        {openModal && (
          <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" dir="rtl" onClick={(e) => e.target === e.currentTarget && setOpenModal(null)}>
            <div className="w-full max-w-md rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-surface-100">باز کردن معامله از سیگنال</h3>
                <button onClick={() => setOpenModal(null)} className="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-800 transition-all">
                  <span className="material-icons text-sm">close</span>
                </button>
              </div>
              <div className="space-y-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-surface-500">نماد</span>
                  <span className="font-bold text-surface-100">{openModal.symbol}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">قیمت سیگنال</span>
                  <span className="font-mono text-surface-200">{formatNum(openModal.price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">بازار</span>
                  <span className="text-surface-200">{marketLabel(openModal.market)}</span>
                </div>
                {openModal.entry_zone && (
                  <div className="rounded-xl bg-surface-800/40 p-2.5">
                    <p className="text-[10px] font-bold text-primary-300 mb-1">🎯 محدوده ورود</p>
                    <p className="text-surface-400">{openModal.entry_zone}</p>
                  </div>
                )}
                {openModal.stop_loss && (
                  <div className="rounded-xl bg-accent-rose/5 border border-accent-rose/15 p-2.5">
                    <p className="text-[10px] font-bold text-accent-rose mb-1">🛑 حد ضرر</p>
                    <p className="text-surface-400">{openModal.stop_loss}</p>
                  </div>
                )}
                {openModal.targets && (
                  <div className="rounded-xl bg-accent-emerald/5 border border-accent-emerald/15 p-2.5">
                    <p className="text-[10px] font-bold text-accent-emerald mb-1">🎯 اهداف</p>
                    <p className="text-surface-400">{openModal.targets}</p>
                  </div>
                )}
                {openModal.reason && (
                  <div className="rounded-xl bg-surface-800/40 p-2.5">
                    <p className="text-[10px] font-bold text-surface-400 mb-1">💡 دلیل سیگنال</p>
                    <p className="text-surface-400">{openModal.reason}</p>
                  </div>
                )}
              </div>
              <div className="mt-5 flex gap-2">
                <button
                  onClick={handleOpenTrade}
                  className="flex-1 py-2 rounded-xl bg-primary-600 hover:bg-primary-500 text-white text-xs font-bold transition-all"
                >
                  ✅ باز کردن (۱٬۰۰۰٬۰۰۰ ریال)
                </button>
                <button
                  onClick={() => setOpenModal(null)}
                  className="px-4 py-2 rounded-xl bg-surface-800 text-surface-400 hover:text-surface-200 text-xs transition-all"
                >
                  انصراف
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Close-trade modal ── */}
        {closeTrade && (
          <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" dir="rtl" onClick={(e) => e.target === e.currentTarget && setCloseTrade(null)}>
            <div className="w-full max-w-sm rounded-2xl border border-surface-700/50 bg-surface-900 shadow-2xl p-5">
              <h3 className="text-sm font-bold text-surface-100 mb-4">بستن معامله {closeTrade.symbol}</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-surface-500">قیمت ورود</span>
                  <span className="font-mono text-surface-200">{formatNum(closeTrade.entry_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">حد ضرر</span>
                  <span className="font-mono text-accent-rose">{formatNum(closeTrade.stop_loss_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">هدف ۱</span>
                  <span className="font-mono text-accent-emerald">{formatNum(closeTrade.target1_price)}</span>
                </div>
              </div>
              <p className="text-[10px] text-surface-600 mt-3">
                با قیمت آخرین معامله بسته می‌شود (در صورت در دسترس بودن).
              </p>
              <div className="mt-5 flex gap-2">
                <button
                  onClick={handleCloseTrade}
                  className="flex-1 py-2 rounded-xl bg-accent-rose hover:bg-red-600 text-white text-xs font-bold transition-all"
                >
                  بستن معامله
                </button>
                <button
                  onClick={() => setCloseTrade(null)}
                  className="px-4 py-2 rounded-xl bg-surface-800 text-surface-400 hover:text-surface-200 text-xs transition-all"
                >
                  انصراف
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Quick links ── */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/signals/dashboard" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← داشبورد سیگنال‌ها</Link>
          <Link href="/signals/stocks" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">سیگنال‌های سهام</Link>
          <Link href="/signals/all" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">همه سیگنال‌ها</Link>
        </div>
      </div>
    </AppLayout>
  );
}
