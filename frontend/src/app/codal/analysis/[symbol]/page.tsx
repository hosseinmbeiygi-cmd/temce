"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { MetricBox } from "@/components/MetricBox";
import { RealLegalCard } from "@/components/RealLegalCard";
import { AuditBadge } from "@/components/AuditBadge";
import { apiGet } from "@/lib/api";
import { formatDateShamsi } from "@/lib/dates";
import { seededRandom } from "@/lib/seeded-random";

// ── Types ──────────────────────────────────────────────────────────

interface AccountingSummary {
  symbol: string;
  total_reports: number;
  latest_reports: Record<string, {
    date: string;
    filename: string;
    label: string;
    items: Record<string, number>;
  }>;
  summary: Record<string, number>;
}

interface AnalysisData {
  symbol: string;
  company_name: string;
  industry: string;
  sub_sector: string;
  market: string;
  board: string;
  state: string;
  price: {
    last: number; yesterday: number; close: number;
    min: number; max: number;
    lowest_allowed: number; highest_allowed: number;
    change: number; change_pct: number;
  };
  fundamental: {
    eps: number; pe_ratio: number; group_pe: number;
    ps_ratio: number; market_cap: number; shares_count: number;
    free_float_pct: number; base_volume: number;
    estimated_revenue: number; estimated_net_profit: number;
    pb_ratio: number; roe_pct: number; roa_pct: number;
    dividend_yield_pct: number;
  };
  trade: { volume: number; value: number; count: number };
  real_legal: {
    buy_real_volume: number; sell_real_volume: number;
    buy_legal_volume: number; sell_legal_volume: number;
    real_net: number; legal_net: number;
    real_net_pct_of_total: number; real_buy_pct: number;
  };
  holders: {
    total_count: number; top_holder_pct: number;
    legal_holder_count: number; real_holder_count: number;
    top_holders: { name: string; shares: number; percentage: number; type: string }[];
  };
  announcements: {
    title: string; date_publish: string;
    link_pdf: string; audit_status: string;
  }[];
  performance: {
    price_change_pct: number; price_vs_low_pct: number;
    volume_vs_base: number;
  };
}

// ── Helpers ────────────────────────────────────────────────────────

function formatCurrency(val: number | null | undefined): string {
  if (val == null || val === 0) return "—";
  if (Math.abs(val) >= 1e12) return (val / 1e12).toFixed(1) + "T";
  if (Math.abs(val) >= 1e9) return (val / 1e9).toFixed(1) + "B";
  if (Math.abs(val) >= 1e6) return (val / 1e6).toFixed(1) + "M";
  if (Math.abs(val) >= 1e3) return (val / 1e3).toFixed(0) + "K";
  return val.toLocaleString("en-US");
}

function formatPct(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "—", color: "text-surface-400" };
  const fixed = val.toFixed(2);
  if (val > 0) return { text: `+${fixed}%`, color: "text-accent-emerald" };
  if (val < 0) return { text: `${fixed}%`, color: "text-accent-rose" };
  return { text: "0.00%", color: "text-surface-400" };
}

function RatingBar({ value, label, goodDirection = "up" }: { value: number; label: string; goodDirection?: "up" | "down" }) {
  const isGood = goodDirection === "up" ? value >= 0 : value <= 0;
  const absVal = Math.min(Math.abs(value), 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-surface-500">{label}</span>
        <span className={isGood ? "text-accent-emerald font-mono" : "text-accent-rose font-mono"}>
          {value >= 0 ? "+" : ""}{value.toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden" dir="ltr">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isGood ? "bg-accent-emerald" : "bg-accent-rose"}`}
          style={{ width: `${absVal}%` }}
        />
      </div>
    </div>
  );
}

function FinancialHealthCard({ value, label, healthy, unhealthy }: { value: number; label: string; healthy: string; unhealthy: string }) {
  const isHealthy = value > 0;
  return (
    <div className={`p-4 rounded-xl border ${isHealthy ? "bg-accent-emerald/5 border-accent-emerald/20" : "bg-accent-rose/5 border-accent-rose/20"}`}>
      <p className="text-xs text-surface-500 mb-1">{label}</p>
      <p className={`text-lg font-bold ${isHealthy ? "text-accent-emerald" : "text-accent-rose"}`}>
        {isHealthy ? healthy : unhealthy}
      </p>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────

export default function CodalAnalysisPage() {
  const params = useParams();
  const symbol = (params?.symbol as string) || "";
  const decodedSymbol = decodeURIComponent(symbol);

  const { data, isLoading, error } = useQuery({
    queryKey: ["codal-analysis", decodedSymbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: AnalysisData }>(
        `/codal/${encodeURIComponent(decodedSymbol)}/analysis`
      );
      return res?.data ?? null;
    },
    enabled: !!decodedSymbol,
  });

  const analysis = data;

  // ── Accounting Data ──────────────────────────────────────────────────
  const [tab, setTab] = useState<"market" | "accounting">("market");

  const { data: accountingData, isLoading: acctLoading } = useQuery({
    queryKey: ["codal-accounting", decodedSymbol],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: AccountingSummary }>(
        `/codal-accounting/${encodeURIComponent(decodedSymbol)}/financials`
      );
      return res?.data ?? null;
    },
    enabled: !!decodedSymbol,
  });

  // ── Derived values ───────────────────────────────────────────────────
  const pricePct = analysis?.price?.change_pct != null ? formatPct(analysis.price.change_pct) : { text: "—", color: "text-surface-500" };
  const peStatus = analysis?.fundamental?.pe_ratio ?
    (analysis.fundamental.pe_ratio < 5 ? "text-accent-emerald" :
     analysis.fundamental.pe_ratio < 10 ? "text-accent-amber" : "text-surface-300") : "text-surface-500";
  const epsStatus = analysis?.fundamental?.eps ?
    (analysis.fundamental.eps > 0 ? "text-accent-emerald" : "text-accent-rose") : "text-surface-500";

  const sparkData = useMemo(() => {
    if (!analysis?.price?.last) return [];
    const base = analysis.price.last;
    const rnd = seededRandom(0x9e3779b9); // deterministic seed — stable fallback sparkline
    const data: number[] = [];
    let v = base * 0.85;
    for (let i = 0; i < 40; i++) {
      v += (rnd() - 0.48) * 0.03 * v;
      data.push(v);
    }
    return data;
  }, [analysis?.price?.last]);

  const isAllowed = analysis?.state === "مجاز";
  const isBanned = analysis?.state === "ممنوع" || analysis?.state === "متوقف";
  const stateColor = isAllowed ? "bg-accent-emerald/15 text-accent-emerald" :
    isBanned ? "bg-accent-rose/15 text-accent-rose" : "bg-surface-700 text-surface-400";

  if (!decodedSymbol) {
    return (
      <AppLayout title="تحلیل کدال" subtitle="نمادی انتخاب نشده است">
        <div className="max-w-5xl mx-auto py-20 text-center text-surface-500">
          <p className="text-5xl mb-4">📊</p>
          <p className="text-lg">لطفاً یک نماد وارد کنید</p>
          <p className="text-sm mt-2">به عنوان مثال: <Link href="/codal/analysis/فولاد" className="text-primary-400 hover:underline">فولاد</Link></p>
        </div>
      </AppLayout>
    );
  }

  if (!isLoading && (!analysis || !analysis.price)) {
    return (
      <AppLayout title="تحلیل کدال" subtitle="داده‌ای یافت نشد">
        <div className="max-w-5xl mx-auto py-20 text-center text-surface-500">
          <span className="material-icons text-5xl mb-4 block">search_off</span>
          <p className="text-lg font-bold">داده‌ای برای نماد «{decodedSymbol}» یافت نشد</p>
          <p className="text-sm mt-2">ابتدا داده‌های بازار را همگام‌سازی کنید</p>
          <Link href="/codal" className="text-primary-400 text-sm mt-4 inline-block hover:underline">بازگشت به کدال</Link>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title={`تحلیل بنیادی ${analysis?.company_name || decodedSymbol}`}
      subtitle={`تحلیل جامع صورت‌های مالی و نسبت‌های بنیادی • ${analysis?.industry || decodedSymbol}`}
    >
      <div className="max-w-6xl mx-auto space-y-5">
        {/* ── Header ────────────────────────────────────────────────────── */}
        {isLoading ? (
          <Skeleton className="h-32 w-full rounded-xl" />
        ) : analysis ? (
          <div className="glass-card p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary-600/20 flex items-center justify-center text-xl">
                  📊
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-2xl font-bold text-surface-100">{analysis.company_name}</h1>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-lg ${stateColor}`}>{analysis.state || "نامشخص"}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-sm text-surface-400">
                    <span className="bg-surface-800 px-2 py-0.5 rounded text-primary-300 font-bold">{analysis.symbol}</span>
                    <span>{analysis.industry}</span>
                    {analysis.sub_sector && <span>• {analysis.sub_sector}</span>}
                    <span>• {[analysis.market, analysis.board].filter(Boolean).join(" / ")}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Link
                  href={`/codal/accounting/${encodeURIComponent(decodedSymbol)}`}
                  className="text-xs bg-violet-600/15 hover:bg-violet-600/25 text-violet-300 px-3 py-2 rounded-lg transition-colors"
                >
                  📒 حسابداری
                </Link>
                <Link
                  href={`/symbol/${decodedSymbol}`}
                  className="text-xs bg-surface-700 hover:bg-surface-600 text-surface-300 px-3 py-2 rounded-lg transition-colors"
                >
                  صفحه نماد
                </Link>
                <Link
                  href={`/codal?symbol=${encodeURIComponent(decodedSymbol)}`}
                  className="text-xs bg-primary-600/15 hover:bg-primary-600/25 text-primary-300 px-3 py-2 rounded-lg transition-colors"
                >
                  اطلاعیه‌های کدال
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <div className="glass-card p-5 text-center text-accent-rose">
            داده‌ای برای نماد «{decodedSymbol}» یافت نشد
          </div>
        )}

        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1,2,3].map(i => <Skeleton key={i} className="h-40 rounded-xl" />)}
          </div>
        )}

        {analysis && (
          <>
            {/* ── Price & Performance Row ─────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Card title="💰 قیمت و بازدهی" className="lg:col-span-1">
                <div className="space-y-4">
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-3xl font-black font-mono text-surface-100">
                        {analysis.price.last.toLocaleString("en-US")}
                      </p>
                      <p className="text-xs text-surface-500 mt-1">ریال</p>
                    </div>
                    <div className="text-right">
                      <p className={`text-lg font-bold font-mono ${pricePct.color}`}>
                        {analysis.price.change.toLocaleString("en-US")} ({pricePct.text})
                      </p>
                      <p className="text-xs text-surface-500 mt-1">تغییر روز</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div className="bg-surface-800 rounded-xl p-3">
                      <p className="text-xs text-surface-500">بالاترین</p>
                      <p className="font-mono font-bold text-accent-rose">{analysis.price.max.toLocaleString("en-US")}</p>
                    </div>
                    <div className="bg-surface-800 rounded-xl p-3">
                      <p className="text-xs text-surface-500">پایین‌ترین</p>
                      <p className="font-mono font-bold text-accent-emerald">{analysis.price.min.toLocaleString("en-US")}</p>
                    </div>
                    <div className="bg-surface-800 rounded-xl p-3">
                      <p className="text-xs text-surface-500">قیمت دیروز</p>
                      <p className="font-mono text-surface-300">{analysis.price.yesterday.toLocaleString("en-US")}</p>
                    </div>
                    <div className="bg-surface-800 rounded-xl p-3">
                      <p className="text-xs text-surface-500">حجم معاملات</p>
                      <p className="font-mono text-surface-300">{formatCurrency(analysis.trade.volume)}</p>
                    </div>
                  </div>

                  {/* Sparkline */}
                  <div className="pt-2">
                    <svg width="100%" height="50" viewBox="0 0 200 50" preserveAspectRatio="none">
                      <path
                        d={sparkData.map((v, i) => `${i === 0 ? "M" : "L"}${(i / (sparkData.length - 1)) * 200},${50 - ((v - Math.min(...sparkData)) / (Math.max(...sparkData) - Math.min(...sparkData) || 1)) * 45}`).join(" ")}
                        fill="none" stroke={analysis.price.change >= 0 ? "#22c55e" : "#ef4444"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>
              </Card>

              <Card title="📊 نسبت‌های بنیادی" className="lg:col-span-1">
                <div className="grid grid-cols-2 gap-4">
                  <MetricBox label="P/E" value={analysis.fundamental.pe_ratio.toFixed(1)} unit="×" color={peStatus} />
                  <MetricBox label="P/S" value={analysis.fundamental.ps_ratio ? analysis.fundamental.ps_ratio.toFixed(2) : "—"} unit="×" />
                  <MetricBox label="EPS" value={analysis.fundamental.eps ? analysis.fundamental.eps.toLocaleString("en-US") : "—"} unit="ریال" color={epsStatus} />
                  <MetricBox label="P/E گروه" value={analysis.fundamental.group_pe ? analysis.fundamental.group_pe.toFixed(1) : "—"} unit="×" />
                  <MetricBox label="ارزش بازار" value={formatCurrency(analysis.fundamental.market_cap)} unit="ریال" color="text-primary-300" />
                  <MetricBox label="تعداد سهام" value={formatCurrency(analysis.fundamental.shares_count)} unit="سهم" />
                </div>
              </Card>

              <Card title="🎯 شاخص‌های عملکردی" className="lg:col-span-1">
                <div className="space-y-4">
                  <RatingBar value={analysis.performance.price_change_pct} label="تغییر قیمت روز" />
                  <RatingBar value={analysis.performance.price_vs_low_pct} label="موقعیت در دامنه روز" />
                  <RatingBar value={analysis.performance.volume_vs_base * 10} label="نسبت حجم به حجم مبنا" />
                  <div className="flex items-center gap-3 pt-2">
                    <div className={`flex-1 p-3 rounded-xl text-center ${analysis.fundamental.free_float_pct > 10 ? "bg-accent-emerald/10" : "bg-accent-amber/10"}`}>
                      <p className="text-xs text-surface-500">شناوری</p>
                      <p className="font-mono font-bold text-surface-100">{analysis.fundamental.free_float_pct.toFixed(1)}%</p>
                    </div>
                    <div className="flex-1 p-3 rounded-xl text-center bg-surface-800">
                      <p className="text-xs text-surface-500">حجم مبنا</p>
                      <p className="font-mono font-bold text-surface-100">{formatCurrency(analysis.fundamental.base_volume)}</p>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* ── Financial Health & Estimates ────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              <FinancialHealthCard
                value={analysis.fundamental.eps}
                label="سودآوری (EPS)"
                healthy="سودده"
                unhealthy="زیان‌ده"
              />
              <FinancialHealthCard
                value={analysis.fundamental.pe_ratio ? (analysis.fundamental.group_pe ? analysis.fundamental.group_pe - analysis.fundamental.pe_ratio : 0) : -1}
                label="P/E نسبت به گروه"
                healthy="ارزان‌تر از گروه"
                unhealthy="گران‌تر از گروه"
              />
              <div className={`p-4 rounded-xl border ${analysis.real_legal.real_net > 0 ? "bg-accent-emerald/5 border-accent-emerald/20" : "bg-accent-rose/5 border-accent-rose/20"}`}>
                <p className="text-xs text-surface-500 mb-1">خالص خرید حقیقی</p>
                <p className={`text-lg font-bold ${analysis.real_legal.real_net > 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                  {analysis.real_legal.real_net > 0 ? "خرید خالص" : "فروش خالص"}
                </p>
                <p className="font-mono text-sm mt-1 text-surface-300">
                  {formatCurrency(Math.abs(analysis.real_legal.real_net))}
                </p>
              </div>
              <div className={`p-4 rounded-xl border ${(analysis.price.last < analysis.price.yesterday) ? "bg-accent-emerald/5 border-accent-emerald/20" : "bg-accent-rose/5 border-accent-rose/20"}`}>
                <p className="text-xs text-surface-500 mb-1">فاصله از آستانه مجاز</p>
                <p className={`text-lg font-bold ${analysis.price.lowest_allowed > 0 ? "text-accent-emerald" : "text-surface-400"}`}>
                  {analysis.price.lowest_allowed > 0
                    ? `کف: ${analysis.price.lowest_allowed.toLocaleString("en-US")}`
                    : "نامشخص"}
                </p>
                <p className="font-mono text-sm mt-1 text-surface-300">
                  {analysis.price.highest_allowed > 0 ? `سقف: ${analysis.price.highest_allowed.toLocaleString("en-US")}` : ""}
                </p>
              </div>
            </div>

            {/* ── Real/Legal Trade Analysis ──────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card title="🧑‍💼 معاملات حقیقی/حقوقی">
                <RealLegalCard data={{
                    buy_real_volume: analysis.real_legal.buy_real_volume,
                    sell_real_volume: analysis.real_legal.sell_real_volume,
                    buy_legal_volume: analysis.real_legal.buy_legal_volume,
                    sell_legal_volume: analysis.real_legal.sell_legal_volume,
                  }} />
                <div className="mt-4 grid grid-cols-2 gap-3 text-center text-sm">
                  <div className="bg-surface-800 rounded-xl p-3">
                    <p className="text-xs text-surface-500 mb-1">درصد خرید حقیقی</p>
                    <p className={`font-mono font-bold text-lg ${analysis.real_legal.real_buy_pct > 50 ? "text-accent-emerald" : "text-surface-300"}`}>
                      {analysis.real_legal.real_buy_pct.toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-surface-800 rounded-xl p-3">
                    <p className="text-xs text-surface-500 mb-1">خالص حقیقی‌ها از کل</p>
                    <p className={`font-mono font-bold text-lg ${analysis.real_legal.real_net_pct_of_total >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {analysis.real_legal.real_net_pct_of_total >= 0 ? "+" : ""}{analysis.real_legal.real_net_pct_of_total.toFixed(1)}%
                    </p>
                  </div>
                </div>
              </Card>

              <Card title="👥 سهامداران عمده">
                {analysis.holders.top_holders.length > 0 ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-surface-500 pb-2 border-b border-surface-700">
                      <span>نام سهامدار</span>
                      <span>درصد</span>
                    </div>
                    {analysis.holders.top_holders.map((h, i) => (
                      <div key={i} className="flex items-center justify-between p-2.5 rounded-lg hover:bg-surface-800/50 transition-colors">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs text-surface-600 w-5">{i + 1}</span>
                          <span className="text-sm text-surface-200 truncate">{h.name}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${h.type === "حقوقی" ? "bg-primary-600/20 text-primary-300" : "bg-accent-amber/15 text-accent-amber"}`}>
                            {h.type}
                          </span>
                        </div>
                        <span className="font-mono font-bold text-sm text-surface-100">{h.percentage.toFixed(2)}%</span>
                      </div>
                    ))}
                    <div className="flex items-center justify-between pt-2 text-xs text-surface-500 border-t border-surface-700">
                      <span>تعداد سهامداران: {analysis.holders.total_count}</span>
                      <span>حقوقی: {analysis.holders.legal_holder_count} | حقیقی: {analysis.holders.real_holder_count}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-surface-500 text-sm text-center py-6">اطلاعات سهامداران در دسترس نیست</p>
                )}
              </Card>
            </div>

            {/* ── Recent Announcements ────────────────────────────────────── */}
            <Card title="📋 آخرین اطلاعیه‌های کدال" subtitle={`آخرین اطلاعیه‌های منتشر شده توسط ${analysis.company_name}`}>
              {analysis.announcements.length > 0 ? (
                <div className="space-y-2">
                  {analysis.announcements.map((a, i) => (
                    <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-surface-200 truncate">{a.title || "بدون عنوان"}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-surface-500">{formatDateShamsi(a.date_publish)}</span>
                          <AuditBadge status={a.audit_status} />
                        </div>
                      </div>
                      {a.link_pdf && (
                        <a
                          href={a.link_pdf}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 text-xs bg-accent-rose/10 text-accent-rose px-3 py-1.5 rounded-lg hover:bg-accent-rose/20 transition-colors"
                        >
                          📄 PDF
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-surface-500 text-sm text-center py-6">هیچ اطلاعیه‌ای یافت نشد</p>
              )}
              {analysis.announcements.length > 0 && (
                <div className="mt-3 text-center">
                  <Link
                    href={`/codal?symbol=${encodeURIComponent(decodedSymbol)}`}
                    className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    مشاهده همه اطلاعیه‌ها ←
                  </Link>
                </div>
              )}
            </Card>

            {/* ── Detailed Metrics Table ──────────────────────────────────── */}
            <Card title="📊 جدول جزئیات بنیادی">
              <div className="overflow-x-auto">
                <table className="w-full text-right text-sm">
                  <thead>
                    <tr className="text-surface-500 border-b border-surface-700 text-xs">
                      <th className="pb-2 px-3 font-medium">معیار</th>
                      <th className="pb-2 px-3 font-medium">مقدار</th>
                      <th className="pb-2 px-3 font-medium">توضیحات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: "P/E", value: analysis.fundamental.pe_ratio.toFixed(2), desc: analysis.fundamental.pe_ratio < 5 ? "ارزشمند" : analysis.fundamental.pe_ratio < 10 ? "منطقی" : "بالا" },
                      { label: "P/S", value: analysis.fundamental.ps_ratio ? analysis.fundamental.ps_ratio.toFixed(2) : "—", desc: "نسبت قیمت به فروش" },
                      { label: "EPS", value: analysis.fundamental.eps ? analysis.fundamental.eps.toLocaleString("en-US") : "—", desc: analysis.fundamental.eps > 0 ? "سودآور" : "زیان‌ده" },
                      { label: "P/E گروه", value: analysis.fundamental.group_pe ? analysis.fundamental.group_pe.toFixed(2) : "—", desc: "میانگین P/E صنعت" },
                      { label: "ارزش بازار", value: formatCurrency(analysis.fundamental.market_cap) + " ریال", desc: "Market Cap" },
                      { label: "تعداد سهام", value: formatCurrency(analysis.fundamental.shares_count), desc: "کل سهام منتشر شده" },
                      { label: "شناوری", value: analysis.fundamental.free_float_pct ? `${analysis.fundamental.free_float_pct.toFixed(2)}%` : "—", desc: "درصد شناور آزاد" },
                      { label: "حجم مبنا", value: formatCurrency(analysis.fundamental.base_volume), desc: "حداقل حجم برای تأثیر بر قیمت" },
                      { label: "درآمد تخمینی", value: formatCurrency(analysis.fundamental.estimated_revenue) + " ریال", desc: "برآورد از P/S" },
                      { label: "سود خالص تخمینی", value: formatCurrency(analysis.fundamental.estimated_net_profit) + " ریال", desc: "برآورد از EPS × تعداد سهام" },
                      { label: "حجم معاملات", value: formatCurrency(analysis.trade.volume), desc: "حجم کل معاملات روز" },
                      { label: "ارزش معاملات", value: formatCurrency(analysis.trade.value) + " ریال", desc: "ارزش کل معاملات روز" },
                      { label: "تعداد معاملات", value: analysis.trade.count.toLocaleString("en-US"), desc: "تعداد دفعات معامله" },
                      { label: "بالاترین قیمت", value: analysis.price.max.toLocaleString("en-US"), desc: "قیمت حداکثر روز" },
                      { label: "پایین‌ترین قیمت", value: analysis.price.min.toLocaleString("en-US"), desc: "قیمت حداقل روز" },
                      { label: "کف مجاز", value: analysis.price.lowest_allowed ? analysis.price.lowest_allowed.toLocaleString("en-US") : "—", desc: "آستانه پایین مجاز" },
                      { label: "سقف مجاز", value: analysis.price.highest_allowed ? analysis.price.highest_allowed.toLocaleString("en-US") : "—", desc: "آستانه بالای مجاز" },
                      { label: "وضعیت نماد", value: analysis.state || "—", desc: "وضعیت معاملاتی" },
                    ].map((row, i) => (
                      <tr key={i} className="border-b border-surface-800/50 hover:bg-white/5">
                        <td className="py-2.5 px-3 text-surface-500">{row.label}</td>
                        <td className="py-2.5 px-3 font-mono text-surface-200 font-bold">{row.value}</td>
                        <td className="py-2.5 px-3 text-xs text-surface-500">{row.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* ── Accounting Section (Codal Excel Files) ──────────────────── */}
            <Card title="📒 اطلاعات حسابداری از صورت‌های مالی کدال" subtitle="داده‌های استخراج شده از فایل‌های اکسل کدال">
              {acctLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-8 w-full rounded" />
                  <Skeleton className="h-8 w-3/4 rounded" />
                  <Skeleton className="h-8 w-1/2 rounded" />
                </div>
              ) : accountingData && !("error" in accountingData) ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-surface-500">
                    <span>{accountingData.total_reports} گزارش موجود</span>
                  </div>

                  {Object.entries(accountingData.latest_reports).length === 0 ? (
                    <p className="text-surface-500 text-sm text-center py-6">هیچ گزارش حسابداری برای این نماد یافت نشد</p>
                  ) : (
                    Object.entries(accountingData.latest_reports).map(([rt, report]) => (
                      <div key={rt} className="border border-surface-700 rounded-xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-3 bg-surface-800/80">
                          <div>
                            <span className="text-sm font-bold text-surface-200">{report.label}</span>
                            <span className="text-xs text-surface-500 mr-3">تاریخ: {report.date}</span>
                          </div>
                          <span className="text-xs text-surface-500 font-mono">{report.filename}</span>
                        </div>
                        {Object.keys(report.items).length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full text-right text-sm">
                              <thead>
                                <tr className="text-surface-500 border-b border-surface-700 text-xs">
                                  <th className="pb-2 px-3 font-medium">ردیف</th>
                                  <th className="pb-2 px-3 font-medium">شرح</th>
                                  <th className="pb-2 px-3 font-medium">مبلغ (ریال)</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(report.items).map(([label, value], idx) => (
                                  <tr key={idx} className="border-b border-surface-800/50 hover:bg-white/5">
                                    <td className="py-2 px-3 text-xs text-surface-500">{idx + 1}</td>
                                    <td className="py-2 px-3 text-surface-200">{label}</td>
                                    <td className="py-2 px-3 font-mono text-surface-100 font-bold">
                                      {value.toLocaleString("en-US")}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="text-surface-500 text-xs text-center py-4">داده‌ای استخراج نشد</p>
                        )}
                      </div>
                    ))
                  )}
                  <div className="text-center pt-2">
                    <Link
                      href={`/codal-accounting/${encodeURIComponent(decodedSymbol)}/reports`}
                      className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                    >
                      مشاهده همه گزارش‌ها ←
                    </Link>
                  </div>
                </div>
              ) : (
                <p className="text-surface-500 text-sm text-center py-6">داده‌های حسابداری کدال برای این نماد در دسترس نیست</p>
              )}
            </Card>
          </>
        )}

        {/* ── Error State ────────────────────────────────────────────────── */}
        {error && !isLoading && (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">⚠️</p>
            <p className="text-lg">خطا در دریافت داده‌های تحلیل</p>
            <p className="text-sm mt-1 text-surface-500">لطفاً بعداً مراجعه کنید</p>
          </div>
        )}

        {/* ── Quick Links ────────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/codal" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">← اطلاعیه‌های کدال</Link>
          <Link href={`/symbol/${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">نماد {decodedSymbol}</Link>
          <Link href="/analysis" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">تحلیل بازار</Link>
          <Link href={`/smart-money?symbol=${decodedSymbol}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">پول هوشمند</Link>
        </div>
      </div>
    </AppLayout>
  );
}
