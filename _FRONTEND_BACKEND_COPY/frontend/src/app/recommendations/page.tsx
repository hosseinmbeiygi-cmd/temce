"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card, CardAction } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";
import Link from "next/link";

// ------ Types -------------------------------------------------------------------------------------------------------

interface Recommendation {
  id: string;
  instrument_id: string;
  symbol: string;
  action: string;
  target_price: number | null;
  current_price: number;
  potential_return_pct: number;
  confidence: number;
  horizon: string;
  source: string;
  analyst: string;
  rationale: string;
  tags: string[];
  stop_loss: number | null;
  strategy: string;
  risk_level: string;
  generated_at: string | null;
  expires_at: string | null;
  created_at: string | null;
}

interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ------ Helpers -----------------------------------------------------------------------------------------------------

const ACTION_META: Record<string, { label: string; icon: string; color: string }> = {
  strong_buy: { label: "خرید قوی", icon: "🔥", color: "bg-accent-emerald text-white" },
  buy: { label: "خرید", icon: "📈", color: "bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30" },
  accumulate: { label: "انباشت", icon: "📊", color: "bg-accent-emerald/10 text-accent-emerald/70 border border-accent-emerald/20" },
  hold: { label: "نگهداری", icon: "⏸️", color: "bg-accent-amber/15 text-accent-amber border border-accent-amber/30" },
  reduce: { label: "کاهش", icon: "📉", color: "bg-accent-rose/10 text-accent-rose/70 border border-accent-rose/20" },
  sell: { label: "فروش", icon: "📉", color: "bg-accent-rose/15 text-accent-rose border border-accent-rose/30" },
  strong_sell: { label: "فروش قوی", icon: "🚨", color: "bg-accent-rose text-white" },
};

const HORIZON_LABELS: Record<string, string> = {
  short_term: "کوتاه‌مدت",
  medium_term: "میان‌مدت",
  long_term: "بلندمدت",
};

const RISK_LABELS: Record<string, { label: string; color: string }> = {
  low: { label: "کم", color: "text-accent-emerald" },
  medium: { label: "متوسط", color: "text-accent-amber" },
  high: { label: "زیاد", color: "text-accent-rose" },
  very_high: { label: "خیلی زیاد", color: "text-accent-rose font-bold" },
};

const STRATEGY_LABELS: Record<string, string> = {
  value: "ارزشی",
  growth: "رشدی",
  momentum: "مومنتوم",
  income: "سودآوری",
  technical: "تکنیکال",
  fundamental: "بنیادی",
  sentiment: "احساسات",
  ml_model: "مدل ML",
  hybrid: "ترکیبی",
  manual: "دستی",
};

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000_000_000) return (n / 1_000_000_000_000).toFixed(2) + "T";
  if (Math.abs(n) >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + "B";
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function formatPct(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "—", color: "text-surface-500" };
  if (val > 0) return { text: `+${val.toFixed(1)}%`, color: "text-accent-emerald" };
  if (val < 0) return { text: `${val.toFixed(1)}%`, color: "text-accent-rose" };
  return { text: "0.0%", color: "text-surface-400" };
}

function getActionLabel(action: string): string {
  return ACTION_META[action]?.label ?? action;
}

function getActionColor(action: string): string {
  return ACTION_META[action]?.color ?? "bg-surface-700 text-surface-300";
}

function getActionIcon(action: string): string {
  return ACTION_META[action]?.icon ?? "❓";
}

// ------ Components --------------------------------------------------------------------------------------------------

function ActionBadge({ action }: { action: string }) {
  const meta = ACTION_META[action];
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-lg ${getActionColor(action)}`}>
      <span>{getActionIcon(action)}</span>
      <span>{getActionLabel(action)}</span>
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value * 100));
  const color = pct >= 70 ? "bg-accent-emerald" : pct >= 40 ? "bg-accent-amber" : "bg-accent-rose";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden" dir="ltr">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-surface-300 w-8 text-right">{pct.toFixed(0)}%</span>
    </div>
  );
}

function ReturnBadge({ pct }: { pct: number | null | undefined }) {
  const fmt = formatPct(pct);
  return <span className={`text-sm font-bold font-mono ${fmt.color}`}>{fmt.text}</span>;
}

function UpliftSection({ current, target }: { current: number; target: number | null }) {
  if (!target || !current) return null;
  const uplift = ((target - current) / current) * 100;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-surface-500">هدف:</span>
      <span className="font-mono font-bold text-surface-200">{formatNumber(target)}</span>
      <span className="font-mono text-xs">({(uplift > 0 ? "+" : "") + uplift.toFixed(1)}%)</span>
    </div>
  );
}

// ------ Stats Card Component ----------------------------------------------------------------------------------------

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string; color?: string }) {
  return (
    <div className="glass-card p-3 flex items-center gap-3">
      <span className="text-xl">{icon}</span>
      <div>
        <div className="text-xs text-surface-500">{label}</div>
        <div className={`text-lg font-bold ${color || "text-surface-100"}`}>{value}</div>
      </div>
    </div>
  );
}

// ------ Main Page ---------------------------------------------------------------------------------------------------

export default function RecommendationsPage() {
  const [actionFilter, setActionFilter] = useState<string | null>(null);
  const [horizonFilter, setHorizonFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [searchSymbol, setSearchSymbol] = useState("");
  const pageSize = 25;

  // Fetch recommendations
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["recommendations", page, actionFilter, horizonFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      const res = await apiGet<{ success: boolean; data: PaginatedResult<Recommendation> }>(
        `/recommendations?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0, page: 1, page_size: 25, total_pages: 1 };
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const recommendations = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, data?.total_pages ?? 1);

  // Apply client-side filters
  let filtered = recommendations;
  if (actionFilter) {
    filtered = filtered.filter((r) => r.action === actionFilter);
  }
  if (horizonFilter) {
    filtered = filtered.filter((r) => r.horizon === horizonFilter);
  }
  if (searchSymbol) {
    const q = searchSymbol.toLowerCase();
    filtered = filtered.filter((r) => r.symbol.toLowerCase().includes(q));
  }

  // Compute stats
  const buyRecs = recommendations.filter((r) => r.action.includes("buy") || r.action === "accumulate" || r.action === "strong_buy");
  const sellRecs = recommendations.filter((r) => r.action.includes("sell") || r.action === "reduce" || r.action === "strong_sell");
  const holdRecs = recommendations.filter((r) => r.action === "hold");
  const avgConfidence = recommendations.length > 0
    ? recommendations.reduce((s, r) => s + (r.confidence ?? 0), 0) / recommendations.length
    : 0;

  const ACTION_TYPES = ["strong_buy", "buy", "accumulate", "hold", "reduce", "sell", "strong_sell"];

  return (
    <AppLayout
      title="توصیه‌ها"
      subtitle={total.toLocaleString() + " توصیه • " + buyRecs.length + " خرید • " + sellRecs.length + " فروش • " + holdRecs.length + " نگهداری"}
    >
      <div className="max-w-7xl mx-auto space-y-5">
        {/* Stats Row */}
        {!isLoading && recommendations.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard icon="💎" label="کل توصیه‌ها" value={total.toLocaleString()} />
            <StatCard icon="🟢" label="خرید" value={buyRecs.length.toLocaleString()} color="text-accent-emerald" />
            <StatCard icon="🔴" label="فروش" value={sellRecs.length.toLocaleString()} color="text-accent-rose" />
            <StatCard icon="⏸️" label="نگهداری" value={holdRecs.length.toLocaleString()} color="text-accent-amber" />
          </div>
        )}

        {/* Filters */}
        <div className="glass-card p-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Action Filter */}
            <div className="flex flex-wrap gap-1">
              <button
                onClick={() => setActionFilter(null)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  !actionFilter
                    ? "bg-primary-600 text-white shadow-lg"
                    : "bg-surface-800 text-surface-400 hover:text-surface-200"
                }`}
              >
                همه
              </button>
              {[
                { key: "buy", label: "خرید", icon: "🟢" },
                { key: "sell", label: "فروش", icon: "🔴" },
                { key: "hold", label: "خنثی", icon: "⏸️" },
              ].map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setActionFilter(actionFilter === opt.key ? null : opt.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    actionFilter === opt.key
                      ? "bg-primary-600 text-white shadow-lg"
                      : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}
                >
                  {opt.icon} {opt.label}
                </button>
              ))}
            </div>

            <div className="w-px h-6 bg-surface-700" />

            {/* Horizon Filter */}
            <div className="flex gap-1">
              {[
                { key: "short_term", label: "کوتاه‌مدت" },
                { key: "medium_term", label: "میان‌مدت" },
                { key: "long_term", label: "بلندمدت" },
              ].map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setHorizonFilter(horizonFilter === opt.key ? null : opt.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                    horizonFilter === opt.key
                      ? "bg-surface-700 text-surface-100"
                      : "bg-surface-800 text-surface-400 hover:text-surface-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="w-px h-6 bg-surface-700" />

            {/* Symbol Search */}
            <div className="flex items-center gap-2">
              <span className="material-icons text-sm text-surface-500">search</span>
              <input
                type="text"
                value={searchSymbol}
                onChange={(e) => setSearchSymbol(e.target.value)}
                placeholder="جستجوی نماد..."
                className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-sm text-surface-100 w-28 outline-none focus:border-primary-500 font-mono"
              />
            </div>

            {/* Refresh */}
            <button
              onClick={() => refetch()}
              className="p-1.5 rounded-lg bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
              title="Refresh"
            >
              <span className="material-icons text-sm">refresh</span>
            </button>
          </div>

          {/* Summary */}
          {recommendations.length > 0 && (
            <div className="mt-3 flex items-center gap-4 text-xs text-surface-500">
              <span>نمایش {filtered.length} از {total} توصیه</span>
              {actionFilter && <span>• فیلتر: {getActionLabel(actionFilter)}</span>}
              {horizonFilter && <span>• افق: {HORIZON_LABELS[horizonFilter] || horizonFilter}</span>}
              {searchSymbol && <span>• نماد: {searchSymbol}</span>}
              <span>• اطمینان میانگین: {(avgConfidence * 100).toFixed(0)}%</span>
            </div>
          )}
        </div>

        {/* Recommendations List */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg font-medium">خطا در دریافت توصیه‌ها</p>
            <p className="text-sm mt-1 text-surface-500">اتصال به سرور را بررسی کنید</p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm transition-colors"
            >
              تلاش مجدد
            </button>
          </div>
        ) : recommendations.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">📋</p>
            <p className="text-lg">هیچ توصیه‌ای یافت نشد</p>
            <p className="text-sm mt-1">توصیه‌ها از طریق API یا پنل مدیریت ایجاد می‌شوند</p>
            <div className="flex justify-center gap-3 mt-6">
              <Link
                href="/fundamental"
                className="px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-200 rounded-lg text-sm transition-colors"
              >
                تحلیل بنیادی
              </Link>
              <Link
                href="/signals"
                className="px-4 py-2 bg-surface-800 hover:bg-surface-700 text-surface-200 rounded-lg text-sm transition-colors"
              >
                سیگنال‌ها
              </Link>
            </div>
          </div>
        ) : (
          <>
            {/* Card-style list */}
            <div className="space-y-3">
              {filtered.map((rec) => {
                const upside = rec.potential_return_pct ?? (rec.target_price && rec.current_price
                  ? ((rec.target_price - rec.current_price) / rec.current_price) * 100
                  : 0);

                return (
                  <div
                    key={rec.id}
                    className="glass-card p-4 hover:bg-surface-800/50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Left side: Symbol + Action */}
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <ActionBadge action={rec.action} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/symbol/${encodeURIComponent(rec.symbol)}`}
                              className="text-base font-bold text-surface-100 hover:text-primary-300 transition-colors"
                            >
                              {rec.symbol}
                            </Link>
                            {rec.risk_level && (
                              <span className={`text-[10px] font-mono ${RISK_LABELS[rec.risk_level]?.color ?? "text-surface-500"}`}>
                                {RISK_LABELS[rec.risk_level]?.label ?? rec.risk_level}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs text-surface-500 flex-wrap">
                            <span>💰 {formatNumber(rec.current_price)}</span>
                            {rec.target_price && <span>🎯 {formatNumber(rec.target_price)}</span>}
                            <ReturnBadge pct={upside} />
                            <span>•</span>
                            <span>{HORIZON_LABELS[rec.horizon] || rec.horizon || "—"}</span>
                            {rec.analyst && (
                              <>
                                <span>•</span>
                                <span>👤 {rec.analyst}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Right side: Confidence + Date */}
                      <div className="text-right shrink-0 min-w-[120px]">
                        <div className="text-xs text-surface-500 mb-1">اطمینان</div>
                        <ConfidenceBar value={rec.confidence ?? 0} />
                        <div className="flex items-center justify-between mt-1.5 text-[10px] text-surface-600">
                          <span>{formatDateShamsi(rec.generated_at)}</span>
                          {rec.strategy && <span>{STRATEGY_LABELS[rec.strategy] || rec.strategy}</span>}
                        </div>
                      </div>
                    </div>

                    {/* Rationale */}
                    {rec.rationale && (
                      <div className="mt-3 pt-3 border-t border-surface-700/50 text-sm text-surface-400 leading-relaxed">
                        {rec.rationale}
                        {rec.tags && rec.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {rec.tags.map((tag, i) => (
                              <span
                                key={i}
                                className="text-[10px] bg-surface-800 text-surface-500 px-2 py-0.5 rounded"
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-2">
                <p className="text-xs text-surface-500">
                  صفحه {page} از {totalPages} — {total.toLocaleString()} توصیه
                </p>
                <div className="flex gap-1">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page <= 1}
                    className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    ← قبلی
                  </button>

                  {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (page <= 3) {
                      pageNum = i + 1;
                    } else if (page >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = page - 2 + i;
                    }
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setPage(pageNum)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          page === pageNum
                            ? "bg-primary-600 text-white shadow-lg"
                            : "bg-surface-800 text-surface-400 hover:text-surface-200"
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}

                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page >= totalPages}
                    className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    بعدی →
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Quick Links */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/signals" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← سیگنال‌ها
          </Link>
          <Link href="/analysis" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            تحلیل بازار
          </Link>
          <Link href="/fundamental" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            تحلیل بنیادی
          </Link>
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            بک‌تست
          </Link>
        </div>

        {/* Legend */}
        <div className="glass-card p-3 text-xs text-surface-500">
          <p className="font-medium text-surface-400 mb-1">راهنما</p>
          <div className="flex flex-wrap gap-4">
            {ACTION_TYPES.map((action) => (
              <span key={action} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${getActionColor(action)}`}>
                <span>{getActionIcon(action)}</span>
                <span>{getActionLabel(action)}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
