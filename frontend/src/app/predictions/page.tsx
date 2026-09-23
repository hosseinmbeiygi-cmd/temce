"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";
import {
  BarChart3,
  Gem,
  Globe,
  Sparkles,
  TrendingDown,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

/* ───────── Types ───────── */

interface ForecastPoint {
  date: string;
  p50: number;
  p_lower: number;
  p_upper: number;
  direction_probability_up: number;
}

interface Forecast {
  symbol: string;
  horizon_days: number;
  data_as_of?: string;
  model?: { name?: string; version?: string };
  forecast: ForecastPoint[];
  quality?: { status?: string };
  meta?: { disclaimer?: string };
}

interface LiveRow {
  symbol?: string;
  name?: string;
  title?: string;
  price?: number;
  price_close?: number;
  price_last?: number;
  change_percent?: number;
  price_change_pct?: number;
}

const HORIZONS = [1, 3, 7, 14, 30, 90];

const PREDICABLES = [
  { symbol: "gold_18k", label: "طلای ۱۸ عیار", unit: "ریال", type: "domestic" },
  { symbol: "xau_usd", label: "اونس جهانی طلا", unit: "دلار", type: "global" },
  { symbol: "xag_usd", label: "اونس جهانی نقره", unit: "دلار", type: "global" },
  { symbol: "usd_irr_free", label: "دلار آزاد", unit: "ریال", type: "domestic" },
] as const;

function findLive(list: LiveRow[], needle: string): LiveRow | undefined {
  return list.find((x) => `${x.symbol ?? ""} ${x.name ?? x.title ?? ""}`.toLowerCase().includes(needle.toLowerCase()));
}

const fa = (n: number) => n.toLocaleString("fa-IR");
const faPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

function MiniCurve({ pts, up }: { pts: ForecastPoint[]; up: boolean }) {
  if (!pts.length) return null;
  const vals = pts.flatMap((p) => [p.p_lower, p.p50, p.p_upper]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const W = 260;
  const H = 56;
  const x = (i: number) => (i / (pts.length - 1)) * W;
  const y = (v: number) => H - ((v - min) / range) * H;
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.p50).toFixed(1)}`).join(" ");
  const top = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.p_upper).toFixed(1)}`).join(" ");
  const bot = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.p_lower).toFixed(1)}`).join(" ");
  const area = `${top} L ${W} ${y(pts[pts.length - 1].p_upper)} ${bot.split(" L ").reverse().join(" L ")} Z`;
  const stroke = up ? "#10b981" : "#f43f5e";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-14" preserveAspectRatio="none" style={{ direction: "ltr" }}>
      <path d={area} fill={stroke} fillOpacity="0.12" />
      <path d={line} fill="none" stroke={stroke} strokeWidth="1.5" />
    </svg>
  );
}

export default function PredictionsPage() {
  const [open, setOpen] = useState<string | null>(null);

  /* Live anchors: gold-coin + currency from BrsApi — passed as last_close. */
  const goldQ = useQuery({
    queryKey: ["predictions-gold-live"],
    queryFn: async () => (await apiGet<{ data?: LiveRow[] }>("/brsapi/gold-coin")).data ?? [],
    staleTime: 120_000,
  });
  const fxQ = useQuery({
    queryKey: ["predictions-fx-live"],
    queryFn: async () => (await apiGet<{ data?: LiveRow[] }>("/brsapi/currency")).data ?? [],
    staleTime: 120_000,
  });
  const commoditiesQ = useQuery({
    queryKey: ["predictions-commodities-live"],
    queryFn: async () => {
      try {
        const r = await apiGet<unknown>("/brsapi/commodities?category=precious_metal");
        return extractArray<LiveRow>(r);
      } catch { return []; }
    },
    staleTime: 120_000,
  });

  const goldList = goldQ.data ?? [];
  const fxList = fxQ.data ?? [];
  const commList = commoditiesQ.data ?? [];

  const anchors = useMemo(() => {
    const g18 = findLive(goldList, "۱۸")?.price ?? findLive(goldList, "18")?.price ?? null;
    const usd = (fxList.find((x) => (x.symbol ?? "").toLowerCase().includes("usd"))?.price) ?? null;
    const xau = findLive(commList, "XAU")?.price ?? findLive(commList, "نیکل")?.price ?? null;
    const xag = findLive(commList, "XAG")?.price ?? null;
    return { gold_18k: g18, xau_usd: xau, xag_usd: xag, usd_irr_free: usd };
  }, [goldList, fxList, commList]);

  const ready = goldQ.data !== undefined && fxQ.data !== undefined;

  /* Fetch all 4 symbols × 6 horizons in one query. */
  const forecastsQ = useQuery<{ symbol: string; forecasts: Forecast[] }[]>({
    queryKey: ["predictions-all", anchors.gold_18k, anchors.xau_usd, anchors.xag_usd, anchors.usd_irr_free],
    enabled: ready && Boolean(anchors.gold_18k || anchors.xau_usd || anchors.xag_usd || anchors.usd_irr_free),
    queryFn: async () => {
      const results = await Promise.allSettled(
        PREDICABLES.map(async ({ symbol }): Promise<{ symbol: string; forecasts: Forecast[] }> => {
          const last = String(anchors[symbol] ?? "");
          if (!last) return { symbol, forecasts: [] };
          const settled = await Promise.allSettled(
            HORIZONS.map((h) =>
              apiGet<{ data?: Forecast }>(`/forecast?symbol=${symbol}&horizon=${h}&last_close=${last}`).then((r) => r?.data ?? (r as unknown as Forecast)),
            ),
          );
          const forecasts = settled
            .filter((s): s is PromiseFulfilledResult<Forecast> => s.status === "fulfilled")
            .map((s) => s.value)
            .filter((f) => f?.forecast?.length)
            .sort((a, b) => a.horizon_days - b.horizon_days);
          return { symbol, forecasts };
        }),
      );
      return results.filter((r): r is PromiseFulfilledResult<{ symbol: string; forecasts: Forecast[] }> => r.status === "fulfilled").map((r) => r.value);
    },
    staleTime: 60_000,
  });

  const isLoading = goldQ.isLoading || fxQ.isLoading || forecastsQ.isLoading;

  return (
    <AppLayout title="پیشبینی قیمتها" subtitle="پیشبینی هوشمند برای قیمتهای کلیدی بازار">
      {/* ─── Hero ─── */}
      <div className="mb-6 rounded-[28px] border border-violet-500/20 bg-gradient-to-l from-violet-950/40 via-surface-900 to-surface-900 relative overflow-hidden">
        <div className="absolute -top-20 -left-20 w-80 h-80 bg-violet-400/10 rounded-full blur-[90px]" />
        <div className="relative p-6 sm:p-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-200 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            دادههای واقعی • قیمت پایه از BrsApi
            <span className="opacity-60">•</span>
            <Sparkles className="w-3 h-3" />
            مدل xgboost_ensemble
          </div>
          <h1 className="mt-4 text-2xl sm:text-3xl font-black tracking-tight text-white">
            پیشبینی قیمتها <span className="text-violet-400">— همه بازارها</span>
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            پیشبینی p50 با بازه عدمقطعیت ۸۰٪ برای طلای ۱۸ عیار، اونس طلا، اونس نقره و دلار آزاد در افقهای ۱ تا ۹۰ روزه
          </p>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-2 text-xs text-amber-300">
        <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1">⚠️ پیشبینی صرفاً برای تحلیل است؛ تضمین بازده نیست.</span>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-64 w-full rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {PREDICABLES.map(({ symbol, label, unit, type }) => {
            const item = forecastsQ.data?.find((f) => f.symbol === symbol);
            const f = item?.forecasts?.[item.forecasts.length - 1];
            const horizonEntry = f ? item?.forecasts.find((x) => x.horizon_days === 7) ?? f : null;
            const anchor = anchors[symbol];
            const last = f?.forecast?.[f.forecast.length - 1];
            const first = f?.forecast?.[0];
            const change = last && first ? ((last.p50 / first.p50) - 1) * 100 : 0;
            const up = change >= 0;
            const isOpen = open === symbol;
            return (
              <div key={symbol} className="rounded-2xl border border-surface-800 bg-surface-900/40 p-4 hover:bg-surface-800/40 transition" dir="rtl">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-9 h-9 rounded-xl grid place-items-center ${type === "global" ? "bg-gradient-to-br from-cyan-400/30 to-blue-600/30 text-cyan-300" : "bg-gradient-to-br from-amber-400/30 to-yellow-600/30 text-amber-300"}`}>
                      {type === "global" ? <Globe className="w-4 h-4" /> : <Gem className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-surface-100">{label}</div>
                      <div className="font-mono text-[10px] text-surface-500">{symbol}</div>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full font-mono ${up ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"}`}>
                    {up ? <TrendingUp className="w-3 h-3 inline" /> : <TrendingDown className="w-3 h-3 inline" />} {faPct(change)}
                  </span>
                </div>

                <div className="mt-3 flex items-end justify-between gap-2">
                  <div>
                    <div className="text-[10px] text-surface-500">قیمت فعلی ({unit})</div>
                    <div className="mt-1 text-xl font-black font-mono text-slate-200">{anchor ? fa(anchor) : "—"}</div>
                  </div>
                  <div className="text-left">
                    <div className="text-[10px] text-surface-500">پیشبینی روز پایانی</div>
                    <div className={`mt-1 text-xl font-black font-mono ${up ? "text-emerald-300" : "text-rose-300"}`} dir="ltr">
                      {last ? last.p50.toFixed(2) : "—"}
                    </div>
                  </div>
                </div>

                {/* ─── Horizon chips ─── */}
                <div className="mt-3 grid grid-cols-3 gap-1.5">
                  {(item?.forecasts ?? []).map((hf) => {
                    const hp = hf.forecast[hf.forecast.length - 1];
                    const pct = first?.p50 ? ((hp.p50 / first.p50) - 1) * 100 : 0;
                    const hu = pct >= 0;
                    return (
                      <div key={hf.horizon_days} className="rounded-lg border border-surface-800 bg-surface-950/40 px-2 py-1.5 text-center">
                        <div className="text-[9px] text-surface-500">{hf.horizon_days} روز</div>
                        <div className={`mt-0.5 text-[11px] font-mono font-bold ${hu ? "text-emerald-400" : "text-rose-400"}`} dir="ltr">
                          {hp.p50.toFixed(2)}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {f && <div className="mt-3"><MiniCurve pts={f.forecast} up={up} /></div>}

                <button
                  onClick={() => setOpen(isOpen ? null : symbol)}
                  className="mt-4 w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-surface-700 bg-surface-800/60 px-3 py-2 text-xs font-bold text-surface-300 hover:bg-surface-800 transition"
                >
                  {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  {isOpen ? "بستن جزئیات" : "مشاهده جزئیات همه افقها"}
                </button>

                {isOpen && horizonEntry && (
                  <div className="mt-3 overflow-auto rounded-xl border border-surface-800">
                    <table className="w-full text-xs">
                      <thead className="bg-surface-800/60 text-surface-400">
                        <tr>
                          <th className="p-2 text-right">افق</th>
                          <th className="p-2 text-left">p50</th>
                          <th className="p-2 text-left">بازه</th>
                          <th className="p-2 text-left">احتمال رشد</th>
                        </tr>
                      </thead>
                      <tbody>
                        {horizonEntry.forecast.map((p, i) => (
                          <tr key={i} className="border-t border-surface-800">
                            <td className="p-2 font-mono text-surface-400">{p.date}</td>
                            <td className="p-2 font-mono font-bold text-surface-100" dir="ltr">{p.p50.toFixed(2)}</td>
                            <td className="p-2 font-mono text-surface-500" dir="ltr">{p.p_lower.toFixed(2)} – {p.p_upper.toFixed(2)}</td>
                            <td className={`p-2 font-mono font-bold ${p.direction_probability_up >= 0.5 ? "text-emerald-400" : "text-rose-400"}`}>
                              {(p.direction_probability_up * 100).toFixed(1)}٪
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!isLoading && forecastsQ.data?.every((f) => f.forecasts.length === 0) && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 text-sm text-amber-200/80">
          پیشبینی برای هیچ نمادی در دسترس نیست. ابتدا دادهی BrsApi و مدل پیشبینی را بررسی کنید.
        </div>
      )}

      <div className="mt-6 p-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 text-[12px] leading-6 text-amber-200/80">
        <BarChart3 className="w-4 h-4 inline ml-1" />
        پیشبینیها محصول مدل آماری xgboost_ensemble بر پایه قیمت آخرین معامله (last_close) و بازه عدمقطعیت منطقهمحور هستند. این خروجی ابزار تحلیل است نه توصیه معاملاتی.
      </div>
    </AppLayout>
  );
}