"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet, apiPost } from "@/lib/api";
import { toast } from "sonner";
import type { Fund } from "../page";

const AreaChartCard = dynamic(() => import("@/components/charts/AreaChartCard"), {
  ssr: false,
  loading: () => <div className="h-64 bg-surface-800/30 animate-pulse rounded-xl" />,
});

interface NavPoint {
  date: string;
  nav: number;
  source?: string;
}

interface FundDetail extends Fund {
  found?: boolean;
  error?: string;
  nav_history?: NavPoint[];
  nav_history_points?: number;
  analysis?: {
    symbol: string;
    name: string;
    scores: {
      financial: number;
      liquidity: number;
      management: number;
      risk: number;
      cost: number;
      transparency: number;
      total: number;
    };
    recommendation: string;
    risk_level: string;
    issues_count: number;
    summary: string;
  };
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatNum(v: number | null | undefined): string {
  if (!v) return "—";
  return v.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

function fmtMoney(v: number | null | undefined): string {
  if (!v) return "—";
  if (v >= 1_000_000_000_000) return (v / 1_000_000_000_000).toFixed(2) + " هزار میلیارد";
  if (v >= 1_000_000_000) return (v / 1_000_000_000).toFixed(2) + " میلیارد";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + " میلیون";
  return v.toLocaleString("fa-IR");
}

const REC_LABELS: Record<string, string> = {
  STRONG_BUY: "خرید قوی",
  BUY: "خرید",
  WATCHLIST: "تحت نظر",
  HOLD: "نگهداری",
  REDUCE: "کاهش",
  SELL: "فروش",
  AVOID: "اجتناب",
};

const REC_COLORS: Record<string, string> = {
  STRONG_BUY: "text-accent-emerald bg-accent-emerald/15",
  BUY: "text-accent-emerald bg-accent-emerald/10",
  WATCHLIST: "text-accent-amber bg-accent-amber/15",
  HOLD: "text-surface-300 bg-surface-600/25",
  REDUCE: "text-accent-rose bg-accent-rose/15",
  SELL: "text-accent-rose bg-accent-rose/20",
  AVOID: "text-accent-rose bg-accent-rose/25",
};

const RISK_LABELS: Record<string, string> = {
  LOW: "کم",
  MEDIUM: "متوسط",
  HIGH: "زیاد",
  CRITICAL: "بحرانی",
};

const RISK_COLORS: Record<string, string> = {
  LOW: "text-accent-emerald bg-accent-emerald/15",
  MEDIUM: "text-accent-amber bg-accent-amber/15",
  HIGH: "text-accent-rose bg-accent-rose/15",
  CRITICAL: "text-accent-rose bg-accent-rose/25",
};

const DIM_LABELS: { key: string; label: string }[] = [
  { key: "financial", label: "مالی" },
  { key: "liquidity", label: "نقدشوندگی" },
  { key: "management", label: "مدیریت" },
  { key: "risk", label: "ریسک" },
  { key: "cost", label: "هزینه" },
  { key: "transparency", label: "شفافیت" },
];

function StatBox({ label, value, sub, tone = "default" }: { label: string; value: string; sub?: string; tone?: "default" | "pos" | "neg" | "accent" }) {
  const toneClass =
    tone === "pos" ? "text-accent-emerald" : tone === "neg" ? "text-accent-rose" : tone === "accent" ? "text-primary-300" : "text-surface-100";
  return (
    <div className="glass-card p-3">
      <p className="text-[10px] text-surface-500 mb-1">{label}</p>
      <p className={`font-mono text-sm font-bold ${toneClass}`} dir="ltr" style={{ textAlign: "right" }}>
        {value}
      </p>
      {sub && <p className={`text-[10px] mt-0.5 ${tone === "pos" ? "text-accent-emerald/70" : tone === "neg" ? "text-accent-rose/70" : "text-surface-600"}`}>{sub}</p>}
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function FundDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params?.symbol ?? "");
  const qc = useQueryClient();
  const [updating, setUpdating] = useState(false);

  const { data: detail, isLoading, error } = useQuery({
    queryKey: ["fund-detail", symbol],
    queryFn: async (): Promise<FundDetail> => {
      const res = await apiGet<FundDetail>(`/funds/${encodeURIComponent(symbol)}`);
      return res ?? { symbol, found: false };
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const chartData = useMemo(() => {
    return (detail?.nav_history ?? []).map((n) => ({
      time: n.date,
      date: n.date,
      value: n.nav,
    }));
  }, [detail?.nav_history]);

  const premiumPct = useMemo(() => {
    // صرف/کسر فقط وقتی معنادار است که NAV واقعی (nav_record) در دست باشد؛
    // اگر NAV فقط جانشین قیمت باشد، تفاضل همیشه ≈ ۰ و گمراه‌کننده است.
    if (
      detail &&
      detail.nav_source === "nav_record" &&
      detail.price_last > 0 &&
      detail.nav > 0
    ) {
      return ((detail.price_last - detail.nav) / detail.nav) * 100;
    }
    return null;
  }, [detail]);

  async function handleUpdate() {
    setUpdating(true);
    try {
      const res = await apiPost<{ symbol: string; error?: string }>(`/funds/${encodeURIComponent(symbol)}/update`);
      if (res?.error) {
        toast.error(res.error);
      } else {
        toast.success("داده‌های صندوق به‌روزرسانی شد");
        qc.invalidateQueries({ queryKey: ["fund-detail", symbol] });
        qc.invalidateQueries({ queryKey: ["funds"] });
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا در به‌روزرسانی");
    } finally {
      setUpdating(false);
    }
  }

  const analysis = detail?.analysis;

  return (
    <AppLayout
      title={detail?.found === false ? "صندوق یافت نشد" : (detail?.name || "صندوق")}
      subtitle={`${symbol} — تمام اطلاعات صندوق`}
      header={
        <div className="flex items-center gap-2 mb-3">
          <Link
            href="/funds"
            className="text-xs text-surface-400 hover:text-primary-300 transition-colors bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5"
          >
            → بازگشت به صندوق‌ها
          </Link>
          {detail?.found && (
            <button
              onClick={handleUpdate}
              disabled={updating}
              className="text-xs font-bold text-primary-300 hover:text-primary-200 bg-primary-600/10 hover:bg-primary-600/20 border border-primary-600/30 rounded-lg px-3 py-1.5 transition-all disabled:opacity-50"
            >
              {updating ? "در حال به‌روزرسانی..." : "🔄 به‌روزرسانی از BrsApi"}
            </button>
          )}
        </div>
      }
    >
      {/* ── Loading / Error ── */}
      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      )}

      {error && !isLoading && (
        <div className="glass-card p-10 text-center text-accent-rose">
          <p className="text-4xl mb-2">⚠️</p>
          <p className="text-sm">خطا در دریافت اطلاعات صندوق</p>
        </div>
      )}

      {!isLoading && detail?.found === false && (
        <div className="glass-card p-10 text-center text-surface-500">
          <p className="text-4xl mb-2">🔍</p>
          <p className="text-sm">صندوقی با نماد «{symbol}» یافت نشد</p>
          <Link href="/funds" className="inline-block mt-3 text-xs text-primary-300 hover:underline">بازگشت به فهرست صندوق‌ها</Link>
        </div>
      )}

      {!isLoading && detail?.found !== false && detail && (
        <>
          {/* ── Header badges ── */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-[10px] px-2 py-1 rounded-full font-bold bg-primary-600/20 text-primary-300">
              {detail.fund_type || "نامشخص"}
            </span>
            <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${
              detail.market === "tse" ? "bg-primary-600/20 text-primary-300" : "bg-accent-gold/15 text-accent-gold"
            }`}>
              {detail.market === "tse" ? "بورس تهران" : "بورس کالا"}
            </span>
            {detail.isin && (
              <span className="text-[10px] px-2 py-1 rounded-full font-mono bg-surface-800 text-surface-400" dir="ltr">
                ISIN: {detail.isin}
              </span>
            )}
            {detail.snapshot_date && (
              <span className="text-[10px] px-2 py-1 rounded-full bg-surface-800 text-surface-400">
                اسنپ‌شات: {detail.snapshot_date}
              </span>
            )}
          </div>

          {/* ── Key stats grid ── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
            <StatBox
              label="NAV"
              value={formatNum(detail.nav)}
              tone="accent"
              sub={
                detail.nav_source === "nav_record"
                  ? detail.nav_date
                    ? `واقعی — ${detail.nav_date}`
                    : "واقعی (صدور/ابطال)"
                  : "تقریبی (آخرین قیمت)"
              }
            />
            <StatBox
              label="تغییر NAV"
              value={`${detail.nav_change_pct >= 0 ? "+" : ""}${detail.nav_change_pct?.toFixed(2)}%`}
              sub={`${detail.nav_change >= 0 ? "+" : ""}${formatNum(detail.nav_change)}`}
              tone={detail.nav_change_pct >= 0 ? "pos" : "neg"}
            />
            <StatBox label="قیمت آخرین" value={formatNum(detail.price_last)} />
            <StatBox label="قیمت پایانی" value={formatNum(detail.price_close)} />
            <StatBox label="قیمت دیروز" value={formatNum(detail.price_yesterday)} />
            <StatBox
              label="صرف/کسر (Premium)"
              value={premiumPct !== null ? `${premiumPct >= 0 ? "+" : ""}${premiumPct.toFixed(2)}%` : "—"}
              sub={premiumPct === null ? "NAV واقعی موجود نیست" : undefined}
              tone={premiumPct !== null && premiumPct > 0 ? "pos" : premiumPct !== null && premiumPct < 0 ? "neg" : "default"}
            />
            <StatBox label="بازه قیمت روز" value={`${formatNum(detail.price_min)} – ${formatNum(detail.price_max)}`} />
            <StatBox label="حجم معاملات" value={fmtMoney(detail.trade_volume)} />
            <StatBox label="ارزش معاملات" value={fmtMoney(detail.trade_value)} />
            <StatBox label="تعداد معاملات" value={formatNum(detail.trade_count)} />
            <StatBox label="تعداد واحد" value={fmtMoney(detail.shares_count)} />
            <StatBox label="حجم مبنا" value={fmtMoney(detail.base_volume)} />
            <StatBox label="ارزش بازار" value={fmtMoney(detail.market_value)} tone="accent" />
            <StatBox
              label="خرید حقیقی"
              value={formatNum(detail.buy_real_volume)}
              tone={detail.buy_real_volume >= detail.sell_real_volume ? "pos" : "neg"}
            />
            <StatBox
              label="فروش حقیقی"
              value={formatNum(detail.sell_real_volume)}
              tone={detail.sell_real_volume > detail.buy_real_volume ? "pos" : "neg"}
            />
            <StatBox label="خرید حقوقی" value={formatNum(detail.buy_legal_volume)} />
            <StatBox label="فروش حقوقی" value={formatNum(detail.sell_legal_volume)} />
          </div>

          {/* ── NAV history chart ── */}
          <div className="mb-5">
            <AreaChartCard
              title="تاریخچه NAV"
              data={chartData}
              dataKey="value"
              height={260}
              strokeColor="#10b981"
              gradientId="fundNavGrad"
              primaryLabel="NAV"
              yAxisLabel="NAV (ریال)"
              yAxisFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v))}
              tooltipFormatter={(v: number) => v.toLocaleString("fa-IR", { maximumFractionDigits: 0 })}
              showAverage
              showMinMax
            />
            {chartData.length === 0 && !isLoading && (
              <p className="text-xs text-surface-600 mt-1">تاریخچه NAV برای این صندوق موجود نیست (بعد از همگام‌سازی NAV ظاهر می‌شود).</p>
            )}
          </div>

          {/* ── ۶بعدی تحلیل ── */}
          {analysis && (
            <Card
              title="تحلیل ۶‌بعدی صندوق"
              actions={
                <div className="flex gap-2">
                  <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${REC_COLORS[analysis.recommendation] || REC_COLORS.HOLD}`}>
                    {REC_LABELS[analysis.recommendation] || analysis.recommendation}
                  </span>
                  <span className={`text-[10px] px-2 py-1 rounded-full font-bold ${RISK_COLORS[analysis.risk_level] || RISK_COLORS.MEDIUM}`}>
                    ریسک: {RISK_LABELS[analysis.risk_level] || analysis.risk_level}
                  </span>
                </div>
              }
            >
              <p className="text-xs text-surface-400 mb-4">{analysis.summary}</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {DIM_LABELS.map((dim) => {
                  const val = analysis.scores[dim.key as keyof typeof analysis.scores] ?? 0;
                  const color =
                    val >= 70 ? "#10b981" : val >= 50 ? "#f59e0b" : "#f43f5e";
                  return (
                    <div key={dim.key} className="bg-surface-800/40 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] text-surface-400">{dim.label}</span>
                        <span className="text-xs font-mono font-bold" style={{ color }}>{val}</span>
                      </div>
                      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${val}%`, backgroundColor: color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </>
      )}
    </AppLayout>
  );
}
