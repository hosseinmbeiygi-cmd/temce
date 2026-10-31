"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { Gem, DollarSign, TrendingUp, TrendingDown, Activity, Coins, BarChart3, Clock, Sparkles } from "lucide-react";

type GoldItem = { symbol?: string; name?: string; title?: string; price?: number; price_close?: number; price_last?: number; change_percent?: number; unit?: string; date?: string; time?: string };
type FxItem = { symbol: string; name?: string; price?: number; change_percent?: number; unit?: string; time?: string };
type ForecastRes = { symbol: string; horizon_days: number; forecast: { date: string; p50: number; p_lower: number; p_upper: number; direction_probability_up: number }[]; model: { name: string; version: string }; quality: { status: string } };
type ForecastDetail = ForecastRes & { meta?: { disclaimer?: string; fair_value_irr?: number; premium_log?: number } };

function fmtMoney(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString("fa-IR", { maximumFractionDigits: digits });
}

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export default function GoldDollarPage() {
  const [tab, setTab] = useState<"live" | "forecast">("live");
  const [subTab, setSubTab] = useState<"gold" | "fx">("gold");
  const [forecastSymbol, setForecastSymbol] = useState("gold_18k");
  const [horizon, setHorizon] = useState(7);
  const [amount, setAmount] = useState("1");

  const goldQ = useQuery({
    queryKey: ["gold-coin-live"],
    queryFn: async () => (await apiGet<{ data?: GoldItem[] }>("/brsapi/gold-coin")).data ?? [],
    refetchInterval: 120_000,
  });
  const fxQ = useQuery({
    queryKey: ["fx-live"],
    queryFn: async () => (await apiGet<{ data?: FxItem[] }>("/brsapi/currency")).data ?? [],
    refetchInterval: 120_000,
  });
  const forecastAnchor = useMemo(() => {
    const findGold = (need: string) => goldQ.data?.find((x) => `${x.symbol ?? ""} ${x.name ?? ""} ${x.title ?? ""}`.includes(need));
    const findFx = (need: string) => fxQ.data?.find((x) => `${x.symbol}`.toLowerCase().includes(need.toLowerCase()));
    const raw =
      forecastSymbol === "gold_18k"
        ? findGold("18")?.price
        : forecastSymbol === "usd_irr_free"
          ? findFx("usd")?.price
          : findFx("xau")?.price;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : null;
  }, [forecastSymbol, goldQ.data, fxQ.data]);

  const forecastQ = useQuery({
    queryKey: ["forecast-gold", forecastSymbol, horizon, forecastAnchor, fxQ.data],
    queryFn: async () => {
      // No fabricated anchor: without a real last close there is no forecast.
      if (forecastAnchor === null) throw new Error("قیمت پایه برای پیش‌بینی در دسترس نیست");
      const usdIrr = fxQ.data?.find((x) => `${x.symbol}`.toLowerCase().includes("usd"))?.price;
      const qs = new URLSearchParams({ symbol: forecastSymbol, horizon: String(horizon), last_close: String(forecastAnchor) });
      if (usdIrr) qs.set("usd_irr", String(usdIrr));
      const r = await apiGet<{ data?: ForecastDetail }>(`/forecast?${qs.toString()}`);
      return r.data;
    },
    enabled: tab === "forecast" && !goldQ.isLoading && !fxQ.isLoading && forecastAnchor !== null,
    staleTime: 60_000,
  });

  const stats = useMemo(() => {
    const g = goldQ.data ?? [];
    const f = fxQ.data ?? [];
    return {
      goldCount: g.length,
      fxCount: f.length,
      bestGold: g.reduce<GoldItem | null>((a, b) => ((b.change_percent ?? -999) > (a?.change_percent ?? -999) ? b : a), null),
      bestFx: f.reduce<FxItem | null>((a, b) => ((b.change_percent ?? -999) > (a?.change_percent ?? -999) ? b : a), null),
    };
  }, [goldQ.data, fxQ.data]);

  const converter = useMemo(() => {
    const usdRaw = fxQ.data?.find((x) => x.symbol?.toLowerCase().includes("usd"))?.price;
    const goldRaw = goldQ.data?.find((x) => (x.symbol ?? x.name ?? "").includes("18"))?.price;
    const usd = Number(usdRaw);
    const gold = Number(goldRaw);
    const grams = Number.parseFloat(amount);
    const hasGold = Number.isFinite(gold) && gold > 0;
    const hasUsd = Number.isFinite(usd) && usd > 0;
    const toIrr = hasGold && Number.isFinite(grams) && grams >= 0 ? grams * gold : null;
    const toUsd = toIrr !== null && hasUsd ? toIrr / usd : null;
    return { usd: hasUsd ? usd : null, gold: hasGold ? gold : null, toIrr, toUsd };
  }, [amount, goldQ.data, fxQ.data]);

  return (
    <AppLayout>
      {/* ===== Hero با پس‌زمینه طلا و دلار ===== */}
      <div className="relative overflow-hidden rounded-[28px] border border-amber-500/20">
        {/* پس‌زمینه گرادینت + بافت */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1300] via-[#2a1f00] to-[#0f2a1a]" />
        <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: `radial-gradient(circle at 1px 1px, #facc15 1px, transparent 0)`, backgroundSize: "24px 24px" }} />
        {/* دایره‌های نور */}
        <div className="absolute -top-24 -right-24 w-[420px] h-[420px] bg-amber-400/20 rounded-full blur-[80px]" />
        <div className="absolute -bottom-32 -left-32 w-[520px] h-[520px] bg-emerald-400/15 rounded-full blur-[90px]" />
        {/* آیکون‌های محو پس‌زمینه */}
        <div className="absolute right-6 top-6 hidden lg:flex gap-3 opacity-20">
          <div className="w-14 h-14 rounded-2xl bg-amber-400/30 grid place-items-center"><Gem className="w-7 h-7 text-amber-200" /></div>
          <div className="w-14 h-14 rounded-2xl bg-emerald-400/30 grid place-items-center"><DollarSign className="w-7 h-7 text-emerald-200" /></div>
          <div className="w-14 h-14 rounded-2xl bg-amber-400/20 grid place-items-center"><Coins className="w-7 h-7 text-amber-100" /></div>
        </div>

        <div className="relative p-6 sm:p-8 lg:p-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-400/15 border border-amber-400/20 text-amber-200 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> به‌روزرسانی خودکار هر ۳۰ ثانیه
            <span className="opacity-60">•</span> <Clock className="w-3 h-3" /> {new Date().toLocaleDateString("fa-IR")}
          </div>
          <h1 className="mt-4 text-2xl sm:text-3xl font-black tracking-tight text-white">
            طلا، دلار و ارزها <span className="bg-gradient-to-l from-amber-300 to-yellow-500 bg-clip-text text-transparent">— لحظه‌ای و پیش‌بینی</span>
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-amber-100/70">قیمت لحظه‌ای طلای ۱۸عیار، سکه، اونس و نرخ دلار/یورو با پیش‌بینی هوشمند p50 + بازه 80% و ارزش منصفانه (اونس × دلار)</p>

          <div className="mt-6 grid grid-cols-3 gap-3 max-w-xl">
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3 backdrop-blur">
              <div className="text-[11px] text-amber-200/60">تعداد طلا</div><div className="text-lg font-bold text-white">{stats.goldCount || "—"}</div>
            </div>
            <div className="rounded-2xl bg-white/5 border border-white/10 p-3 backdrop-blur">
              <div className="text-[11px] text-emerald-200/60">تعداد ارز</div><div className="text-lg font-bold text-white">{stats.fxCount || "—"}</div>
            </div>
            <div className="rounded-2xl bg-gradient-to-br from-amber-400 to-yellow-600 p-3 text-amber-950">
              <div className="text-[11px] opacity-70 flex items-center gap-1"><Sparkles className="w-3 h-3" /> بهترین رشد</div>
              <div className="text-sm font-bold truncate">{stats.bestGold?.name ?? stats.bestFx?.symbol ?? "—"}</div>
            </div>
          </div>

          {/* تب‌های اصلی */}
          <div className="mt-8 flex gap-2">
            {([
              { k: "live", l: "قیمت لحظه‌ای", i: Activity },
              { k: "forecast", l: "پیش‌بینی", i: BarChart3 },
            ] as const).map((t) => (
              <button key={t.k} onClick={() => setTab(t.k)} className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold transition ${tab === t.k ? "bg-white text-zinc-900 shadow-lg" : "bg-white/10 text-white hover:bg-white/15 border border-white/10"}`}>
                <t.i className="w-4 h-4" /> {t.l}
              </button>
            ))}
          </div>
        </div>
      </div>

      {(goldQ.isError || fxQ.isError) && (
        <div className="mb-4 rounded-xl border border-rose-800/40 bg-rose-950/20 px-3 py-2 text-xs text-rose-300">
          دریافت قیمت‌های پایه ناموفق بود؛ عدد جایگزین ساخته نمی‌شود.
        </div>
      )}

      {/* ===== محتوای تب‌ها ===== */}
      <div className="mt-6">
        {tab === "live" && (
          <>
            <div className="flex gap-2 mb-4">
              {(["gold", "fx"] as const).map((k) => (
                <button key={k} onClick={() => setSubTab(k)} className={`px-4 py-2 rounded-full text-sm font-medium border transition ${subTab === k ? "bg-amber-500 text-white border-amber-500 shadow" : "bg-surface-800 text-surface-300 border-surface-700 hover:bg-surface-700"}`}>
                  {k === "gold" ? "💎 طلا و سکه" : "💵 ارزها"}
                </button>
              ))}
              <div className="ml-auto hidden sm:flex items-center gap-2 text-xs text-surface-500"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> به‌روزرسانی خودکار</div>
            </div>

            {subTab === "gold" ? (
              goldQ.isLoading ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}</div>
              ) : goldQ.isError ? (
                <div className="text-center py-14 text-rose-300">دریافت قیمت طلا و سکه ناموفق بود.</div>
              ) : goldQ.data?.length ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {goldQ.data.map((g, i) => {
                    const change = g.change_percent;
                    const up = change !== null && change !== undefined && change >= 0;
                    return (
                      <div key={i} className="relative overflow-hidden rounded-2xl border border-amber-500/15 bg-gradient-to-br from-zinc-900 to-zinc-800 p-4 hover:shadow-xl hover:shadow-amber-500/10 transition">
                        <div className="absolute -right-6 -top-6 w-20 h-20 bg-amber-400/15 rounded-full blur-2xl" />
                        <div className="flex items-start justify-between">
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-yellow-600 grid place-items-center text-white shadow"><Gem className="w-5 h-5" /></div>
                          <span className={`text-xs px-2 py-1 rounded-full font-mono ${change == null ? "bg-zinc-700/40 text-zinc-300" : up ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"}`}>
                            {change != null && (up ? <TrendingUp className="w-3 h-3 inline" /> : <TrendingDown className="w-3 h-3 inline" />)} {fmtPct(change)}
                          </span>
                        </div>
                        <div className="mt-3 text-sm font-bold text-white truncate">{g.name ?? g.title ?? g.symbol ?? "—"}</div>
                        <div className="text-[11px] text-zinc-400">{g.symbol ?? "—"} • {g.unit ?? "—"}</div>
                        <div className="mt-3 text-2xl font-black font-mono text-amber-300">{fmtMoney(g.price ?? g.price_close)}</div>
                        <div className="text-[11px] text-zinc-500">{g.date ?? ""} {g.time ?? ""}</div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-14 text-surface-500">داده‌ای نیست – ابتدا همگام‌سازی BrsApi را اجرا کنید</div>
              )
            ) : fxQ.isLoading ? (
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}</div>
            ) : fxQ.isError ? (
              <div className="text-center py-14 text-rose-300">دریافت نرخ ارزها ناموفق بود.</div>
            ) : fxQ.data?.length ? (
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {fxQ.data.map((c, i) => {
                  const change = c.change_percent;
                  const up = change !== null && change !== undefined && change >= 0;
                  return (
                    <div key={i} className="rounded-2xl border border-emerald-500/15 bg-gradient-to-br from-zinc-900 to-zinc-800 p-4 hover:shadow-xl hover:shadow-emerald-500/10 transition">
                      <div className="flex items-center justify-between">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 grid place-items-center text-white"><DollarSign className="w-5 h-5" /></div>
                        <span className={`text-xs font-mono ${change == null ? "text-zinc-400" : up ? "text-emerald-400" : "text-rose-400"}`}>{fmtPct(change)}</span>
                      </div>
                      <div className="mt-3 text-sm font-bold text-white truncate">{c.name ?? c.symbol ?? "—"}</div>
                      <div className="mt-1 text-xl font-black font-mono text-emerald-300">{fmtMoney(c.price)}</div>
                      <div className="text-[11px] text-zinc-500">{c.unit ?? "—"} • {c.time ?? ""}</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-14 text-surface-500">داده‌ای نیست</div>
            )}

            {/* مبدل سریع + API Info */}
            <div className="mt-6 grid lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 rounded-2xl border border-surface-800 bg-surface-900/40 p-4">
                <div className="text-sm font-bold flex items-center gap-2"><Coins className="w-4 h-4 text-amber-400" /> مبدل سریع</div>
                <div className="mt-3 flex flex-wrap gap-3 items-center">
                  <input value={amount} onChange={(e) => setAmount(e.target.value)} className="w-28 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700 text-sm font-mono" placeholder="گرم" inputMode="decimal" aria-label="وزن طلا به گرم" />
                  <span className="text-sm text-surface-400">گرم طلای ۱۸عیار ≈</span>
                  <span className="text-sm font-mono font-bold text-amber-300" dir="ltr">{converter.toIrr === null ? "—" : `${fmtMoney(converter.toIrr)} ریال`}</span>
                  <span className="text-sm text-surface-400">• معادل</span>
                  <span className="text-sm font-mono font-bold text-emerald-300" dir="ltr">{converter.toUsd === null ? "—" : `${fmtMoney(converter.toUsd, 2)} دلار`}</span>
                </div>
                <div className="mt-2 text-[11px] text-surface-500">نرخ‌ها از BrsApi لحظه‌ای؛ اگر نرخ دلار یا طلا نرسد، «—» نمایش داده می‌شود و عدد جایگزین ساخته نمی‌شود.</div>
              </div>
              <div className="rounded-2xl border border-amber-500/15 bg-amber-500/5 p-4">
                <div className="text-sm font-bold text-amber-300">API</div>
                <div className="mt-2 space-y-1 font-mono text-[11px] text-surface-400">
                  <div>GET /api/v1/brsapi/gold-coin</div>
                  <div>GET /api/v1/brsapi/currency</div>
                  <div>GET /api/v1/forecast?symbol=gold_18k&horizon=7</div>
                </div>
              </div>
            </div>
          </>
        )}

        {tab === "forecast" && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-4 flex flex-wrap gap-3 items-end">
              <label className="text-sm">نماد
                <select value={forecastSymbol} onChange={(e) => setForecastSymbol(e.target.value)} className="ml-2 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700 text-sm">
                  <option value="gold_18k">طلای ۱۸عیار</option>
                  <option value="usd_irr_free">دلار آزاد</option>
                  <option value="xau_usd">اونس جهانی</option>
                </select>
              </label>
              <label className="text-sm">افق
                <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className="ml-2 px-3 py-2 rounded-xl bg-surface-800 border border-surface-700 text-sm">
                  {[1,3,7,14,30,90].map((h) => <option key={h} value={h}>{h} روز</option>)}
                </select>
              </label>
              <div className="text-xs text-amber-200/70 mr-auto flex flex-col gap-1 text-left">
                <span>مدل: {forecastQ.data?.model ? `${forecastQ.data.model.name} ${forecastQ.data.model.version}` : "—"} • بازه ۸۰٪ روزانه</span>
                <span>قیمت پایه: {forecastAnchor === null ? "—" : `${fmtMoney(forecastAnchor)} (${forecastSymbol === "xau_usd" ? "دلار" : "ریال"})`}</span>
                {forecastQ.data?.meta?.disclaimer && <span className="text-amber-300/80">{forecastQ.data.meta.disclaimer}</span>}
              </div>
            </div>

            {forecastQ.isLoading ? <Skeleton className="h-64 rounded-2xl" /> : forecastQ.data ? (
              <>
                {/* نوار پیش‌بینی بصری */}
                <div className="rounded-2xl border border-surface-800 bg-gradient-to-br from-zinc-900 to-zinc-800 p-4">
                  <div className="text-sm font-bold text-white mb-3 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-amber-400" /> نمودار پیش‌بینی (p50 با بازه)</div>
                  <div className="flex items-end gap-1 h-32">
                    {forecastQ.data.forecast.slice(0, 14).map((f) => {
                      const max = Math.max(...forecastQ.data!.forecast.map((x) => x.p_upper));
                      const scale = Number.isFinite(max) && max > 0 ? max : null;
                      const h = scale === null ? 0 : (f.p50 / scale) * 100;
                      const lo = scale === null ? 0 : (f.p_lower / scale) * 100;
                      const hi = scale === null ? 0 : (f.p_upper / scale) * 100;
                      return (
                        <div key={f.date} className="flex-1 flex flex-col items-center gap-1">
                          <div className="relative w-full flex justify-center" style={{ height: "96px" }}>
                            <div className="absolute bg-amber-400/15 rounded-full" style={{ bottom: `${lo}%`, height: `${hi - lo}%`, width: "60%" }} />
                            <div className="absolute bg-gradient-to-t from-amber-500 to-yellow-400 rounded-full" style={{ bottom: `${h - 1}%`, height: "6px", width: "60%" }} />
                          </div>
                          <div className="text-[9px] font-mono text-zinc-500">{f.date.slice(5)}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="overflow-auto rounded-2xl border border-surface-800">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-800/60 text-surface-400"><tr><th className="p-3 text-right">تاریخ</th><th className="p-3">p50</th><th className="p-3">بازه پایین</th><th className="p-3">بازه بالا</th><th className="p-3">رشد</th></tr></thead>
                    <tbody>
                      {forecastQ.data.forecast.map((f) => (
                        <tr key={f.date} className="border-t border-surface-800 hover:bg-surface-800/30">
                          <td className="p-3 font-mono">{f.date}</td>
                          <td className="p-3 font-mono font-bold text-amber-300">{f.p50.toLocaleString("fa-IR")}</td>
                          <td className="p-3 font-mono text-zinc-500">{f.p_lower.toLocaleString("fa-IR")}</td>
                          <td className="p-3 font-mono text-zinc-500">{f.p_upper.toLocaleString("fa-IR")}</td>
                          <td className="p-3 font-mono">{Number.isFinite(f.direction_probability_up) ? `${(f.direction_probability_up * 100).toFixed(0)}%` : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="p-6 rounded-2xl border border-amber-500/20 bg-amber-500/5 text-sm text-amber-200">
                {forecastAnchor === null
                  ? "قیمت پایه واقعی (طلای ۱۸عیار / دلار / انس) در دسترس نیست؛ پیش‌بینی ساخته نمی‌شود."
                  : forecastQ.isError
                    ? "سرویس پیش‌بینی در دسترس نیست؛ عدد جایگزین نمایش داده نمی‌شود."
                    : "پیش‌بینی‌ای برای این نماد و افق موجود نیست."}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
