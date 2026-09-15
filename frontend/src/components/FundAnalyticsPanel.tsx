"use client";

/**
 * 🏦 FundAnalyticsPanel — پنل تحلیل Enterprise صندوق (بخش ۷).
 *
 * ۸ تب تحلیلی:
 *  ۱. نمای کلی و کارت‌های خلاصه   ۲. روند NAV      ۳. ترکیب دارایی
 *  ۴. تحلیل گزارش‌های کدال        ۵. گروه‌بندی صنعتی ۶. رتبه‌بندی
 *  ۷. بک‌تست                      ۸. پیش‌بینی و یادگیری ماشین
 *
 * وضعیت‌ها: Live / Estimated / Stale + Progress غیرمسدودکننده هنگام
 * First-time Discovery. داده همیشه از API v2 (Read-Through) می‌آید.
 */

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="h-64 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const PieChartCard = dynamic(() => import("@/components/charts/PieChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});
const BarChartCard = dynamic(() => import("@/components/charts/BarChartCard"), {
  ssr: false,
  loading: () => <div className="h-56 bg-surface-800/30 animate-pulse rounded-xl" />,
});

// ── Types ───────────────────────────────────────────────────────────────────

type Freshness = "live" | "estimated" | "stale" | string;

interface UniverseFund {
  fund_id: string;
  symbol: string;
  name: string;
  isin: string;
  market: string;
  fund_type_hint: string;
}

interface NavPoint {
  date: string;
  nav_issue?: number | null;
  nav_redemption?: number | null;
  nav_statistical?: number | null;
}

interface Holding {
  holding_type: string;
  instrument_symbol: string | null;
  instrument_name: string | null;
  quantity: number | null;
  market_value: number | null;
  weight_pct: number | null;
}

interface Diff {
  symbol: string;
  current_period: string | null;
  prev_weight_pct: number | null;
  curr_weight_pct: number | null;
  weight_change_pct: number | null;
  flow_direction: string | null;
}

interface Valuation {
  nav_estimated: number | null;
  nav_official: number | null;
  coverage_pct: number;
  equity_value: number;
  cash_and_fixed_income: number;
  total_value: number;
  units_outstanding: number | null;
  freshness: Freshness;
}

interface ScoreData {
  total: number;
  components: { return: number; risk: number; liquidity: number; stability: number };
  metrics: {
    total_return_1y_pct: number | null;
    volatility_annual_pct: number | null;
    sharpe: number | null;
    sortino: number | null;
    max_drawdown_pct: number | null;
    calmar: number | null;
    alpha_annual_pct: number | null;
    beta: number | null;
    tracking_error_pct: number | null;
  };
  points_used: number;
}

interface BacktestStrategy {
  strategy: string;
  total_invested: number;
  final_value: number;
  total_return_pct: number;
  annualized_return_pct: number | null;
  max_drawdown_pct: number;
  trade_count: number;
}

interface BacktestData {
  strategies: Record<string, BacktestStrategy>;
  available: boolean;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

const FRESHNESS_META: Record<string, { label: string; cls: string; dot: string }> = {
  live: { label: "Live · لحظه‌ای", cls: "bg-accent-emerald/15 text-accent-emerald", dot: "bg-accent-emerald" },
  estimated: { label: "Estimated · تخمینی", cls: "bg-accent-amber/15 text-accent-amber", dot: "bg-accent-amber" },
  stale: { label: "Stale · کهنه", cls: "bg-accent-rose/15 text-accent-rose", dot: "bg-accent-rose" },
};

function FreshnessChip({ freshness }: { freshness: Freshness | undefined }) {
  if (!freshness) return null;
  const meta = FRESHNESS_META[freshness] ?? FRESHNESS_META.stale;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[9px] px-2 py-0.5 rounded-full font-bold ${meta.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot} ${freshness === "live" ? "animate-pulse" : ""}`} />
      {meta.label}
    </span>
  );
}

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + " میلیارد";
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + " میلیون";
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

const HOLDING_TYPE_LABELS: Record<string, string> = {
  equity: "سهام",
  fixed_income: "اوراق با درآمد ثابت",
  deposit: "سپرده بانکی",
  gold: "طلا و کالا",
  derivative: "مشتقات",
  cash: "نقد",
  other: "سایر",
};

const FLOW_LABELS: Record<string, { label: string; cls: string }> = {
  in: { label: "ورود پول", cls: "text-accent-emerald" },
  out: { label: "خروج پول", cls: "text-accent-rose" },
  new: { label: "پوزیشن جدید", cls: "text-accent-cyan" },
  exited: { label: "خروج کامل", cls: "text-accent-rose" },
  hold: { label: "بدون تغییر", cls: "text-surface-400" },
};

const STRATEGY_LABELS: Record<string, string> = {
  buy_hold: "خرید و نگهداری",
  dca_monthly: "میانگین‌گیری ماهانه (DCA)",
  dip_buying: "خرید در افت",
};

// ── Main ────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "overview", label: "نمای کلی" },
  { id: "nav", label: "روند NAV" },
  { id: "composition", label: "ترکیب دارایی" },
  { id: "codal", label: "گزارش‌های کدال" },
  { id: "sector", label: "گروه‌بندی صنعتی" },
  { id: "ranking", label: "رتبه‌بندی" },
  { id: "backtest", label: "بک‌تست" },
  { id: "ml", label: "پیش‌بینی و ML" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function FundAnalyticsPanel({ symbol }: { symbol: string; fundName?: string }) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const fundId = `tse:${symbol}`;

  // ── Queries (همه از v2 — Read-Through خودکار) ──
  const { data: universe, isLoading: universeLoading } = useQuery({
    queryKey: ["fund-v2-universe"],
    queryFn: async () => {
      const res = await apiGet<{ data: { funds: UniverseFund[]; freshness: Freshness } }>("/funds/v2/universe");
      return res?.data ?? { funds: [], freshness: "stale" as Freshness };
    },
    staleTime: 300_000,
  });

  const { data: navData } = useQuery({
    queryKey: ["fund-v2-nav", fundId],
    queryFn: async () => {
      const res = await apiGet<{ data: { points: NavPoint[]; freshness: Freshness } }>(
        `/funds/v2/${encodeURIComponent(fundId)}/nav-history`
      );
      return res?.data ?? { points: [], freshness: "stale" as Freshness };
    },
    staleTime: 300_000,
  });

  const { data: holdingsData } = useQuery({
    queryKey: ["fund-v2-holdings", fundId],
    queryFn: async () => {
      const res = await apiGet<{ data: { holdings: Holding[]; freshness: Freshness; diffs: Diff[] } }>(
        `/funds/v2/${encodeURIComponent(fundId)}/holdings`
      );
      return res?.data ?? { holdings: [], freshness: "stale" as Freshness, diffs: [] };
    },
    staleTime: 600_000,
  });

  const { data: valuation } = useQuery({
    queryKey: ["fund-v2-valuation", fundId],
    queryFn: async () => {
      const res = await apiGet<{ data: Valuation }>(`/funds/v2/${encodeURIComponent(fundId)}/valuation`);
      return res?.data ?? null;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const { data: score, isLoading: scoreLoading } = useQuery({
    queryKey: ["fund-v2-score", fundId],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: ScoreData }>(`/funds/v2/${encodeURIComponent(fundId)}/score`);
        return res?.success ? res.data : null;
      } catch {
        return null;
      }
    },
    staleTime: 600_000,
  });

  const { data: backtest } = useQuery({
    queryKey: ["fund-v2-backtest", fundId],
    queryFn: async () => {
      try {
        const res = await apiGet<{ data: BacktestData }>(`/funds/v2/${encodeURIComponent(fundId)}/backtest`);
        return res?.data ?? null;
      } catch {
        return null;
      }
    },
    staleTime: 3_600_000,
  });

  const { data: rankings } = useQuery({
    queryKey: ["fund-v2-rankings"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ data: { rankings: { rank: number; fund_id: string; symbol: string; total_score: number; sharpe: number | null }[] } }>(
          "/funds/v2/rankings?limit=50"
        );
        return res?.data?.rankings ?? [];
      } catch {
        return [];
      }
    },
    staleTime: 600_000,
  });

  // ── Derived data ──
  const fundMeta = useMemo(
    () => universe?.funds.find((f) => f.symbol === symbol),
    [universe, symbol]
  );
  const isDiscovering = universeLoading || (universe?.funds.length ?? 0) === 0;

  const navChartData = useMemo(
    () =>
      (navData?.points ?? []).map((p) => ({
        date: p.date,
        value: Number(p.nav_statistical ?? p.nav_redemption ?? p.nav_issue ?? 0),
      })),
    [navData]
  );

  const compositionData = useMemo(() => {
    const byType: Record<string, number> = {};
    for (const h of holdingsData?.holdings ?? []) {
      const label = HOLDING_TYPE_LABELS[h.holding_type] ?? h.holding_type;
      byType[label] = (byType[label] ?? 0) + Number(h.market_value ?? 0);
    }
    const colors = ["#10b981", "#06b6d4", "#f59e0b", "#eab308", "#a78bfa", "#64748b", "#f43f5e"];
    return Object.entries(byType)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value], i) => ({ name, value, color: colors[i % colors.length] }));
  }, [holdingsData]);

  const topHoldings = useMemo(
    () => (holdingsData?.holdings ?? []).filter((h) => h.holding_type === "equity").slice(0, 10),
    [holdingsData]
  );

  const sectorData = useMemo(() => {
    // گروه‌بندی ساده بر اساس نوع دارایی (در نبود سکتور نماد)
    const bySym = (holdingsData?.holdings ?? []).filter((h) => h.holding_type === "equity");
    const colors = ["#10b981", "#06b6d4", "#f59e0b", "#a78bfa", "#f43f5e", "#eab308", "#3b82f6", "#ec4899"];
    return bySym.slice(0, 8).map((h, i) => ({
      name: h.instrument_name || h.instrument_symbol || "—",
      value: Number(h.weight_pct ?? 0),
      color: colors[i % colors.length],
    }));
  }, [holdingsData]);

  const valuationPct = useMemo(() => {
    if (!valuation?.nav_estimated || !valuation?.nav_official) return null;
    return ((valuation.nav_estimated - valuation.nav_official) / valuation.nav_official) * 100;
  }, [valuation]);

  // ── Loading / Discovery state ──
  if (isDiscovering) {
    return (
      <Card title="تحلیل Enterprise صندوق">
        <div className="py-8 text-center">
          <div className="inline-flex items-center gap-2 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-primary-400 animate-ping" />
            <span className="text-sm text-surface-300 font-bold">
              در حال کشف و همگام‌سازی Universe صندوق‌ها…
            </span>
          </div>
          <p className="text-xs text-surface-500 mb-5">
            اولین بار داده‌ها از منبع رسمی دریافت و در دیتابیس ذخیره می‌شود؛ این فرآیند غیرمسدودکننده است.
          </p>
          <div className="space-y-3 max-w-md mx-auto">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
          <div className="mt-5 h-1.5 w-64 mx-auto bg-surface-800 rounded-full overflow-hidden">
            <div className="h-full w-1/3 bg-primary-500/70 rounded-full animate-[shimmer_1.5s_infinite]" />
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title="تحلیل Enterprise صندوق"
      actions={
        <div className="flex items-center gap-2">
          {fundMeta && (
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-surface-800 text-surface-400">
              {fundMeta.fund_type_hint}
            </span>
          )}
          <FreshnessChip freshness={valuation?.freshness ?? navData?.freshness} />
        </div>
      }
    >
      {/* ── Tabs ── */}
      <div className="flex gap-1 flex-wrap border-b border-surface-700 pb-2 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === t.id
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                : "text-surface-400 hover:text-surface-200 hover:bg-surface-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══ ۱. نمای کلی ═══ */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatBox
              label="NAV تخمینی (لحظه‌ای)"
              value={valuation?.nav_estimated ? fmt(valuation.nav_estimated) : "—"}
              sub={
                valuation?.coverage_pct !== undefined
                  ? `پوشش داده: ${valuation.coverage_pct}٪`
                  : undefined
              }
              tone="accent"
            />
            <StatBox
              label="NAV رسمی"
              value={valuation?.nav_official ? fmt(valuation.nav_official) : "—"}
              sub={valuationPct !== null ? `اختلاف: ${fmtPct(valuationPct)}` : undefined}
            />
            <StatBox
              label="ارزش کل دارایی"
              value={valuation ? fmt(valuation.total_value) : "—"}
            />
            <StatBox
              label="امتیاز کمی"
              value={score ? score.total.toFixed(1) : "—"}
              sub={score ? `${score.points_used} نقطه NAV` : "داده ناکافی"}
              tone={score ? (score.total >= 70 ? "pos" : score.total < 40 ? "neg" : "default") : "default"}
            />
          </div>

          {score && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MiniMetric label="شارپ" value={score.metrics.sharpe?.toFixed(2)} />
              <MiniMetric label="سورتینو" value={score.metrics.sortino?.toFixed(2)} />
              <MiniMetric label="حداکثر افت" value={score.metrics.max_drawdown_pct ? `${score.metrics.max_drawdown_pct.toFixed(1)}%` : undefined} />
              <MiniMetric label="بتا (شاخص کل)" value={score.metrics.beta?.toFixed(2)} />
            </div>
          )}

          {/* وزن‌های امتیاز */}
          {score && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <ScoreBar label="بازدهی" value={score.components.return} />
              <ScoreBar label="ریسک" value={score.components.risk} />
              <ScoreBar label="نقدشوندگی" value={score.components.liquidity} />
              <ScoreBar label="ثبات" value={score.components.stability} />
            </div>
          )}
          {scoreLoading && <Skeleton className="h-16 w-full rounded-lg" />}
        </div>
      )}

      {/* ═══ ۲. روند NAV ═══ */}
      {activeTab === "nav" && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <FreshnessChip freshness={navData?.freshness} />
            <span className="text-[10px] text-surface-500">
              صدور/ابطال + قیمت آماری — منبع دیتابیس داخلی (Read-Through)
            </span>
          </div>
          {navChartData.length > 1 ? (
            <AreaChartCard
              title=""
              data={navChartData}
              height={280}
              strokeColor="#10b981"
              gradientId="fundV2NavGrad"
              primaryLabel="NAV"
              yAxisFormatter={(v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v.toLocaleString("fa-IR"))}
              tooltipFormatter={(v: number) => v.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
              showMinMax
            />
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">
              تاریخچه NAV کافی موجود نیست — پس از اولین همگام‌سازی ظاهر می‌شود.
            </p>
          )}
        </div>
      )}

      {/* ═══ ۳. ترکیب دارایی ═══ */}
      {activeTab === "composition" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <FreshnessChip freshness={holdingsData?.freshness} />
            <span className="text-[10px] text-surface-500">
              بر اساس آخرین گزارش ماهانه کدال
            </span>
          </div>
          {compositionData.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              <PieChartCard title="ترکیب دارایی بر اساس نوع" data={compositionData} />
              <div className="space-y-1.5">
                {topHoldings.map((h, i) => (
                  <div key={`${h.instrument_symbol}-${i}`} className="flex items-center gap-2 bg-surface-800/40 rounded-lg px-3 py-2">
                    <span className="font-bold text-surface-200 text-xs w-20">{h.instrument_symbol}</span>
                    <span className="flex-1 text-[10px] text-surface-500 truncate">{h.instrument_name}</span>
                    <span className="font-mono text-xs text-primary-300">{fmtPct(h.weight_pct)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">
              گزارش ترکیب دارایی موجود نیست — به‌صورت خودکار از کدال دریافت می‌شود.
            </p>
          )}
        </div>
      )}

      {/* ═══ ۴. گزارش‌های کدال ═══ */}
      {activeTab === "codal" && (
        <div className="space-y-3">
          <p className="text-xs text-surface-500">
            ردیابی ورود/خروج پول صندوق بین دو گزارش ماهانه متوالی
          </p>
          {(holdingsData?.diffs ?? []).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="text-right py-2 px-2">نماد</th>
                    <th className="text-right py-2 px-2">وزن قبل</th>
                    <th className="text-right py-2 px-2">وزن فعلی</th>
                    <th className="text-right py-2 px-2">تغییر</th>
                    <th className="text-right py-2 px-2">جریان</th>
                  </tr>
                </thead>
                <tbody>
                  {holdingsData!.diffs.map((d, i) => {
                    const flow = FLOW_LABELS[d.flow_direction ?? "hold"] ?? FLOW_LABELS.hold;
                    return (
                      <tr key={`${d.symbol}-${i}`} className="border-b border-surface-800/50 hover:bg-white/[0.02]">
                        <td className="py-2 px-2 font-bold text-surface-200">{d.symbol}</td>
                        <td className="py-2 px-2 font-mono text-surface-400">{fmtPct(d.prev_weight_pct)}</td>
                        <td className="py-2 px-2 font-mono text-surface-300">{fmtPct(d.curr_weight_pct)}</td>
                        <td className={`py-2 px-2 font-mono font-bold ${(d.weight_change_pct ?? 0) >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                          {fmtPct(d.weight_change_pct)}
                        </td>
                        <td className={`py-2 px-2 ${flow.cls}`}>{flow.label}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">
              هنوز دو دوره گزارش متوالی ثبت نشده است.
            </p>
          )}
        </div>
      )}

      {/* ═══ ۵. گروه‌بندی صنعتی ═══ */}
      {activeTab === "sector" && (
        <div>
          {sectorData.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              <PieChartCard title="وزن بزرگ‌ترین دارایی‌های سهامی" data={sectorData} />
              <BarChartCard
                title="وزن درصدی دارایی‌ها"
                data={sectorData.map((s) => ({ date: s.name, value: s.value }))}
                height={220}
                valueLabel="وزن ٪"
              />
            </div>
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">داده گروه‌بندی موجود نیست.</p>
          )}
        </div>
      )}

      {/* ═══ ۶. رتبه‌بندی ═══ */}
      {activeTab === "ranking" && (
        <div>
          {(rankings ?? []).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700">
                    <th className="text-right py-2 px-2">رتبه</th>
                    <th className="text-right py-2 px-2">صندوق</th>
                    <th className="text-right py-2 px-2">امتیاز</th>
                    <th className="text-right py-2 px-2">شارپ</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings!.map((r) => {
                    const isThisFund = r.symbol === symbol;
                    return (
                      <tr
                        key={r.fund_id}
                        className={`border-b border-surface-800/50 ${isThisFund ? "bg-primary-600/10" : "hover:bg-white/[0.02]"}`}
                      >
                        <td className="py-2 px-2 font-mono font-bold text-primary-300">{r.rank}</td>
                        <td className="py-2 px-2 text-surface-200">
                          {r.symbol}
                          {isThisFund && <span className="text-[8px] text-primary-300 mr-1">(این صندوق)</span>}
                        </td>
                        <td className="py-2 px-2 font-mono text-surface-300">{r.total_score?.toFixed(1)}</td>
                        <td className="py-2 px-2 font-mono text-surface-400">{r.sharpe?.toFixed(2) ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">
              رتبه‌بندی پس از امتیازدهی دوره‌ای اول ظاهر می‌شود.
            </p>
          )}
        </div>
      )}

      {/* ═══ ۷. بک‌تست ═══ */}
      {activeTab === "backtest" && (
        <div>
          {backtest?.available ? (
            <div className="grid md:grid-cols-3 gap-3">
              {Object.entries(backtest.strategies).map(([key, s]) => (
                <div key={key} className="bg-surface-800/40 rounded-xl p-4">
                  <p className="text-xs font-bold text-surface-200 mb-3">{STRATEGY_LABELS[key] ?? key}</p>
                  <div className="space-y-2 text-[11px]">
                    <Row label="سرمایه‌گذاری" value={fmt(s.total_invested)} />
                    <Row label="ارزش نهایی" value={fmt(s.final_value)} tone={s.final_value >= s.total_invested ? "pos" : "neg"} />
                    <Row
                      label="بازدهی کل"
                      value={fmtPct(s.total_return_pct)}
                      tone={s.total_return_pct >= 0 ? "pos" : "neg"}
                    />
                    <Row
                      label="بازدهی سالانه"
                      value={s.annualized_return_pct !== null ? fmtPct(s.annualized_return_pct) : "—"}
                      tone={(s.annualized_return_pct ?? 0) >= 0 ? "pos" : "neg"}
                    />
                    <Row label="حداکثر افت" value={`${s.max_drawdown_pct.toFixed(1)}%`} tone="neg" />
                    <Row label="تعداد معاملات" value={String(s.trade_count)} />
                  </div>
                </div>
              ))}
              <p className="md:col-span-3 text-[10px] text-surface-600 mt-1">
                شبیه‌سازی با کارمزد واقعی و تقویم بازار ایران — بدون استفاده از داده‌های آینده (No Look-Ahead Bias).
              </p>
            </div>
          ) : (
            <p className="text-xs text-surface-500 py-8 text-center">
              بک‌تست به حداقل ۳۰ نقطه NAV نیاز دارد.
            </p>
          )}
        </div>
      )}

      {/* ═══ ۸. پیش‌بینی و ML ═══ */}
      {activeTab === "ml" && (
        <div className="py-8 text-center">
          <p className="text-3xl mb-2">🤖</p>
          <p className="text-sm font-bold text-surface-300 mb-1">ماژول پیش‌بینی و یادگیری ماشین</p>
          <p className="text-xs text-surface-500 max-w-md mx-auto">
            مدل‌های پیش‌بینی NAV روی تاریخچه این صندوق پس از تکمیل P0 (تاریخچه کامل و امتیازدهی دوره‌ای)
            فعال می‌شوند. داده‌های خام این صندوق هم‌اکنون در حال جمع‌آوری است.
          </p>
          {score && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5 max-w-2xl mx-auto">
              <MiniMetric label="آلفای سالانه" value={score.metrics.alpha_annual_pct ? fmtPct(score.metrics.alpha_annual_pct) : undefined} />
              <MiniMetric label="کالمر" value={score.metrics.calmar?.toFixed(2)} />
              <MiniMetric label="Tracking Error" value={score.metrics.tracking_error_pct ? `${score.metrics.tracking_error_pct.toFixed(1)}%` : undefined} />
              <MiniMetric label="نوسان سالانه" value={score.metrics.volatility_annual_pct ? `${score.metrics.volatility_annual_pct.toFixed(1)}%` : undefined} />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Small components ────────────────────────────────────────────────────────

function StatBox({ label, value, sub, tone = "default" }: { label: string; value: string; sub?: string; tone?: "default" | "pos" | "neg" | "accent" }) {
  const toneClass =
    tone === "pos" ? "text-accent-emerald" : tone === "neg" ? "text-accent-rose" : tone === "accent" ? "text-primary-300" : "text-surface-100";
  return (
    <div className="glass-card p-3">
      <p className="text-[10px] text-surface-500 mb-1">{label}</p>
      <p className={`font-mono text-sm font-bold ${toneClass}`} dir="ltr" style={{ textAlign: "right" }}>
        {value}
      </p>
      {sub && <p className="text-[10px] mt-0.5 text-surface-600">{sub}</p>}
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bg-surface-800/40 rounded-lg px-3 py-2">
      <p className="text-[9px] text-surface-500">{label}</p>
      <p className="font-mono text-xs font-bold text-surface-200">{value ?? "—"}</p>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 70 ? "#10b981" : value >= 50 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="bg-surface-800/40 rounded-lg p-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-surface-400">{label}</span>
        <span className="text-xs font-mono font-bold" style={{ color }}>
          {value.toFixed(0)}
        </span>
      </div>
      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function Row({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "pos" | "neg" }) {
  const toneClass = tone === "pos" ? "text-accent-emerald" : tone === "neg" ? "text-accent-rose" : "text-surface-200";
  return (
    <div className="flex items-center justify-between">
      <span className="text-surface-500">{label}</span>
      <span className={`font-mono font-bold ${toneClass}`}>{value}</span>
    </div>
  );
}
