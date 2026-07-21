"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface MarketSignal {
  symbol: string;
  name: string;
  market: string;
  direction: string;
  timeframe: string;
  entry_zone: string;
  stop_loss: string;
  targets: string;
  risk_reward: string;
  position_sizing: string;
  confirmation_condition: string;
  reason: string;
  invalidation: string;
  trailing_stop: string;
  price: number;
  change_pct: number;
  score: number;
  strength: number;
  confidence: number;
  source: string;
  created_at: string;
}

interface SignalSummary {
  total_signals: number;
  buy_count: number;
  sell_count: number;
  hold_count: number;
  markets: Record<string, { buy: number; sell: number; hold: number; top_buy?: any }>;
}

interface SignalResponse {
  signals: MarketSignal[];
  summary: SignalSummary;
  filters: Record<string, any>;
  generated_at: string;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const MARKETS = [
  { id: "all", label: "همه بازارها", icon: "🌐" },
  { id: "stock", label: "سهام", icon: "📈" },
  { id: "gold", label: "سکه و طلا", icon: "🪙" },
  { id: "currency", label: "ارز", icon: "💱" },
  { id: "crypto", label: "رمزارز", icon: "₿" },
  { id: "option", label: "آپشن", icon: "📊" },
  { id: "commodity", label: "کالا", icon: "🛢️" },
  { id: "ime", label: "بورس کالا", icon: "🏭" },
];

const TIMEFRAMES = [
  { id: "all", label: "همه" },
  { id: "daily", label: "روزانه" },
  { id: "2day", label: "۲ روزه" },
  { id: "3day", label: "۳ روزه" },
  { id: "weekly", label: "هفتگی" },
  { id: "monthly", label: "ماهانه" },
  { id: "quarterly", label: "سه‌ماهه" },
];

const SIGNAL_FILTERS = [
  { id: "all", label: "همه", color: "text-surface-400" },
  { id: "buy", label: "🟢 خرید", color: "text-accent-emerald" },
  { id: "sell", label: "🔴 فروش", color: "text-accent-rose" },
  { id: "hold", label: "⚪ انتظار", color: "text-surface-400" },
];

const MARKET_LABELS: Record<string, string> = {
  stock: "سهام", gold: "طلا", currency: "ارز", crypto: "رمزارز",
  option: "آپشن", commodity: "کالا", ime: "بورس کالا",
};

const TIMEFRAME_LABELS: Record<string, string> = {
  daily: "روزانه", "2day": "۲ روزه", "3day": "۳ روزه",
  weekly: "هفتگی", monthly: "ماهانه", quarterly: "سه‌ماهه",
};

const DIRECTION_LABELS: Record<string, string> = {
  buy: "خرید", sell: "فروش", hold: "نگهداری", wait: "انتظار",
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const directionColor = (d: string) =>
  d === "buy" ? "bg-accent-emerald/15 text-accent-emerald border-accent-emerald/30" :
  d === "sell" ? "bg-accent-rose/15 text-accent-rose border-accent-rose/30" :
  "bg-surface-700/30 text-surface-400 border-surface-600/30";

const marketColor = (m: string) =>
  m === "stock" ? "bg-blue-500/15 text-blue-400" :
  m === "gold" ? "bg-yellow-500/15 text-yellow-400" :
  m === "currency" ? "bg-green-500/15 text-green-400" :
  m === "crypto" ? "bg-purple-500/15 text-purple-400" :
  m === "option" ? "bg-orange-500/15 text-orange-400" :
  m === "commodity" ? "bg-amber-500/15 text-amber-400" :
  m === "ime" ? "bg-cyan-500/15 text-cyan-400" :
  "bg-surface-600/30 text-surface-400";

const fmt = (n: number) => n?.toLocaleString("fa-IR") ?? "—";
const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
const fmtScore = (n: number) => `${n.toFixed(0)}`;

// ── Signal Detail Modal ────────────────────────────────────────────────────────

function SignalDetail({ signal, onClose }: { signal: MarketSignal; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-900 border border-surface-700 rounded-2xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-1 rounded-full font-bold ${directionColor(signal.direction)}`}>
              {DIRECTION_LABELS[signal.direction] || signal.direction}
            </span>
            <span className="text-sm font-bold text-surface-100">{signal.symbol}</span>
            <span className="text-xs text-surface-500">{signal.name}</span>
          </div>
          <button onClick={onClose} className="text-surface-500 hover:text-surface-200 text-xl">&times;</button>
        </div>

        {/* Score bar */}
        <div className="mb-4">
          <div className="flex justify-between text-[10px] text-surface-500 mb-1">
            <span>امتیاز: {fmtScore(signal.score)}/100</span>
            <span>قدرت: {(signal.strength * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${signal.direction === "buy" ? "bg-accent-emerald" : signal.direction === "sell" ? "bg-accent-rose" : "bg-surface-500"}`}
              style={{ width: `${Math.min(100, signal.score)}%` }} />
          </div>
        </div>

        {/* 6 Mandatory Fields */}
        <div className="space-y-3 mb-4">
          <h4 className="text-xs font-bold text-surface-300 border-b border-surface-700 pb-1">📋 ۶ ستون اصلی سیگنال</h4>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۱. نماد و جهت معامله</p>
            <p className="text-xs text-surface-200 font-bold">{signal.symbol} — {DIRECTION_LABELS[signal.direction]}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۲. بازه زمانی سیگنال</p>
            <p className="text-xs text-surface-200">{TIMEFRAME_LABELS[signal.timeframe] || signal.timeframe}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۳. نقطه ورود (Entry Price)</p>
            <p className="text-xs text-surface-200">{signal.entry_zone}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۴. حد ضرر (Stop-Loss)</p>
            <p className="text-xs text-accent-rose font-bold">{signal.stop_loss}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۵. اهداف سود (Targets)</p>
            <p className="text-xs text-accent-emerald">{signal.targets}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۶. نسبت ریسک به ریوارد (R/R)</p>
            <p className="text-xs text-surface-200 font-bold">{signal.risk_reward}</p>
          </div>
        </div>

        {/* 5 Professional Fields */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-surface-300 border-b border-surface-700 pb-1">🛠️ ارکان تکمیلی و حرفه‌ای</h4>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۷. حجم پیشنهادی (Position Sizing)</p>
            <p className="text-xs text-surface-200">{signal.position_sizing || "—"}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۸. شرط تأیید ورود</p>
            <p className="text-xs text-surface-200">{signal.confirmation_condition || "—"}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۹. علت و منطق (چرا؟)</p>
            <p className="text-xs text-surface-200">{signal.reason || "—"}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۱۰. شرایط فسخ سیگنال</p>
            <p className="text-xs text-surface-200">{signal.invalidation || "—"}</p>
          </div>

          <div className="bg-surface-800/50 rounded-xl p-3">
            <p className="text-[10px] text-surface-500 mb-1">۱۱. مدیریت پس از ورود (Trailing Stop)</p>
            <p className="text-xs text-surface-200">{signal.trailing_stop || "—"}</p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 pt-3 border-t border-surface-700 flex justify-between text-[10px] text-surface-500">
          <span>منبع: {signal.source}</span>
          <span>{new Date(signal.created_at).toLocaleTimeString("fa-IR")}</span>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function MultiMarketSignalsPage() {
  const [selectedMarket, setSelectedMarket] = useState("all");
  const [selectedTimeframe, setSelectedTimeframe] = useState("all");
  const [selectedSignal, setSelectedSignal] = useState("all");
  const [selectedSignalDetail, setSelectedSignalDetail] = useState<MarketSignal | null>(null);

  const fetchData = useCallback(async () => {
    const params = new URLSearchParams({
      market: selectedMarket,
      timeframe: selectedTimeframe,
      signal: selectedSignal,
      limit: "100",
    });
    return apiGet<SignalResponse>(`/multi-signals?${params}`);
  }, [selectedMarket, selectedTimeframe, selectedSignal]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["multi-signals", selectedMarket, selectedTimeframe, selectedSignal],
    queryFn: fetchData,
    refetchInterval: 60000,
    staleTime: 30000,
  });

  const signals: MarketSignal[] = data?.signals || [];
  const summary: SignalSummary = data?.summary || { total_signals: 0, buy_count: 0, sell_count: 0, hold_count: 0, markets: {} };

  return (
    <AppLayout title="🎯 سیگنال‌یاب چندبازاره" subtitle="بهترین فرصت‌های خرید و فروش از تمام بازارها">
      <div className="space-y-4">
        {/* ── Filters ── */}
        <Card title="فیلترها">
          <div className="space-y-3">
            {/* Market filter */}
            <div>
              <p className="text-[10px] text-surface-500 mb-2">بازار:</p>
              <div className="flex flex-wrap gap-1.5">
                {MARKETS.map((m) => (
                  <button key={m.id} onClick={() => setSelectedMarket(m.id)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${selectedMarket === m.id ? "bg-primary-600/30 text-primary-300 border-primary-500/50" : "bg-surface-800 text-surface-400 border-surface-700/30 hover:text-surface-200"}`}>
                    {m.icon} {m.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeframe filter */}
            <div>
              <p className="text-[10px] text-surface-500 mb-2">بازه زمانی:</p>
              <div className="flex flex-wrap gap-1.5">
                {TIMEFRAMES.map((tf) => (
                  <button key={tf.id} onClick={() => setSelectedTimeframe(tf.id)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${selectedTimeframe === tf.id ? "bg-primary-600/30 text-primary-300 border-primary-500/50" : "bg-surface-800 text-surface-400 border-surface-700/30 hover:text-surface-200"}`}>
                    {tf.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Signal filter */}
            <div>
              <p className="text-[10px] text-surface-500 mb-2">نوع سیگنال:</p>
              <div className="flex flex-wrap gap-1.5">
                {SIGNAL_FILTERS.map((sf) => (
                  <button key={sf.id} onClick={() => setSelectedSignal(sf.id)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${selectedSignal === sf.id ? "bg-primary-600/30 text-primary-300 border-primary-500/50" : "bg-surface-800 text-surface-400 border-surface-700/30 hover:text-surface-200"}`}>
                    {sf.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* ── Summary Cards ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card title="کل سیگنال‌ها">
            <p className="text-2xl font-bold text-surface-100">{fmt(summary.total_signals)}</p>
          </Card>
          <Card title="🟢 سیگنال خرید">
            <p className="text-2xl font-bold text-accent-emerald">{fmt(summary.buy_count)}</p>
          </Card>
          <Card title="🔴 سیگنال فروش">
            <p className="text-2xl font-bold text-accent-rose">{fmt(summary.sell_count)}</p>
          </Card>
          <Card title="⚪ در انتظار">
            <p className="text-2xl font-bold text-surface-400">{fmt(summary.hold_count)}</p>
          </Card>
        </div>

        {/* ── Market Breakdown ── */}
        {Object.keys(summary.markets).length > 0 && (
          <Card title="خلاصه هر بازار">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
              {Object.entries(summary.markets).map(([market, stats]) => (
                <div key={market} className="bg-surface-800/50 rounded-xl p-2.5 text-center">
                  <p className="text-[10px] text-surface-500">{MARKET_LABELS[market] || market}</p>
                  <div className="flex justify-center gap-2 mt-1">
                    <span className="text-[10px] text-accent-emerald">{stats.buy}🟢</span>
                    <span className="text-[10px] text-accent-rose">{stats.sell}🔴</span>
                  </div>
                  {stats.top_buy && (
                    <p className="text-[9px] text-surface-400 mt-1 truncate">🏆 {stats.top_buy.symbol}</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* ── Loading ── */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            <span className="mr-3 text-sm text-surface-400">در حال محاسبه سیگنال‌ها...</span>
          </div>
        )}

        {/* ── Signals Table ── */}
        {!isLoading && signals.length > 0 && (
          <Card title={`لیست سیگنال‌ها (${signals.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-surface-700">
                    <th className="py-2 px-2 text-right text-surface-500">#</th>
                    <th className="py-2 px-2 text-right text-surface-500">نماد</th>
                    <th className="py-2 px-2 text-right text-surface-500">بازار</th>
                    <th className="py-2 px-2 text-right text-surface-500">جهت</th>
                    <th className="py-2 px-2 text-right text-surface-500">تایم‌فریم</th>
                    <th className="py-2 px-2 text-right text-surface-500">قیمت</th>
                    <th className="py-2 px-2 text-right text-surface-500">تغییر</th>
                    <th className="py-2 px-2 text-right text-surface-500">امتیاز</th>
                    <th className="py-2 px-2 text-right text-surface-500">R/R</th>
                    <th className="py-2 px-2 text-right text-surface-500">حد ضرر</th>
                    <th className="py-2 px-2 text-right text-surface-500">منطق</th>
                    <th className="py-2 px-2 text-right text-surface-500">جزئیات</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((s, i) => (
                    <tr key={`${s.symbol}-${s.timeframe}-${i}`} className="border-b border-surface-800/50 hover:bg-surface-800/30 cursor-pointer"
                      onClick={() => setSelectedSignalDetail(s)}>
                      <td className="py-2 px-2 text-surface-500">{i + 1}</td>
                      <td className="py-2 px-2">
                        <div>
                          <span className="font-bold text-surface-200">{s.symbol}</span>
                          <span className="text-surface-500 mr-1 text-[9px]">{s.name}</span>
                        </div>
                      </td>
                      <td className="py-2 px-2">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${marketColor(s.market)}`}>
                          {MARKET_LABELS[s.market] || s.market}
                        </span>
                      </td>
                      <td className="py-2 px-2">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold border ${directionColor(s.direction)}`}>
                          {DIRECTION_LABELS[s.direction]}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-surface-300">{TIMEFRAME_LABELS[s.timeframe] || s.timeframe}</td>
                      <td className="py-2 px-2 font-mono text-surface-200">{fmt(s.price)}</td>
                      <td className={`py-2 px-2 font-mono ${s.change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {fmtPct(s.change_pct)}
                      </td>
                      <td className="py-2 px-2">
                        <div className="flex items-center gap-1">
                          <div className="w-8 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${s.score > 60 ? "bg-accent-emerald" : s.score < 40 ? "bg-accent-rose" : "bg-surface-500"}`}
                              style={{ width: `${Math.min(100, s.score)}%` }} />
                          </div>
                          <span className="text-surface-400">{fmtScore(s.score)}</span>
                        </div>
                      </td>
                      <td className="py-2 px-2 text-surface-300 font-mono">{s.risk_reward}</td>
                      <td className="py-2 px-2 text-accent-rose text-[9px] max-w-[120px] truncate">{s.stop_loss}</td>
                      <td className="py-2 px-2 text-surface-400 text-[9px] max-w-[150px] truncate">{s.reason}</td>
                      <td className="py-2 px-2">
                        <button className="text-primary-400 hover:text-primary-300 text-[10px]">📋</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* ── Empty State ── */}
        {!isLoading && signals.length === 0 && (
          <Card title="نتیجه‌ای یافت نشد">
            <div className="text-center py-12">
              <span className="text-4xl mb-4 block">🔍</span>
              <p className="text-surface-400 text-sm">سیگنالی با فیلترهای انتخاب شده یافت نشد</p>
              <p className="text-surface-500 text-[10px] mt-1">فیلترها را تغییر دهید اگر داده کافی در دیتابیس وجود داشته باشد</p>
            </div>
          </Card>
        )}

        {/* ── Refresh Button ── */}
        <div className="flex justify-center">
          <button onClick={() => refetch()}
            className="px-4 py-2 bg-primary-600/20 text-primary-300 rounded-xl text-xs font-bold hover:bg-primary-600/30 transition-all border border-primary-500/30">
            🔄 بروزرسانی سیگنال‌ها
          </button>
        </div>

        {/* ── Detail Modal ── */}
        {selectedSignalDetail && (
          <SignalDetail signal={selectedSignalDetail} onClose={() => setSelectedSignalDetail(null)} />
        )}
      </div>
    </AppLayout>
  );
}
