"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, extractArray } from "@/lib/api";
import {
  Activity,
  BrainCircuit,
  Coins,
  DollarSign,
  Gem,
  History,
  LineChart,
  Newspaper,
  Sparkles,
} from "lucide-react";
import PriceChart, { type Candle } from "./components/PriceChart";
import ForecastTab from "./components/ForecastTab";
import BacktestTab from "./components/BacktestTab";
import MlTab from "./components/MlTab";
import { fa, faDateTime, faPct, fmtTr, isGoldText, isSilverText } from "./components/helpers";

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
  time_unix?: number;
}

interface SilverFund {
  symbol?: string;
  name?: string;
  fund_type?: string;
  price_last?: number;
  nav?: number;
  nav_change_pct?: number;
  change_percent?: number;
  market_value?: number;
  base_volume?: number;
  trade_value?: number;
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
  price_last_settlement?: number;
  date_end_text?: string;
  date_update?: string;
}

interface NewsItem {
  id?: string | number;
  title?: string;
  summary?: string;
  source?: string;
  url?: string;
  published_at?: string;
  sentiment?: string;
}

type Tab = "overview" | "forecast" | "funds" | "futures" | "backtest" | "ml" | "news";

const TABS: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "نمای کلی", icon: LineChart },
  { id: "forecast", label: "پیش‌بینی", icon: Sparkles },
  { id: "funds", label: "صندوق‌ها", icon: Gem },
  { id: "futures", label: "آتی (IME)", icon: Activity },
  { id: "backtest", label: "بک‌تست", icon: History },
  { id: "ml", label: "هوش مصنوعی", icon: BrainCircuit },
  { id: "news", label: "اخبار", icon: Newspaper },
];

function latestBySymbol<T extends { symbol?: string }>(rows: T[], ts: (r: T) => number): Map<string, T> {
  const by = new Map<string, T>();
  for (const r of rows) {
    const k = r.symbol ?? "";
    if (!k) continue;
    const prev = by.get(k);
    if (!prev || ts(r) > ts(prev)) by.set(k, r);
  }
  return by;
}

function sentimentDot(s?: string): string {
  if (s === "bullish" || s === "positive") return "bg-up";
  if (s === "bearish" || s === "negative") return "bg-down";
  return "bg-ink-3";
}

export default function SilverMarketPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [grams, setGrams] = useState("1");

  const pricesQ = useQuery({
    queryKey: ["silver-spot"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: PriceItem[] }>("/brsapi/commodities?category=precious_metal&limit=2000");
      const list: PriceItem[] = extractArray<PriceItem>(r?.data ?? r);
      const bySymbol = latestBySymbol(list, (x) => Number(x.time_unix ?? 0));
      return [...bySymbol.values()].filter(
        (x) => isSilverText(`${x.symbol ?? ""} ${x.name ?? x.title ?? ""}`) && !isGoldText(`${x.symbol ?? ""} ${x.name ?? ""}`),
      );
    },
    refetchInterval: 120_000,
  });

  const fxQ = useQuery({
    queryKey: ["fx-usd"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: PriceItem[] }>("/brsapi/currency");
      const list: PriceItem[] = extractArray<PriceItem>(r?.data ?? r);
      return list.find((x) => (x.symbol ?? "").toUpperCase().includes("USD"))?.price ?? null;
    },
    refetchInterval: 120_000,
  });

  const fundsQ = useQuery({
    queryKey: ["silver-funds"],
    queryFn: async () => {
      const r = await apiGet<{ items?: SilverFund[]; data?: SilverFund[] }>("/funds?market=ime&limit=200");
      const items: SilverFund[] = extractArray<SilverFund>((r as { items?: SilverFund[] })?.items ?? (r as { data?: SilverFund[] })?.data ?? r);
      return items.filter((f) => {
        const n = `${f.name ?? ""} ${f.symbol ?? ""}`;
        const silver = isSilverText(n) || f.fund_type === "نقره";
        const commodity = f.fund_type === "کالایی" || /کالایی|کالا/.test(n);
        return (silver || commodity) && !isGoldText(n) && ((f.nav ?? 0) > 0 || (f.price_last ?? 0) > 0);
      });
    },
    refetchInterval: 60_000,
  });

  const futQ = useQuery({
    queryKey: ["silver-futures"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: FutureRow[] }>("/brsapi/manage/download/ime-futures?live=true&limit=2000");
      const items: FutureRow[] = Array.isArray(r) ? (r as FutureRow[]) : extractArray<FutureRow>(r?.data ?? r);
      const silver = items.filter(
        (x) =>
          isSilverText(`${x.contract_code ?? ""} ${x.contract_description ?? ""}`) &&
          !isGoldText(`${x.contract_code ?? ""} ${x.contract_description ?? ""}`),
      );
      const byCode = new Map<string, FutureRow>();
      for (const x of silver) {
        const prev = byCode.get(x.contract_code);
        if (!prev || (x.date_update ?? "") > (prev.date_update ?? "")) byCode.set(x.contract_code, x);
      }
      return [...byCode.values()].filter((x) => (x.price_last ?? 0) > 0);
    },
    refetchInterval: 60_000,
  });

  const spotHistoryQ = useQuery({
    queryKey: ["silver-spot-history"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: PriceItem[] }>("/brsapi/commodities?category=precious_metal&limit=2000");
      const list: PriceItem[] = extractArray<PriceItem>(r?.data ?? r);
      const byDate = new Map<string, PriceItem>();
      for (const x of list) {
        if (!/^XAG/i.test(x.symbol ?? "")) continue;
        const k = x.date ?? "";
        const prev = byDate.get(k);
        if (!prev || (x.time_unix ?? 0) > (prev.time_unix ?? 0)) byDate.set(k, x);
      }
      const dates = [...byDate.keys()].sort();
      const closes = dates.map((d) => byDate.get(d)?.price ?? 0).filter((p) => p > 0);
      return dates
        .map((d, i) => {
          const close = byDate.get(d)?.price ?? 0;
          if (close <= 0) return null;
          const open = i > 0 ? closes[i - 1] : close;
          return { time: d.replace(/\//g, "-"), open, high: Math.max(open, close), low: Math.min(open, close), close };
        })
        .filter(Boolean) as Candle[];
    },
    refetchInterval: 600_000,
    staleTime: 600_000,
  });

  const newsQ = useQuery({
    queryKey: ["silver-news"],
    queryFn: async () => {
      const r = await apiGet<{ data?: { items?: NewsItem[] }; items?: NewsItem[] }>("/news/search?q=نقره");
      const items: NewsItem[] = r?.data?.items ?? r?.items ?? [];
      return items.filter((x) => x.title && /نقره|سیلور|silver|xag/i.test(`${x.title} ${x.summary ?? ""}`));
    },
    refetchInterval: 300_000,
  });

  const ounce = useMemo(() => {
    const list = pricesQ.data ?? [];
    return list.find((p) => (p.symbol ?? "").toUpperCase().includes("XAG")) ?? list.find((p) => (p.symbol ?? "").toUpperCase().includes("AG")) ?? null;
  }, [pricesQ.data]);

  const gramFromFutures = useMemo(() => {
    const f = (futQ.data ?? []).find((x) => (x.price_last ?? 0) > 0 && (x.contract_size ?? 0) > 0);
    return f ? (f.price_last as number) / (f.contract_size as number) : null;
  }, [futQ.data]);

  const usd = fxQ.data ?? null;
  const candles = spotHistoryQ.data ?? [];
  const lastCandle = candles[candles.length - 1] ?? null;
  const firstCandle = candles[0] ?? null;
  const rangeChange = lastCandle && firstCandle ? (lastCandle.close / firstCandle.close - 1) * 100 : null;
  const candleMin = candles.length ? Math.min(...candles.map((c) => c.low)) : null;
  const candleMax = candles.length ? Math.max(...candles.map((c) => c.high)) : null;

  const converter = useMemo(() => {
    const g = parseFloat(grams) || 0;
    const toUsd = ounce?.price == null ? null : (g / 31.1035) * ounce.price;
    const toIrr = toUsd == null || usd == null ? null : toUsd * usd;
    return { toUsd, toIrr };
  }, [grams, ounce, usd]);

  const heroCards = [
    { label: "انس جهانی نقره (XAG/USD)", value: ounce?.price != null ? ounce.price.toFixed(2) : "—", unit: "دلار / انس", change: ounce?.change_percent ?? ounce?.price_change_pct ?? null },
    { label: "نقره گرمی (آتی IME)", value: gramFromFutures != null ? fa(Math.round(gramFromFutures)) : "—", unit: "ریال / گرم", change: null },
    { label: "دلار آمریکا", value: usd != null ? fa(Math.round(usd)) : "—", unit: "ریال", change: null },
    { label: "صندوق‌های نقره / کالایی", value: fa(fundsQ.data?.length ?? 0), unit: "نماد", change: null },
    { label: "قراردادهای آتی نقره", value: fa(futQ.data?.length ?? 0), unit: "قرارداد", change: null },
  ];

  return (
    <AppLayout title="بازار نقره" subtitle="تحلیل یکپارچه نقره، صندوق‌ها، آتی، پیش‌بینی، بک‌تست و ML — داده واقعی BrsApi">
      <div className="space-y-5">
        <section className="rounded-3xl border border-primary-500/20 bg-gradient-to-br from-primary-950 via-card to-card p-5 text-white shadow-[var(--shadow-card-hover)] lg:p-6">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] font-bold">
                <span className="rounded-full bg-white/10 px-2.5 py-1">داده زنده: BrsApi.ir</span>
                <span className="rounded-full bg-white/10 px-2.5 py-1">IME + TSETMC</span>
                <span className="rounded-full bg-warn/15 px-2.5 py-1 text-warn">صرفاً داده واقعی — بدون داده ساختگی</span>
              </div>
              <h2 className="text-xl font-black tracking-tight lg:text-2xl">نقره — پایش، تحلیل و بک‌تست</h2>
              <p className="mt-1 text-xs text-brand-200/80">
                آخرین به‌روزرسانی: {faDateTime(ounce?.date ?? null)} · تاریخچه نمودار: {fa(candles.length)} کندل
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {heroCards.map((c) => (
                <div key={c.label} className="rounded-2xl border border-white/10 bg-white/5 p-3">
                  <p className="text-[10px] text-brand-200/70">{c.label}</p>
                  <p className="mt-1 font-mono text-sm font-black" dir="ltr">{c.value}</p>
                  <p className={`text-[10px] ${c.change == null ? "text-brand-200/50" : c.change >= 0 ? "text-up" : "text-down"}`}>{c.change == null ? c.unit : faPct(c.change)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <nav className="flex gap-2 overflow-x-auto rounded-2xl border border-line bg-card p-2">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex min-w-[110px] flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition ${tab === id ? "bg-primary-600 text-white shadow" : "text-ink-3 hover:bg-soft hover:text-ink"}`}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </nav>

        {tab === "overview" && (
          <section className="grid gap-5 xl:grid-cols-[1.7fr_1fr]">
            <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div>
                  <h3 className="text-sm font-black text-ink">نمودار انس جهانی نقره (XAG/USD)</h3>
                  <p className="mt-1 text-[11px] text-ink-3">کندل‌های روزانه ساخته‌شده از اسنپ‌شات‌های واقعی BrsApi</p>
                </div>
                {ounce?.price != null && (
                  <div className="text-left">
                    <p className="font-mono text-2xl font-black text-ink" dir="ltr">{ounce.price.toFixed(2)}</p>
                    <p className={`text-xs font-bold ${(ounce.change_percent ?? 0) >= 0 ? "text-up" : "text-down"}`} dir="ltr">
                      {faPct(ounce.change_percent ?? ounce.price_change_pct ?? null)}
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-4 rounded-xl bg-soft/60 p-2">
                {spotHistoryQ.isLoading ? (
                  <div className="h-64 animate-pulse rounded-xl bg-soft" />
                ) : (
                  <PriceChart candles={candles} emptyHint="داده تاریخی روزانه XAG برای نمودار موجود نیست — ابتدا همگام‌سازی BrsApi را اجرا کنید." />
                )}
              </div>

              {candles.length >= 2 && (
                <div className="mt-3 flex flex-wrap justify-between gap-2 text-[10px] text-ink-3">
                  <span>کمینه: <b className="font-mono text-ink-2" dir="ltr">{candleMin?.toFixed(2)}</b></span>
                  <span>بیشینه: <b className="font-mono text-ink-2" dir="ltr">{candleMax?.toFixed(2)}</b></span>
                  <span>تغییر بازه: <b className={`font-mono ${(rangeChange ?? 0) >= 0 ? "text-up" : "text-down"}`} dir="ltr">{faPct(rangeChange)}</b></span>
                  <span>آخرین کندل: <b className="font-mono text-ink-2" dir="ltr">{lastCandle?.time ?? "—"}</b></span>
                </div>
              )}
            </div>

            <div className="space-y-5">
              <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
                <div className="mb-3 flex items-center gap-2">
                  <DollarSign className="size-4 text-primary-500" />
                  <h3 className="text-sm font-black text-ink">مبدل سریع (گرم ⇄ انس ⇄ ریال)</h3>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    value={grams}
                    onChange={(e) => setGrams(e.target.value)}
                    className="w-24 rounded-xl border border-line bg-soft px-3 py-2 font-mono text-sm text-ink"
                    placeholder="گرم"
                    inputMode="decimal"
                    dir="ltr"
                  />
                  <span className="text-xs text-ink-3">گرم نقره ≈</span>
                  <span className="font-mono text-sm font-bold text-up" dir="ltr">
                    {converter.toUsd == null ? "—" : `${converter.toUsd.toFixed(2)} $`}
                  </span>
                  <span className="text-ink-3">•</span>
                  <span className="font-mono text-sm font-bold text-ink" dir="ltr">
                    {converter.toIrr == null ? "—" : `${fa(Math.round(converter.toIrr))} ریال`}
                  </span>
                </div>
                <p className="mt-3 text-[10px] text-ink-3">
                  انس {ounce?.price != null ? ounce.price.toFixed(2) : "—"} دلار × دلار {usd != null ? fa(Math.round(usd)) : "—"} ریال (هر انس = ۳۱.۱۰۳۵ گرم)
                </p>
              </div>

              <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
                <div className="mb-3 flex items-center gap-2">
                  <Coins className="size-4 text-primary-500" />
                  <h3 className="text-sm font-black text-ink">وضعیت لحظه‌ای</h3>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between rounded-xl bg-soft px-3 py-2">
                    <span className="text-ink-3">انس جهانی</span>
                    <b className="font-mono text-ink" dir="ltr">{ounce?.price != null ? `${ounce.price.toFixed(2)} $` : "—"}</b>
                  </div>
                  <div className="flex items-center justify-between rounded-xl bg-soft px-3 py-2">
                    <span className="text-ink-3">نقره گرمی (آتی)</span>
                    <b className="font-mono text-ink" dir="ltr">{gramFromFutures != null ? `${fa(Math.round(gramFromFutures))} ریال` : "—"}</b>
                  </div>
                  <div className="flex items-center justify-between rounded-xl bg-soft px-3 py-2">
                    <span className="text-ink-3">دلار آزاد</span>
                    <b className="font-mono text-ink" dir="ltr">{usd != null ? `${fa(Math.round(usd))} ریال` : "—"}</b>
                  </div>
                  <div className="flex items-center justify-between rounded-xl bg-soft px-3 py-2">
                    <span className="text-ink-3">تعداد صندوق</span>
                    <b className="font-mono text-ink">{fa(fundsQ.data?.length ?? 0)}</b>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {tab === "forecast" && <ForecastTab />}
        {tab === "backtest" && <BacktestTab />}
        {tab === "ml" && <MlTab />}

        {tab === "funds" && (
          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-ink">صندوق‌های نقره و کالایی</h3>
                <p className="mt-1 text-[11px] text-ink-3">قیمت و NAV از TSETMC · حباب = قیمت/NAV − ۱</p>
              </div>
              <Gem className="size-5 text-primary-500" />
            </div>
            {fundsQ.isLoading ? (
              <div className="h-40 animate-pulse rounded-xl bg-soft" />
            ) : fundsQ.data?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-right text-ink-3">
                      <th className="p-2">نام</th>
                      <th className="p-2">نماد</th>
                      <th className="p-2">قیمت</th>
                      <th className="p-2">NAV</th>
                      <th className="p-2">حباب</th>
                      <th className="p-2">تغییر NAV</th>
                      <th className="p-2">ارزش معاملات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fundsQ.data.map((f) => {
                      const price = f.price_last ?? 0;
                      const nav = f.nav ?? 0;
                      const bubble = nav > 0 ? (price / nav - 1) * 100 : 0;
                      const navCh = f.nav_change_pct ?? f.change_percent ?? 0;
                      return (
                        <tr key={f.symbol} className="border-t border-line">
                          <td className="p-2 font-bold text-ink-2">{f.name}</td>
                          <td className="p-2 font-mono">{f.symbol}</td>
                          <td className="p-2 font-mono">{fa(price)}</td>
                          <td className="p-2 font-mono">{fa(nav)}</td>
                          <td className={`p-2 font-mono font-bold ${bubble >= 0 ? "text-up" : "text-down"}`} dir="ltr">{faPct(bubble)}</td>
                          <td className={`p-2 font-mono ${navCh >= 0 ? "text-up" : "text-down"}`} dir="ltr">{faPct(navCh)}</td>
                          <td className="p-2 font-mono">{fmtTr(f.trade_value ?? f.base_volume)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-xs text-ink-3">صندوق نقره‌ای در API موجود نیست.</p>
            )}
          </section>
        )}

        {tab === "futures" && (
          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-ink">قراردادهای آتی نقره (IME)</h3>
                <p className="mt-1 text-[11px] text-ink-3">قراردادهای واقعی بورس کالا — فقط نمایش</p>
              </div>
              <Activity className="size-5 text-primary-500" />
            </div>
            {futQ.isLoading ? (
              <div className="h-40 animate-pulse rounded-xl bg-soft" />
            ) : futQ.data?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-right text-ink-3">
                      <th className="p-2">نماد</th>
                      <th className="p-2">توضیحات</th>
                      <th className="p-2">اندازه قرارداد</th>
                      <th className="p-2">آخرین قیمت</th>
                      <th className="p-2">تغییر</th>
                      <th className="p-2">حجم</th>
                      <th className="p-2">تسویه</th>
                    </tr>
                  </thead>
                  <tbody>
                    {futQ.data.map((f) => (
                      <tr key={f.contract_code} className="border-t border-line">
                        <td className="p-2 font-mono font-bold text-ink-2">{f.contract_code}</td>
                        <td className="p-2 text-ink-3">{f.contract_description}</td>
                        <td className="p-2 font-mono">{fa(f.contract_size ?? 0)} {f.contract_size_unit}</td>
                        <td className="p-2 font-mono font-bold">{fa(f.price_last ?? 0)}</td>
                        <td className={`p-2 font-mono ${(f.price_last_change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`} dir="ltr">{faPct(f.price_last_change_pct ?? 0)}</td>
                        <td className="p-2 font-mono">{fmtTr(f.trade_volume)}</td>
                        <td className="p-2 font-mono">{fa(f.price_last_settlement ?? 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-8 text-center text-xs text-ink-3">قرارداد آتی نقره‌ای در API موجود نیست.</p>
            )}
          </section>
        )}

        {tab === "news" && (
          <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-ink">اخبار بازار نقره</h3>
                <p className="mt-1 text-[11px] text-ink-3">جستجوی کلیدواژهٔ نقره در خبرها</p>
              </div>
              <Newspaper className="size-5 text-primary-500" />
            </div>
            {newsQ.isLoading ? (
              <div className="h-40 animate-pulse rounded-xl bg-soft" />
            ) : newsQ.data?.length ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {newsQ.data.slice(0, 9).map((n, i) => (
                  <a
                    key={n.id ?? i}
                    href={n.url ?? "#"}
                    target={n.url ? "_blank" : undefined}
                    rel="noreferrer"
                    className="block rounded-2xl border border-line bg-soft p-4 transition hover:bg-card"
                  >
                    <div className="flex items-start gap-2">
                      <span className={`mt-1.5 size-2 shrink-0 rounded-full ${sentimentDot(n.sentiment)}`} />
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 text-sm font-bold text-ink">{n.title ?? "—"}</div>
                        <div className="mt-2 flex items-center justify-between text-[11px] text-ink-3">
                          <span>{n.source ?? "—"}</span>
                          <span className="font-mono">{n.published_at?.slice(0, 10) ?? ""}</span>
                        </div>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-xs text-ink-3">خبری با کلیدواژهٔ نقره یافت نشد.</p>
            )}
          </section>
        )}

        <p className="px-1 text-[11px] text-ink-3">
          این صفحه فقط داده‌های واقعی دریافت‌شده از API را نمایش می‌دهد؛ در صورت توقف منبع، مقدار ساختگی جایگزین نمی‌شود.
        </p>
      </div>
    </AppLayout>
  );
}
