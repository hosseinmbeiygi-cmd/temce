"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
import { Coins, TrendingUp, TrendingDown, Newspaper, BarChart3, DollarSign, Clock, Sparkles, AlertTriangle, Calendar, Gem } from "lucide-react";

/* ───────── Types ───────── */

interface PriceItem {
  symbol?: string;
  name?: string;
  title?: string;
  price?: number;
  price_close?: number;
  price_last?: number;
  price_change?: number;
  price_change_pct?: number;
  change_percent?: number;
  unit?: string;
  date?: string;
  time?: string;
  category?: string;
}

interface SilverFund {
  symbol: string;
  name?: string;
  fund_type?: string;
  market?: string;
  nav?: number;
  nav_change?: number;
  nav_change_pct?: number;
  price_last?: number;
  price_close?: number;
  trade_volume?: number;
  trade_value?: number;
  market_value?: number;
  shares_count?: number;
  time?: string;
  updated_at?: string;
}

interface FutureRow {
  contract_code: string;
  contract_description?: string;
  contract_size?: number;
  contract_size_unit?: string;
  price_last?: number;
  price_last_change_pct?: number;
  trade_volume?: number;
  open_interest?: number;
  date_end_text?: string;
  date_update?: string;
}

interface NewsItem {
  id?: string | number;
  title?: string;
  summary?: string;
  source?: string;
  url?: string;
  category?: string;
  symbols?: string[];
  published_at?: string;
  sentiment?: string;
  sentiment_score?: number;
}

interface CandleDataPoint {
  date: string;
  time?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface SilverForecastPoint {
  date: string;
  p50: number;
  p_lower: number;
  p_upper: number;
  direction_probability_up: number;
}

interface SilverForecast {
  symbol: string;
  horizon_days: number;
  data_as_of?: string;
  model?: { name?: string; version?: string; note?: string };
  forecast: SilverForecastPoint[];
  quality?: { status?: string; is_stale?: boolean };
  risk?: { level?: string; volatility?: string };
  meta?: { disclaimer?: string };
}

function isSilverText(value: unknown): boolean {
  return /نقره|سیلور|silver|xag|ag999|ag925/i.test(String(value ?? ""));
}

function isGoldText(value: unknown): boolean {
  return /طلا|زر|سکه|gold|xau/i.test(String(value ?? ""));
}

/* ───────── Format helpers ───────── */

const fa = (n: number) => n.toLocaleString("fa-IR");
const faPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

function fmtTr(v?: number): string {
  if (v == null) return "—";
  if (v >= 1e12) return (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9) return (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return fa(v);
}

function sentimentDot(s?: string): string {
  if (s === "bullish" || s === "positive") return "bg-emerald-400";
  if (s === "bearish" || s === "negative") return "bg-rose-400";
  return "bg-surface-500";
}

/* ───────── Page ───────── */

export default function SilverMarketPage() {
  const [grams, setGrams] = useState("1");

  const pricesQ = useQuery({
    queryKey: ["silver-spot"],
    queryFn: async () => {
      try {
        const r = await apiGet<any>("/brsapi/commodities?category=precious_metal");
        const list: PriceItem[] = extractArray<PriceItem>(r?.data ?? r);
        const silver = list.filter((x) => {
          const text = `${x.symbol ?? ""} ${x.name ?? x.title ?? ""} ${x.category ?? ""}`;
          return isSilverText(text) && !isGoldText(text);
        });
        return silver.filter((x) => (x.price ?? x.price_close ?? 0) > 0).map((x) => ({ ...x, price_change_pct: x.price_change_pct ?? x.change_percent }));
      } catch {/* fall through */}
      return [];
    },
    refetchInterval: 120_000,
  });

  const fxQ = useQuery({
    queryKey: ["fx-usd"],
    queryFn: async () => {
      try {
        const r = await apiGet<any>("/brsapi/currency");
        const list: PriceItem[] = extractArray<PriceItem>(r?.data ?? r);
        const usd = list.find((x) => (x.symbol ?? "").toLowerCase().includes("usd"));
        return usd?.price ?? null;
      } catch { return null; }
    },
    refetchInterval: 120_000,
  });

  const fundsQ = useQuery({
    queryKey: ["silver-funds"],
    queryFn: async () => {
      try {
        const r = await apiGet<any>("/funds?market=ime&limit=200");
        const items: SilverFund[] = extractArray<SilverFund>(r?.items ?? r?.data ?? r);
        return items.filter((f) => {
          const n = `${f.name ?? ""} ${f.symbol ?? ""}`;
          const isSilver = isSilverText(n) || f.fund_type === "نقره";
          const isCommodity = f.fund_type === "کالایی" || /کالایی|کالا/.test(n);
          const isGold = isGoldText(n);
          return (isSilver || (isCommodity && !isGold)) && ((f.nav ?? 0) > 0 || (f.price_last ?? 0) > 0);
        });
      } catch {/* fall through */}
      return [];
    },
    refetchInterval: 60_000,
  });

  const futQ = useQuery({
    queryKey: ["silver-futures"],
    queryFn: async () => {
      try {
        const r = await apiGet<any>("/ime/futures");
        const items: FutureRow[] = extractArray<FutureRow>(r?.data ?? r);
        const silver = items.filter((x) => {
          const text = `${x.contract_code ?? ""} ${x.contract_description ?? ""}`;
          return isSilverText(text) && !isGoldText(text);
        });
        // dedupe by contract_code — endpoint returns one row per historical snapshot
        const seen = new Set<string>();
        const uniq = silver.filter((x) => (seen.has(x.contract_code) ? false : (seen.add(x.contract_code), true)));
        return uniq.filter((x) => (x.price_last ?? 0) > 0);
      } catch {/* fall through */}
      return [];
    },
    refetchInterval: 60_000,
  });

  const silverFundSymbol = fundsQ.data?.find((f) => isSilverText(`${f.symbol} ${f.name}`))?.symbol ?? null;

  /* Real NAV history of the first available silver ETF — powers the price chart. */
  const navQ = useQuery({
    queryKey: ["silver-fund-nav", silverFundSymbol],
    enabled: Boolean(silverFundSymbol),
    queryFn: async () => {
      // Let transient proxy failures (socket hang up) propagate so RQ retries.
      const r = await apiGet<any>(`/funds/${encodeURIComponent(silverFundSymbol as string)}`);
      const data = r?.data ?? r;
      const nh: { date: string; nav: number; source?: string }[] = data?.nav_history ?? [];
      const snaps = nh
        .filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x.date) && x.nav > 0)
        .sort((a, b) => a.date.localeCompare(b.date));
      return snaps.length > 1 ? snaps : null;
    },
    retry: 2,
    refetchInterval: 300_000,
  });

  const newsQ = useQuery({
    queryKey: ["silver-news"],
    queryFn: async () => {
      try {
        const r = await apiGet<any>("/news?category=market&page_size=6");
        const items: NewsItem[] = extractArray<NewsItem>(r?.data?.items ?? r?.items ?? r?.data ?? r);
        return items.filter((x) => {
          if (!x.title) return false;
          const text = `${x.title} ${x.summary ?? ""} ${(x.symbols ?? []).join(" ")}`;
          return /نقره|سیلور|silver|xag/i.test(text);
        });
      } catch {/* fall through */}
      return [];
    },
    refetchInterval: 300_000,
  });

  /* Candles — real NAV history only. */
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const candles = useMemo<CandleDataPoint[]>(() => {
    if (!mounted) return [];
    const snaps = navQ.data;
    if (snaps && snaps.length > 1) {
      const out: CandleDataPoint[] = [];
      for (let i = 1; i < snaps.length; i++) {
        const open = snaps[i - 1].nav;
        const close = snaps[i].nav;
        out.push({ date: snaps[i].date, open, high: Math.max(open, close), low: Math.min(open, close), close, volume: 0 });
      }
      return out;
    }
    return [];
  }, [navQ.data, mounted]);

  /* Per-gram silver derived from the nearest active futures contract (real). */
  const gramFromFutures = useMemo(() => {
    const f = (futQ.data ?? []).find((x) => (x.price_last ?? 0) > 0 && (x.contract_size ?? 0) > 0);
    if (!f) return null;
    return (f.price_last as number) / (f.contract_size as number);
  }, [futQ.data]);

  const ounce = useMemo(() => {
    const list = pricesQ.data ?? [];
    return list.find((p) => (p.symbol ?? "").toUpperCase().includes("XAG") || (p.unit ?? "").includes("انس"));
  }, [pricesQ.data]);

  const silverForecastQ = useQuery<SilverForecast[]>({
    queryKey: ["silver-xag-forecast", ounce?.price],
    enabled: Boolean(ounce?.price && ounce.price > 0),
    queryFn: async () => {
      const horizons = [1, 3, 7, 14, 30, 90];
      const lastClose = ounce?.price ?? 0;
      const results = await Promise.allSettled(
        horizons.map(async (horizon) => {
          const r = await apiGet<any>(
            `/forecast?symbol=xag_usd&horizon=${horizon}&last_close=${lastClose}`,
          );
          return (r?.data ?? r) as SilverForecast;
        }),
      );
      return results
        .filter((result): result is PromiseFulfilledResult<SilverForecast> => result.status === "fulfilled")
        .map((result) => result.value)
        .filter((item) => item?.forecast?.length > 0)
        .sort((a, b) => a.horizon_days - b.horizon_days);
    },
    staleTime: 300_000,
    retry: 1,
  });

  const coin999 = useMemo(() => {
    const list = pricesQ.data ?? [];
    return list.find((p) => (p.name ?? "").includes("999") || (p.name ?? "").includes("گرمی"));
  }, [pricesQ.data]);

  const silverEtfCount = fundsQ.data?.length ?? 0;
  const usd = fxQ.data ?? null;

  const converter = useMemo(() => {
    const g = parseFloat(grams) || 0;
    const toUsd = ounce?.price == null ? null : (g / 31.1035) * ounce.price;
    const toIrr = toUsd == null || usd == null ? null : toUsd * usd;
    return { toUsd, toIrr, usdRate: usd };
  }, [grams, ounce, usd]);

  /* Bar chart data: futures last_price per contract, like forecast pattern. */
  const futuresBars = useMemo(() => {
    const list = futQ.data ?? [];
    const max = Math.max(1, ...list.map((f) => f.price_last ?? 0));
    return list.map((f) => ({ label: f.contract_code, value: f.price_last ?? 0, change: f.price_last_change_pct ?? 0, max }));
  }, [futQ.data]);

  return (
    <AppLayout title="بازار نقره" subtitle="هر آنچه از بازار نقره و صندوق‌های نقره نیاز دارید" sidebar={false}>
      {/* ─── Hero ─── */}
      <div className="relative overflow-hidden rounded-[28px] border border-slate-500/20 mb-6">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0f0a1a] via-[#1a1530] to-[#0f1a2a]" />
        <div className="absolute inset-0 opacity-[0.08]" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, #cbd5e1 1px, transparent 0)", backgroundSize: "24px 24px" }} />
        <div className="absolute -top-24 -right-24 w-[420px] h-[420px] bg-slate-400/20 rounded-full blur-[80px]" />
        <div className="absolute -bottom-32 -left-32 w-[520px] h-[520px] bg-indigo-400/15 rounded-full blur-[90px]" />

        <div className="relative p-6 sm:p-8 lg:p-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-400/15 border border-slate-400/20 text-slate-200 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            بازار زنده • به‌روزرسانی هر ۲ دقیقه
            <span className="opacity-60">•</span>
            <Clock className="w-3 h-3" />
            {new Date().toLocaleDateString("fa-IR")}
          </div>

          <h1 className="mt-4 text-2xl sm:text-3xl font-black tracking-tight text-white">
            بازار نقره <span className="bg-gradient-to-l from-slate-200 to-slate-400 bg-clip-text text-transparent">— لحظه‌ای و صندوق‌ها</span>
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/70">
            قیمت لحظه‌ای نقره گرمی ۹۹۹، شمش نقره، اونس جهانی و صندوق‌های ETF نقره (نقراط، سیگلو، پلاتا، سیمین)
          </p>

          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-4xl">
            <HeroStat icon={<Gem className="w-4 h-4" />} color="slate" label="انس جهانی نقره" value={ounce ? `${(ounce.price ?? 0).toFixed(2)}` : "—"} unit={ounce?.unit ?? "دلار/انس"} change={ounce?.price_change_pct} />
            <HeroStat icon={<Coins className="w-4 h-4" />} color="emerald" label="نقره گرمی (برگرفته از آتی)" value={gramFromFutures ? fa(Math.round(gramFromFutures)) : coin999 ? fa(Math.round(coin999.price ?? 0)) : "—"} unit="ریال/گرم" change={gramFromFutures ? undefined : coin999?.price_change_pct} />
            <HeroStat icon={<BarChart3 className="w-4 h-4" />} color="indigo" label="صندوق‌های نقره" value={`${silverEtfCount}`} unit="نماد" sub={futQ.data ? `${futQ.data.length} آتی` : undefined} />
            <HeroStat icon={<DollarSign className="w-4 h-4" />} color="amber" label="دلار آمریکا" value={usd == null ? "—" : fa(Math.round(usd))} unit="ریال" />
          </div>
        </div>
      </div>

      {/* ─── Live silver prices (with sparkline) ─── */}
      <SectionHeader icon={<Sparkles className="w-4 h-4 text-slate-300" />} title="قیمت لحظه‌ای نقره" />
      {pricesQ.isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(pricesQ.data ?? []).map((p, i) => {
            const up = (p.price_change_pct ?? 0) >= 0;
            const last = p.price ?? p.price_close ?? 0;
            return (
              <div key={i} className="relative overflow-hidden rounded-2xl border border-slate-500/15 bg-gradient-to-br from-zinc-900 to-zinc-800 p-4 hover:shadow-xl hover:shadow-slate-500/10 transition" dir="rtl">
                <div className="absolute -right-6 -top-6 w-20 h-20 bg-slate-400/15 rounded-full blur-2xl" />
                <div className="flex items-start justify-between gap-2">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-300 to-slate-500 grid place-items-center text-zinc-900 shadow">
                    <Coins className="w-5 h-5" />
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`text-xs px-2 py-1 rounded-full font-mono ${up ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"}`}>
                      {up ? <TrendingUp className="w-3 h-3 inline" /> : <TrendingDown className="w-3 h-3 inline" />} {faPct(p.price_change_pct ?? 0)}
                    </span>
                  </div>
                </div>
                <div className="mt-3 text-sm font-bold text-white truncate">{p.name ?? p.title ?? p.symbol}</div>
                <div className="text-[11px] text-zinc-400 font-mono">{p.symbol ?? "—"} • {p.unit ?? "IRR"}</div>
                <div className="mt-2 text-2xl font-black font-mono text-slate-200">{last > 0 ? last.toLocaleString("fa-IR") : "—"}</div>
                <div className="text-[11px] text-zinc-500">{p.date ?? ""} {p.time ?? ""}</div>
              </div>
            );
          })}
          {!pricesQ.data?.length && <div className="sm:col-span-2 lg:col-span-4 rounded-2xl border border-surface-800 bg-surface-900/40 p-6 text-center text-sm text-surface-500">قیمت واقعی نقره در API موجود نیست.</div>}
        </div>
      )}

      {/* ─── Candle chart (NAV history) ─── */}
      <div className="mt-6">
        <SectionHeader icon={<BarChart3 className="w-4 h-4 text-cyan-300" />} title="نمودار قیمت نقره" sub={navQ.data ? `NAV واقعی ${silverFundSymbol ?? "صندوق نقره"} — روزانه` : "NAV واقعی در دسترس نیست"} />
        {pricesQ.isLoading ? (
          <Skeleton className="h-[300px] rounded-2xl" />
        ) : (
          <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-4">
            {!candles.length && <div className="py-16 text-center text-sm text-surface-500">داده‌ی تاریخی واقعی برای نمودار در دسترس نیست.</div>}
            <div className="flex items-end gap-[2px] h-48">
              {candles.map((c, i) => {
                const all = candles.map((x) => x.high);
                const max = Math.max(...all);
                const min = Math.min(...all);
                const range = max - min || 1;
                const bodyTop = Math.max(c.open, c.close);
                const bodyBot = Math.min(c.open, c.close);
                const bodyTopPct = ((max - bodyTop) / range) * 100;
                const bodyBotPct = ((max - bodyBot) / range) * 100;
                const bodyH = Math.max(2, bodyBotPct - bodyTopPct);
                const wickTopPct = ((max - c.high) / range) * 100;
                const wickBotPct = ((max - c.low) / range) * 100;
                const up = c.close >= c.open;
                const color = up ? "bg-emerald-500" : "bg-rose-500";
                const wickColor = up ? "bg-emerald-400/60" : "bg-rose-400/60";
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end min-w-0 group relative" style={{ height: "100%" }}>
                    <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 px-2 py-1 rounded bg-zinc-900 border border-zinc-700 text-[10px] text-zinc-100 whitespace-nowrap font-mono">
                      {c.date}: O{(c.open).toFixed(2)} H{(c.high).toFixed(2)} L{(c.low).toFixed(2)} C{(c.close).toFixed(2)}
                    </div>
                    <div className="w-full relative" style={{ height: "100%" }}>
                      <div className={`absolute left-1/2 -translate-x-1/2 w-[1px] ${wickColor}`} style={{ top: `${wickTopPct}%`, height: `${wickBotPct - wickTopPct}%` }} />
                      <div className={`absolute left-1/2 -translate-x-1/2 ${color} rounded-sm`} style={{ top: `${bodyTopPct}%`, height: `${bodyH}%`, width: "70%" }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center justify-between text-[10px] text-surface-500 font-mono">
              <span>{candles[0]?.date}</span>
              <span className="flex items-center gap-3">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" />صعودی</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-rose-500 rounded-sm" />نزولی</span>
              </span>
              <span>{candles[candles.length - 1]?.date}</span>
            </div>
          </div>
        )}
      </div>

      {/* ─── XAG/USD multi-horizon forecast ─── */}
      <div className="mt-6">
        <SectionHeader
          icon={<TrendingUp className="w-4 h-4 text-violet-300" />}
          title="پیش‌بینی انس جهانی نقره (XAG/USD)"
          sub="افق‌های ۱ تا ۹۰ روزه · بازه عدم‌قطعیت ۸۰٪"
        />
        {silverForecastQ.isLoading ? (
          <Skeleton className="h-72 rounded-2xl" />
        ) : silverForecastQ.data?.length ? (
          <div className="rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-950/30 via-surface-900/60 to-surface-900/40 p-4" dir="rtl">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div>
                <div className="text-sm font-bold text-surface-100">سناریوی مدل برای قیمت دلار/انس</div>
                <div className="mt-1 text-[11px] text-surface-500">
                  مدل: {silverForecastQ.data[0].model?.name ?? "—"} · نسخه: {silverForecastQ.data[0].model?.version ?? "—"}
                </div>
              </div>
              <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[10px] text-amber-300">
                آزمایشی؛ تضمین بازده نیست
              </span>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {silverForecastQ.data.map((forecast) => {
                const point = forecast.forecast[forecast.forecast.length - 1];
                const up = point.direction_probability_up >= 0.5;
                const change = ounce?.price ? ((point.p50 / ounce.price) - 1) * 100 : 0;
                return (
                  <div key={forecast.horizon_days} className="rounded-xl border border-surface-800 bg-surface-950/45 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-surface-200">{forecast.horizon_days} روزه</span>
                      <span className={`text-[11px] font-mono ${up ? "text-emerald-400" : "text-rose-400"}`}>
                        احتمال رشد {(point.direction_probability_up * 100).toFixed(0)}٪
                      </span>
                    </div>
                    <div className="mt-3 flex items-end justify-between gap-2">
                      <div>
                        <div className="text-[10px] text-surface-500">پیش‌بینی میانه</div>
                        <div className={`mt-1 text-xl font-black font-mono ${change >= 0 ? "text-emerald-300" : "text-rose-300"}`} dir="ltr">
                          {point.p50.toFixed(2)}
                        </div>
                      </div>
                      <span className={`rounded-lg px-2 py-1 text-xs font-mono ${change >= 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                        {faPct(change)}
                      </span>
                    </div>
                    <div className="mt-3 text-[10px] text-surface-500 font-mono" dir="ltr">
                      {point.p_lower.toFixed(2)} — {point.p_upper.toFixed(2)}
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-surface-800 overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-l from-violet-400 to-cyan-400" style={{ width: `${Math.min(100, Math.max(0, point.direction_probability_up * 100))}%` }} />
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[10px] text-surface-600">
                      <span>{point.date}</span>
                      <span>{forecast.quality?.status === "good" ? "کیفیت داده: خوب" : "کیفیت داده: بررسی شود"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 text-[11px] leading-5 text-amber-200/70">
              {silverForecastQ.data[0].meta?.disclaimer ?? "پیش‌بینی مدل صرفاً برای تحلیل است و جایگزین مدیریت ریسک و تصمیم سرمایه‌گذاری نیست."}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 text-sm text-amber-200/80">
            پیش‌بینی انس نقره در دسترس نیست؛ ابتدا داده‌ی XAG/USD و مدل فعال را بررسی کنید.
          </div>
        )}
      </div>

      {/* ─── Futures term-structure bars ─── */}
      <div className="mt-6">
        <SectionHeader icon={<Calendar className="w-4 h-4 text-cyan-300" />} title="ساختار قیمت آتی نقره" />
        {futQ.isLoading ? (
          <Skeleton className="h-40 rounded-2xl" />
        ) : (
          <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-4">
            {futuresBars.length > 0 && <div className="flex items-end gap-2 h-32">
              {futuresBars.map((b, i) => {
                const up = b.change >= 0;
                const h = (b.value / b.max) * 100;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                    <div className="text-[10px] font-mono text-slate-200" dir="ltr">{(b.value ?? 0).toFixed(2)}</div>
                    <div className="relative w-full flex justify-center" style={{ height: "88px" }}>
                      <div
                        className="absolute bottom-0 rounded-t-md"
                        style={{
                          height: `${h}%`,
                          width: "70%",
                          background: up
                            ? "linear-gradient(to top, rgba(16,185,129,0.85), rgba(16,185,129,0.45))"
                            : "linear-gradient(to top, rgba(244,63,94,0.85), rgba(244,63,94,0.45))",
                        }}
                      />
                    </div>
                    <div className="text-[9px] font-mono text-zinc-500 truncate w-full text-center">{b.label}</div>
                    <div className={`text-[9px] font-mono ${up ? "text-emerald-400" : "text-rose-400"}`}>{faPct(b.change)}</div>
                  </div>
                );
              })}
            </div>}
            {!futuresBars.length && <div className="py-12 text-center text-sm text-surface-500">داده‌ی واقعی ساختار آتی موجود نیست.</div>}
            <div className="mt-3 text-[10px] text-surface-500 text-center">
              قیمت پایانی هر قرارداد آتی (ریال — هر قرارداد ۱۰ گرم گواهی سپرده نقره)
            </div>
          </div>
        )}
      </div>

      {/* ─── Silver ETFs ─── */}
      <div className="mt-6">
        <SectionHeader icon={<BarChart3 className="w-4 h-4 text-indigo-300" />} title="مشتقات و صندوق‌های نقره" />
        {fundsQ.isLoading ? (
          <Skeleton className="h-64 rounded-2xl" />
        ) : (
          <div className="overflow-auto rounded-2xl border border-surface-800">
            <table className="w-full text-sm">
              <thead className="bg-surface-800/60 text-surface-400">
                <tr>
                  <th className="p-3 text-right">نام صندوق</th>
                  <th className="p-3 text-right font-mono">نماد</th>
                  <th className="p-3 text-left">قیمت</th>
                  <th className="p-3 text-left">NAV</th>
                  <th className="p-3 text-left">حباب</th>
                  <th className="p-3 text-left">تغییر NAV</th>
                  <th className="p-3 text-left">ارزش بازار</th>
                  <th className="p-3 text-left">ارزش معاملات</th>
                  <th className="p-3 text-right">زمان</th>
                </tr>
              </thead>
              <tbody>
            {(fundsQ.data ?? []).map((f) => {
                  const up = (f.nav_change_pct ?? 0) >= 0;
                  return (
                    <tr key={f.symbol} className="border-t border-surface-800 hover:bg-surface-800/30">
                      <td className="p-3 font-bold text-surface-100">{f.name ?? f.symbol}</td>
                      <td className="p-3 font-mono text-surface-300">{f.symbol}</td>
                      <td className="p-3 text-left font-mono font-bold text-surface-100">{fa(Math.round(f.price_last ?? 0))}</td>
                      <td className="p-3 text-left font-mono text-surface-300">{fa(Math.round(f.nav ?? 0))}</td>
                      <td className="p-3 text-left font-mono font-bold">{
                        (() => {
                          const p = f.price_last ?? 0;
                          const n = f.nav ?? 1;
                          const prem = (p / n - 1) * 100;
                          const c = prem >= 0 ? "text-amber-400" : "text-emerald-400";
                          return <span className={c}>{prem >= 0 ? "+" : ""}{prem.toFixed(2)}%</span>;
                        })()
                      }</td>
                      <td className={`p-3 text-left font-mono font-bold ${up ? "text-emerald-400" : "text-rose-400"}`}>{faPct(f.nav_change_pct ?? 0)}</td>
                      <td className="p-3 text-left font-mono text-surface-400">{fmtTr(f.market_value)}</td>
                      <td className="p-3 text-left font-mono text-surface-400">{fmtTr(f.trade_value)}</td>
                      <td className="p-3 text-right text-[11px] text-surface-500 font-mono">{f.time ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!fundsQ.data?.length && <div className="p-6 text-center text-sm text-surface-500">صندوق نقره یا کالایی واقعی در API موجود نیست.</div>}
          </div>
        )}
      </div>

      {/* ─── Futures table ─── */}
      <div className="mt-6">
        <SectionHeader icon={<Calendar className="w-4 h-4 text-cyan-300" />} title="قراردادهای آتی نقره" />
        {futQ.isLoading ? (
          <Skeleton className="h-48 rounded-2xl" />
        ) : (
          <div className="overflow-auto rounded-2xl border border-surface-800">
            <table className="w-full text-sm">
              <thead className="bg-surface-800/60 text-surface-400">
                <tr>
                  <th className="p-3 text-right">نماد</th>
                  <th className="p-3 text-right">نام</th>
                  <th className="p-3 text-left">سررسید</th>
                  <th className="p-3 text-left">قیمت</th>
                  <th className="p-3 text-left">تغییر</th>
                  <th className="p-3 text-left">حجم</th>
                  <th className="p-3 text-left">موقعیت باز</th>
                </tr>
              </thead>
              <tbody>
                {(futQ.data ?? []).map((f) => {
                  const up = (f.price_last_change_pct ?? 0) >= 0;
                  return (
                    <tr key={f.contract_code} className="border-t border-surface-800 hover:bg-surface-800/30">
                      <td className="p-3 font-mono font-bold text-surface-200">{f.contract_code}</td>
                      <td className="p-3 text-surface-300">{f.contract_description ?? "—"}</td>
                      <td className="p-3 text-left font-mono text-surface-400 text-xs">{f.date_end_text || f.date_update || "—"}</td>
                      <td className="p-3 text-left font-mono font-bold text-slate-200">{(f.price_last ?? 0).toLocaleString("fa-IR")}</td>
                      <td className={`p-3 text-left font-mono font-bold ${up ? "text-emerald-400" : "text-rose-400"}`}>{faPct(f.price_last_change_pct ?? 0)}</td>
                      <td className="p-3 text-left font-mono text-surface-400">{fa(f.trade_volume ?? 0)}</td>
                      <td className="p-3 text-left font-mono text-surface-400">{fa(f.open_interest ?? 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!futQ.data?.length && <div className="p-6 text-center text-sm text-surface-500">قرارداد آتی نقره‌ای در API موجود نیست.</div>}
          </div>
        )}
      </div>

      {/* ─── Converter + API info ─── */}
      <div className="mt-6 grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl border border-surface-800 bg-surface-900/40 p-4">
          <div className="text-sm font-bold flex items-center gap-2">
            <Coins className="w-4 h-4 text-slate-300" />
            مبدل سریع (نقره)
          </div>
          <div className="mt-3 flex flex-wrap gap-3 items-center">
            <input
              value={grams}
              onChange={(e) => setGrams(e.target.value)}
              className="w-28 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700 text-sm font-mono"
              placeholder="گرم"
              inputMode="decimal"
            />
            <span className="text-sm text-surface-400">گرم نقره ≈</span>
            <span className="text-sm font-mono font-bold text-emerald-300">{converter.toUsd == null ? "—" : `${converter.toUsd.toFixed(2)} دلار`}</span>
            <span className="text-sm text-surface-400">•</span>
            <span className="text-sm font-mono font-bold text-slate-200">{converter.toIrr == null ? "—" : `${fa(Math.round(converter.toIrr))} ریال`}</span>
          </div>
          <div className="mt-2 text-[11px] text-surface-500">
            قیمت از BrsApi: اونس {ounce ? (ounce.price ?? 0).toFixed(2) : "—"} دلار × دلار {usd == null ? "—" : `${fa(Math.round(usd))} ریال`} (هر انس = ۳۱.۱۰۳۵ گرم)
          </div>
        </div>

        <div className="rounded-2xl border border-slate-500/15 bg-slate-500/5 p-4">
          <div className="text-sm font-bold text-slate-300">API</div>
          <div className="mt-2 space-y-1 font-mono text-[11px] text-surface-400">
            <div>GET /api/v1/brsapi/commodities?category=precious_metal</div>
            <div>GET /api/v1/brsapi/currency</div>
            <div>GET /api/v1/funds?market=ime</div>
            <div>GET /api/v1/funds/{silverFundSymbol ?? "{نماد نقره}"} (nav_history)</div>
            <div>GET /api/v1/ime/futures</div>
            <div>GET /api/v1/news?category=market</div>
          </div>
        </div>
      </div>

      {/* ─── News ─── */}
      <div className="mt-6">
        <SectionHeader icon={<Newspaper className="w-4 h-4 text-amber-300" />} title="اخبار لحظه‌ای بازار نقره" />
        {newsQ.isLoading ? (
          <Skeleton className="h-40 rounded-2xl" />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(newsQ.data ?? []).slice(0, 6).map((n, i) => (
              <a
                key={n.id ?? i}
                href={n.url ?? "#"}
                target={n.url ? "_blank" : undefined}
                rel="noreferrer"
                className="rounded-2xl border border-surface-800 bg-surface-900/40 p-4 hover:bg-surface-800/50 transition block"
              >
                <div className="flex items-start gap-2">
                  <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${sentimentDot(n.sentiment)}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-surface-100 line-clamp-2">{n.title ?? "—"}</div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-surface-500">
                      <span>{n.source ?? "—"}</span>
                      <span className="font-mono">{n.published_at ?? ""}</span>
                    </div>
                  </div>
                </div>
              </a>
            ))}
            {!newsQ.data?.length && <div className="sm:col-span-2 lg:col-span-3 rounded-2xl border border-surface-800 bg-surface-900/40 p-6 text-center text-sm text-surface-500">خبر واقعی بازار در API موجود نیست.</div>}
          </div>
        )}
      </div>

      {/* ─── Disclaimer ─── */}
      <div className="mt-6 p-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 flex items-start gap-2 text-[12px] text-amber-200/80">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <div>این صفحه فقط داده‌های واقعی دریافت‌شده از API را نمایش می‌دهد؛ در صورت توقف منبع، مقدار ساختگی جایگزین نمی‌شود. برای معامله واقعی به پلتفرم‌های آنلاین مجاز مراجعه کنید.</div>
      </div>
    </AppLayout>
  );
}

/* ───────── Sub-components ───────── */

function SectionHeader({ icon, title, sub }: { icon: React.ReactNode; title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <div className="w-8 h-8 rounded-xl bg-surface-800/80 border border-surface-700 grid place-items-center">
        {icon}
      </div>
      <h2 className="text-sm font-bold text-surface-100">{title}</h2>
      {sub && <span className="text-[10px] text-surface-500 font-mono">{sub}</span>}
    </div>
  );
}

function HeroStat({
  icon, color, label, value, unit, change, sub,
}: { icon: React.ReactNode; color: "slate" | "emerald" | "indigo" | "amber"; label: string; value: string; unit: string; change?: number; sub?: string }) {
  const up = (change ?? 0) >= 0;
  const colorMap: Record<string, string> = {
    slate: "from-slate-300 to-slate-500",
    emerald: "from-emerald-400 to-teal-600",
    indigo: "from-indigo-400 to-violet-600",
    amber: "from-amber-400 to-yellow-600",
  };
  const textMap: Record<string, string> = {
    slate: "text-slate-200",
    emerald: "text-emerald-300",
    indigo: "text-indigo-300",
    amber: "text-amber-300",
  };
  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 p-3 backdrop-blur">
      <div className="text-[11px] text-white/60 flex items-center gap-1">
        <span className={`w-5 h-5 rounded-md bg-gradient-to-br ${colorMap[color]} grid place-items-center text-zinc-900`}>{icon}</span>
        {label}
      </div>
      <div className={`mt-2 text-lg font-bold font-mono ${textMap[color]}`}>{value}</div>
      <div className="text-[10px] text-white/50 flex items-center gap-1 mt-0.5">
        <span>{unit}</span>
        {change != null && (
          <span className={up ? "text-emerald-400 font-mono" : "text-rose-400 font-mono"}>{faPct(change)}</span>
        )}
        {sub && <span className="text-white/40">• {sub}</span>}
      </div>
    </div>
  );
}
