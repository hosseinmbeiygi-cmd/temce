"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import Skeleton from "@/components/Skeleton";

// ── Types ───────────────────────────────────────────────────────────

interface QueueDetail {
  symbol: string;
  name: string;
  queue_status: "BUY_QUEUE" | "SELL_QUEUE" | "NONE";
  queue_volume_ratio: number;
  queue_days_streak: number;
  queue_type_change: string;
  distance_to_limit: number;
  last_price: number;
  price_change_pct: number;
  [key: string]: unknown;
}

interface HeavyQueueItem {
  symbol: string;
  ratio: number;
  streak: number;
}

interface MarketSummary {
  buy_queues: number;
  sell_queues: number;
  no_queues: number;
  buy_queue_pct: number;
  sell_queue_pct: number;
}

interface MarketSignals {
  new_buy_queues: string[];
  new_sell_queues: string[];
  broken_queues: string[];
  heavy_buy_queues: HeavyQueueItem[];
  heavy_sell_queues: HeavyQueueItem[];
}

interface QueueMarketData {
  total_symbols: number;
  analyzed_at: string;
  summary: MarketSummary;
  signals: MarketSignals;
  details: QueueDetail[];
}

interface QueueMarketResponse {
  total_symbols: number;
  analyzed_at: string;
  summary: MarketSummary;
  signals: MarketSignals;
  details: QueueDetail[];
}

interface QueueSymbolData {
  symbol: string;
  name?: string;
  queue_status: "BUY_QUEUE" | "SELL_QUEUE" | "NONE";
  queue_volume_ratio: number;
  queue_days_streak: number;
  queue_type_change: string;
  distance_to_limit: number;
  last_price: number;
  limit_up?: number;
  limit_down?: number;
  queue_buy_volume?: number;
  queue_sell_volume?: number;
  interpretation?: Record<string, string>;
  adjustments?: Record<string, unknown>;
  final_decision?: string;
  override_reason?: string;
  [key: string]: unknown;
}

// ── Helpers ─────────────────────────────────────────────────────────

function statusColor(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "#10b981";
    case "SELL_QUEUE": return "#ef4444";
    default: return "#475569";
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "صف خرید 🟢";
    case "SELL_QUEUE": return "صف فروش 🔴";
    default: return "بدون صف ⚪";
  }
}

function statusBgColor(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "#10b98110";
    case "SELL_QUEUE": return "#ef444410";
    default: return "#47556910";
  }
}

function statusBorderColor(status: string): string {
  switch (status) {
    case "BUY_QUEUE": return "#10b98130";
    case "SELL_QUEUE": return "#ef444430";
    default: return "#47556930";
  }
}

function formatPersianDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("fa-IR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function typeChangeLabel(tc: string): string {
  switch (tc) {
    case "NEW_BUY_QUEUE": return "🟢 صف خرید جدید";
    case "NEW_SELL_QUEUE": return "🔴 صف فروش جدید";
    case "QUEUE_BROKEN": return "🟡 صف شکسته شد";
    default: return "";
  }
}

function typeChangeColor(tc: string): string {
  switch (tc) {
    case "NEW_BUY_QUEUE": return "#10b981";
    case "NEW_SELL_QUEUE": return "#ef4444";
    case "QUEUE_BROKEN": return "#f59e0b";
    default: return "#64748b";
  }
}

// ── Component ───────────────────────────────────────────────────────

export default function QueueStatusPanel() {
  const [searchSymbol, setSearchSymbol] = useState("");
  const [symbolResult, setSymbolResult] = useState<QueueSymbolData | null>(null);
  const [symbolLoading, setSymbolLoading] = useState(false);

  // ── Market overview query ──
  const { data: marketData, isLoading, isError, refetch } = useQuery<QueueMarketData>({
    queryKey: ["queue-analysis-market"],
    queryFn: async () => {
      const res = await apiGet<QueueMarketResponse>("/queue-analysis/market?limit=500");
      return res;
    },
    staleTime: 30_000,
    refetchInterval: 120_000,
  });

  // ── Single symbol search ──
  const handleSearch = async () => {
    const sym = searchSymbol.trim();
    if (!sym) return;
    setSymbolLoading(true);
    setSymbolResult(null);
    try {
      const res = await apiGet<QueueSymbolData>(`/queue-analysis/${encodeURIComponent(sym)}`);
      setSymbolResult(res);
    } catch {
      setSymbolResult({
        symbol: sym,
        queue_status: "NONE",
        queue_volume_ratio: 0,
        queue_days_streak: 0,
        queue_type_change: "NO_CHANGE",
        distance_to_limit: 0,
        last_price: 0,
        _error: "نماد یافت نشد",
      });
    }
    setSymbolLoading(false);
  };

  const summary = marketData?.summary;
  const signals = marketData?.signals;
  const details = marketData?.details || [];

  // ── Loading state ──
  if (isLoading) {
    return (
      <div className="glass-card p-4">
        <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="material-icons text-sm">move_up</span>
          تحلیل صف بازار
        </h2>
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  // ── Error state ──
  if (isError || !marketData) {
    return (
      <div className="glass-card p-4">
        <h2 className="text-sm font-bold text-surface-200 mb-3 flex items-center gap-2">
          <span className="material-icons text-sm">move_up</span>
          تحلیل صف بازار
        </h2>
        <div className="py-4 text-center">
          <span className="material-icons text-xl text-accent-rose mb-1">cloud_off</span>
          <p className="text-[10px] text-surface-500">سرور در دسترس نیست</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-[9px] px-3 py-1.5 bg-surface-800 rounded-lg text-surface-400 hover:text-surface-200 transition-all"
          >
            تلاش مجدد
          </button>
        </div>
      </div>
    );
  }

  // ── Heavy queues sorted ──
  const heavyBuy = (signals?.heavy_buy_queues || []).slice(0, 5);
  const heavySell = (signals?.heavy_sell_queues || []).slice(0, 5);

  // ── Queue list (filtered to non-NONE, sorted by ratio desc) ──
  const queueList = details
    .filter((d) => d.queue_status !== "NONE")
    .sort((a, b) => b.queue_volume_ratio - a.queue_volume_ratio)
    .slice(0, 30);

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-surface-200 flex items-center gap-2">
            <span className="material-icons text-sm">move_up</span>
            تحلیل صف بازار
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-lg">
              {formatPersianDate(marketData.analyzed_at)}
            </span>
            <button
              onClick={() => refetch()}
              className="text-[9px] px-2 py-1 bg-surface-800 rounded-lg text-surface-500 hover:text-surface-300 transition-all"
            >
              <span className="material-icons text-xs">refresh</span>
            </button>
          </div>
        </div>

        {/* ── Summary cards ── */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            <div className="rounded-xl p-3 border border-accent-emerald/20 bg-accent-emerald/05 text-center">
              <div className="text-lg font-black text-accent-emerald font-mono">{summary.buy_queues}</div>
              <div className="text-[9px] text-surface-500 mt-0.5">صف خرید 🟢</div>
              <div className="text-[8px] text-surface-600">{summary.buy_queue_pct}%</div>
            </div>
            <div className="rounded-xl p-3 border border-accent-rose/20 bg-accent-rose/05 text-center">
              <div className="text-lg font-black text-accent-rose font-mono">{summary.sell_queues}</div>
              <div className="text-[9px] text-surface-500 mt-0.5">صف فروش 🔴</div>
              <div className="text-[8px] text-surface-600">{summary.sell_queue_pct}%</div>
            </div>
            <div className="rounded-xl p-3 border border-surface-700/30 bg-surface-800/20 text-center">
              <div className="text-lg font-black text-surface-300 font-mono">{summary.no_queues}</div>
              <div className="text-[9px] text-surface-500 mt-0.5">بدون صف ⚪</div>
            </div>
            <div className="rounded-xl p-3 border border-surface-700/30 bg-surface-800/20 text-center">
              <div className="text-lg font-black text-surface-300 font-mono">{marketData.total_symbols}</div>
              <div className="text-[9px] text-surface-500 mt-0.5">کل نمادها</div>
            </div>
          </div>
        )}

        {/* ── Progress bar: buy vs sell ── */}
        {summary && (summary.buy_queues > 0 || summary.sell_queues > 0) && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-[9px] text-surface-500 mb-1">
              <span>صف خرید {summary.buy_queues}</span>
              <span>صف فروش {summary.sell_queues}</span>
            </div>
            <div className="h-2.5 bg-surface-800 rounded-full overflow-hidden flex">
              <div
                className="h-full transition-all duration-700 rounded-r-full"
                style={{
                  width: `${summary.buy_queue_pct}%`,
                  backgroundColor: "#10b981",
                }}
              />
              <div
                className="h-full transition-all duration-700 rounded-l-full"
                style={{
                  width: `${summary.sell_queue_pct}%`,
                  backgroundColor: "#ef4444",
                }}
              />
            </div>
          </div>
        )}

        {/* ── Signals grid ── */}
        {signals && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {/* New Buy Queues */}
            <div className="rounded-xl p-2.5 border border-accent-emerald/20 bg-accent-emerald/05">
              <div className="text-[9px] font-bold text-accent-emerald mb-1">صف خرید جدید 🟢</div>
              {signals.new_buy_queues.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {signals.new_buy_queues.slice(0, 8).map((sym) => (
                    <span key={sym} className="text-[8px] px-1.5 py-0.5 bg-accent-emerald/10 rounded text-accent-300 font-mono">
                      {sym}
                    </span>
                  ))}
                  {signals.new_buy_queues.length > 8 && (
                    <span className="text-[8px] text-surface-500">+{signals.new_buy_queues.length - 8}</span>
                  )}
                </div>
              ) : (
                <span className="text-[8px] text-surface-500">—</span>
              )}
            </div>

            {/* New Sell Queues */}
            <div className="rounded-xl p-2.5 border border-accent-rose/20 bg-accent-rose/05">
              <div className="text-[9px] font-bold text-accent-rose mb-1">صف فروش جدید 🔴</div>
              {signals.new_sell_queues.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {signals.new_sell_queues.slice(0, 8).map((sym) => (
                    <span key={sym} className="text-[8px] px-1.5 py-0.5 bg-accent-rose/10 rounded text-accent-300 font-mono">
                      {sym}
                    </span>
                  ))}
                  {signals.new_sell_queues.length > 8 && (
                    <span className="text-[8px] text-surface-500">+{signals.new_sell_queues.length - 8}</span>
                  )}
                </div>
              ) : (
                <span className="text-[8px] text-surface-500">—</span>
              )}
            </div>

            {/* Broken Queues */}
            <div className="rounded-xl p-2.5 border border-accent-amber/20 bg-accent-amber/05">
              <div className="text-[9px] font-bold text-accent-amber mb-1">صف شکسته شده 🟡</div>
              {signals.broken_queues.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {signals.broken_queues.slice(0, 8).map((sym) => (
                    <span key={sym} className="text-[8px] px-1.5 py-0.5 bg-accent-amber/10 rounded text-accent-300 font-mono">
                      {sym}
                    </span>
                  ))}
                  {signals.broken_queues.length > 8 && (
                    <span className="text-[8px] text-surface-500">+{signals.broken_queues.length - 8}</span>
                  )}
                </div>
              ) : (
                <span className="text-[8px] text-surface-500">—</span>
              )}
            </div>

            {/* Heavy Buy */}
            <div className="rounded-xl p-2.5 border border-accent-emerald/20 bg-accent-emerald/05">
              <div className="text-[9px] font-bold text-accent-emerald mb-1">سنگین‌ترین صف خرید</div>
              {heavyBuy.length > 0 ? (
                <div className="space-y-1">
                  {heavyBuy.map((h) => (
                    <div key={h.symbol} className="flex items-center justify-between text-[8px]">
                      <span className="font-mono text-accent-300">{h.symbol}</span>
                      <span className="text-surface-500">{(h.ratio * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-[8px] text-surface-500">—</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Symbol Search ── */}
      <div className="glass-card p-4">
        <h3 className="text-xs font-bold text-surface-200 mb-2 flex items-center gap-2">
          <span className="material-icons text-sm">search</span>
          جستجوی وضعیت صف نماد
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={searchSymbol}
            onChange={(e) => setSearchSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="مثال: فولاد"
            className="flex-1 px-3 py-2 bg-surface-800 border border-surface-700/30 rounded-xl text-xs text-surface-200 placeholder:text-surface-500 focus:outline-none focus:border-primary-600/50 transition-all"
          />
          <button
            onClick={handleSearch}
            disabled={symbolLoading || !searchSymbol.trim()}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white text-xs font-medium rounded-xl transition-all"
          >
            {symbolLoading ? "..." : "جستجو"}
          </button>
        </div>

        {symbolResult && (
          <div
            className="mt-3 rounded-xl p-3 border transition-all"
            style={{
              borderColor: statusBorderColor(symbolResult.queue_status),
              backgroundColor: statusBgColor(symbolResult.queue_status),
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-surface-200">{symbolResult.symbol}</span>
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white"
                style={{ backgroundColor: statusColor(symbolResult.queue_status) }}
              >
                {statusLabel(symbolResult.queue_status)}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div>
                <span className="text-surface-500">نسبت حجم صف: </span>
                <span className="font-mono text-surface-200">
                  {(symbolResult.queue_volume_ratio * 100).toFixed(0)}%
                </span>
              </div>
              <div>
                <span className="text-surface-500">تداوم: </span>
                <span className="font-mono text-surface-200">{symbolResult.queue_days_streak} روز</span>
              </div>
              <div>
                <span className="text-surface-500">فاصله تا دامنه: </span>
                <span className="font-mono text-surface-200">{symbolResult.distance_to_limit.toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-surface-500">قیمت: </span>
                <span className="font-mono text-surface-200">{symbolResult.last_price?.toLocaleString()}</span>
              </div>
            </div>

            {/* Type change badge */}
            {symbolResult.queue_type_change && symbolResult.queue_type_change !== "NO_CHANGE" && (
              <div
                className="mt-2 text-[9px] px-2 py-1 rounded-lg inline-block"
                style={{
                  backgroundColor: typeChangeColor(symbolResult.queue_type_change) + "15",
                  color: typeChangeColor(symbolResult.queue_type_change),
                }}
              >
                {typeChangeLabel(symbolResult.queue_type_change)}
              </div>
            )}

            {/* Interpretation */}
            {symbolResult.interpretation && (
              <div className="mt-2 space-y-0.5">
                {Object.values(symbolResult.interpretation).map((text, i) => (
                  <div key={i} className="text-[9px] text-surface-400">{text as string}</div>
                ))}
              </div>
            )}

            {/* Final decision if overridden */}
            {symbolResult.override_reason && (
              <div className="mt-2 text-[9px] px-2 py-1 rounded-lg bg-accent-amber/10 text-accent-300">
                ⚠️ {symbolResult.override_reason}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Queue list ── */}
            {queueList.slice(0, 30).length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-xs font-bold text-surface-200 mb-2 flex items-center gap-2">
            <span className="material-icons text-sm">list</span>
            نمادهای دارای صف
            <span className="text-[9px] text-surface-500 bg-surface-800 px-2 py-0.5 rounded-full font-normal">
              {queueList.slice(0, 30).length} نماد
            </span>
          </h3>

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="border-b border-surface-700/50">
                  <th className="text-right px-2 py-1.5 text-[9px] font-medium text-surface-500">نماد</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">وضعیت</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">شدت</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">تداوم</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">نوع تغییر</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">فاصله</th>
                  <th className="text-center px-2 py-1.5 text-[9px] font-medium text-surface-500">تغییرات</th>
                </tr>
              </thead>
              <tbody>
                {queueList.map((q) => (
                  <tr
                    key={q.symbol}
                    className="border-b border-surface-800/20 hover:bg-surface-800/20 transition-colors"
                  >
                    <td className="px-2 py-2 font-bold font-mono text-primary-300">{q.symbol}</td>
                    <td className="px-2 py-2 text-center">
                      <span
                        className="text-[8px] font-bold px-1.5 py-0.5 rounded-full text-white"
                        style={{ backgroundColor: statusColor(q.queue_status) }}
                      >
                        {q.queue_status === "BUY_QUEUE" ? "خرید" : "فروش"}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(q.queue_volume_ratio * 100).toFixed(0)}%`,
                              backgroundColor: statusColor(q.queue_status),
                            }}
                          />
                        </div>
                        <span className="font-mono text-surface-400">{(q.queue_volume_ratio * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-2 py-2 text-center font-mono text-surface-300">{q.queue_days_streak}</td>
                    <td className="px-2 py-2 text-center">
                      {q.queue_type_change !== "NO_CHANGE" ? (
                        <span className="text-[8px]" style={{ color: typeChangeColor(q.queue_type_change) }}>
                          {typeChangeLabel(q.queue_type_change)}
                        </span>
                      ) : (
                        <span className="text-surface-600">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-center font-mono text-surface-400">
                      {q.distance_to_limit.toFixed(1)}%
                    </td>
                    <td className="px-2 py-2 text-center">
                      <span className={`font-mono text-[10px] ${q.price_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                        {q.price_change_pct > 0 ? "+" : ""}{q.price_change_pct?.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {queueList.slice(0, 10).map((q) => (
              <div
                key={q.symbol}
                className="rounded-xl p-3 border transition-all"
                style={{
                  borderColor: statusBorderColor(q.queue_status),
                  backgroundColor: statusBgColor(q.queue_status),
                }}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-primary-300">{q.symbol}</span>
                  <span
                    className="text-[8px] font-bold px-1.5 py-0.5 rounded-full text-white"
                    style={{ backgroundColor: statusColor(q.queue_status) }}
                  >
                    {statusLabel(q.queue_status)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[9px]">
                  <span className="text-surface-500">شدت صف</span>
                  <div className="flex items-center gap-1">
                    <div className="w-16 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${(q.queue_volume_ratio * 100).toFixed(0)}%`, backgroundColor: statusColor(q.queue_status) }} />
                    </div>
                    <span className="font-mono text-surface-400">{(q.queue_volume_ratio * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex justify-between text-[9px] mt-1">
                  <span className="text-surface-500">تداوم: {q.queue_days_streak} روز</span>
                  <span className={`font-mono ${q.price_change_pct >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                    {q.price_change_pct > 0 ? "+" : ""}{q.price_change_pct?.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Heavy sell alert ── */}
      {heavySell.length > 2 && (
        <div className="rounded-xl p-3 border border-accent-rose/30 bg-accent-rose/05">
          <div className="flex items-center gap-2">
            <span className="material-icons text-accent-rose text-sm">warning</span>
            <span className="text-[10px] text-surface-300">
              ⚠️ <strong>{heavySell.length}</strong> نماد با صف فروش سنگین (شدت &gt; ۷۰٪)
            </span>
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {heavySell.map((h) => (
              <span key={h.symbol} className="text-[8px] px-1.5 py-0.5 bg-accent-rose/10 rounded text-accent-300 font-mono">
                {h.symbol} ({(h.ratio * 100).toFixed(0)}%)
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
