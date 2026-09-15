"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, extractArray } from "@/lib/api";
import { fa, faDate, faPct } from "./helpers";

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
  model?: { name?: string; version?: string; note?: string };
  forecast: ForecastPoint[];
  quality?: { status?: string; is_stale?: boolean };
  risk?: { level?: string; volatility?: string };
  meta?: { disclaimer?: string; note?: string; fair_value_irr?: number | null; premium_log?: number | null } | null;
}

interface PriceItem {
  symbol?: string;
  price?: number;
}

const HORIZONS = [1, 3, 7, 14, 30, 90];

function BandChart({ points, anchor, height = 260 }: { points: ForecastPoint[]; anchor: number; height?: number }) {
  if (points.length < 2) {
    return <div className="grid h-40 place-items-center rounded-xl bg-soft text-xs text-ink-3">نقاط پیش‌بینی کافی نیست.</div>;
  }
  const w = 800;
  const padX = 64;
  const padY = 22;
  const plotR = w - 20;
  const all = [anchor, ...points.map((p) => p.p_lower), ...points.map((p) => p.p_upper)];
  const max = Math.max(...all);
  const min = Math.min(...all);
  const range = max - min || 1;
  const n = points.length;
  const x = (i: number) => padX + (i / Math.max(n - 1, 1)) * (plotR - padX);
  const y = (v: number) => padY + (1 - (v - min) / range) * (height - padY * 2);
  const band = [
    ...points.map((p, i) => `${x(i).toFixed(1)},${y(p.p_upper).toFixed(1)}`),
    ...points.map((p, i) => `${x(n - 1 - i).toFixed(1)},${y(p.p_lower).toFixed(1)}`),
  ].join(" ");
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.p50).toFixed(1)}`).join(" ");
  const step = Math.max(1, Math.floor(n / 6));

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet" style={{ direction: "ltr" }}>
      <polygon points={band} fill="#3b82f6" fillOpacity="0.14" stroke="#3b82f6" strokeOpacity="0.35" strokeWidth={1} />
      <polyline points={line} fill="none" stroke="#3b82f6" strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
      <line x1={padX} x2={plotR} y1={y(anchor)} y2={y(anchor)} stroke="#f59e0b" strokeDasharray="6 4" strokeWidth={1.2} />
      <text x={plotR + 2} y={y(anchor) + 3} fill="#f59e0b" fontSize={10} fontFamily="monospace">
        {anchor.toFixed(2)}
      </text>
      {points.map((p, i) =>
        i % step === 0 ? (
          <text key={p.date} x={x(i)} y={height - 5} fill="#94a3b8" fontSize={9} textAnchor="middle">
            {p.date?.slice(5) ?? ""}
          </text>
        ) : null,
      )}
      <text x={padX - 6} y={padY + 3} fill="#94a3b8" fontSize={10} fontFamily="monospace" textAnchor="end">
        {max.toFixed(2)}
      </text>
      <text x={padX - 6} y={height - padY + 3} fill="#94a3b8" fontSize={10} fontFamily="monospace" textAnchor="end">
        {min.toFixed(2)}
      </text>
    </svg>
  );
}

function bridge(direction: string, probUp: number): { text: string; tone: string } {
  if (direction === "up" && probUp >= 0.55) return { text: "سوگیری صعودی — خرید Call / فروش Put / Bull Call Spread", tone: "text-up" };
  if (direction === "down" && probUp <= 0.45) return { text: "سوگیری نزولی — خرید Put / فروش Call / Bear Put Spread", tone: "text-down" };
  if (direction === "neutral") return { text: "بازار خنثی — Iron Condor / Short Straddle برای فروش نوسان", tone: "text-warn" };
  return { text: "جهت‌گیری ضعیف — پوشش ریسک با Covered Call یا Protective Put", tone: "text-ink-2" };
}

export default function ForecastTab() {
  const [selected, setSelected] = useState(30);

  const priceQ = useQuery({
    queryKey: ["silver-spot-anchor"],
    queryFn: async () => {
      const r = await apiGet<{ success?: boolean; data?: PriceItem[] }>("/brsapi/commodities?category=precious_metal&limit=2000");
      const list = extractArray<PriceItem>(r?.data ?? r);
      return list.find((p) => (p.symbol ?? "").toUpperCase().includes("XAG"))?.price ?? null;
    },
    refetchInterval: 120_000,
  });

  const anchor = priceQ.data ?? null;

  const forecastQ = useQuery<{ list: Forecast[]; error: string | null }>({
    queryKey: ["silver-forecast-all", anchor],
    enabled: Boolean(anchor && anchor > 0),
    queryFn: async () => {
      const envelopes = await Promise.allSettled(
        HORIZONS.map((h) => apiGet<{ success: boolean; data?: Forecast; error?: { message?: string } }>(`/forecast?symbol=xag_usd&horizon=${h}&last_close=${anchor}`)),
      );
      const list: Forecast[] = [];
      let error: string | null = null;
      for (const envelope of envelopes) {
        if (envelope.status !== "fulfilled") continue;
        if (envelope.value?.success && envelope.value.data?.forecast?.length) {
          list.push(envelope.value.data);
        } else if (!error) {
          error = envelope.value?.error?.message ?? "پیش‌بینی در دسترس نیست";
        }
      }
      list.sort((a, b) => a.horizon_days - b.horizon_days);
      return { list, error };
    },
    staleTime: 300_000,
    retry: 1,
  });

  const active = useMemo(
    () => forecastQ.data?.list.find((f) => f.horizon_days === selected) ?? forecastQ.data?.list[0] ?? null,
    [forecastQ.data, selected],
  );

  const last = active && active.forecast.length > 0 ? active.forecast[active.forecast.length - 1] : null;
  const expected = last && anchor ? ((last.p50 - anchor) / anchor) * 100 : null;
  const direction = expected == null ? "neutral" : expected > 0.5 ? "up" : expected < -0.5 ? "down" : "neutral";
  const probUp = last?.direction_probability_up ?? 0.5;
  const advice = bridge(direction, probUp);

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] lg:p-5">
        <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
          <div>
            <h3 className="text-sm font-black text-ink">پیش‌بینی انس جهانی نقره (XAG/USD)</h3>
            <p className="mt-1 text-[11px] text-ink-3">
              مدل {active?.model?.name ?? "xgboost_ensemble"} · بازه اطمینان ۸۰٪ · داده تا {active?.data_as_of ? faDate(active.data_as_of) : "—"}
            </p>
          </div>
          <div className="flex flex-wrap gap-1 rounded-xl bg-soft p-1">
            {HORIZONS.map((h) => {
              const f = forecastQ.data?.list.find((x) => x.horizon_days === h);
              const pt = f && f.forecast.length > 0 ? f.forecast[f.forecast.length - 1] : undefined;
              return (
                <button
                  key={h}
                  onClick={() => setSelected(h)}
                  disabled={!f}
                  className={`rounded-lg px-3 py-1.5 text-[10px] font-bold transition disabled:opacity-40 ${selected === h ? "bg-card text-primary-600 shadow-sm" : "text-ink-3"}`}
                >
                  {h} روز
                  {pt ? <span className="ms-1 font-mono opacity-70">{fa(pt.p50)}</span> : null}
                </button>
              );
            })}
          </div>
        </div>

        {priceQ.isLoading || forecastQ.isLoading ? (
          <div className="mt-4 h-64 animate-pulse rounded-xl bg-soft" />
        ) : !active || !last ? (
          <p className="mt-4 rounded-xl bg-soft px-4 py-10 text-center text-xs text-warn">
            {forecastQ.data?.error ?? "پیش‌بینی در دسترس نیست — منبع XAG/USD یا سرویس پیش‌بینی پاسخ نداده است."}
          </p>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-xl bg-soft px-3 py-3 text-center">
                <p className="text-[10px] text-ink-3">قیمت پایه</p>
                <p className="mt-1 font-mono text-sm font-black text-ink" dir="ltr">{anchor?.toFixed(2) ?? "—"}</p>
              </div>
              <div className="rounded-xl bg-soft px-3 py-3 text-center">
                <p className="text-[10px] text-ink-3">پیش‌بینی {active.horizon_days} روزه</p>
                <p className="mt-1 font-mono text-sm font-black text-primary-600" dir="ltr">{fa(last.p50)}</p>
              </div>
              <div className="rounded-xl bg-soft px-3 py-3 text-center">
                <p className="text-[10px] text-ink-3">تغییر انتظاری</p>
                <p className={`mt-1 font-mono text-sm font-black ${(expected ?? 0) >= 0 ? "text-up" : "text-down"}`} dir="ltr">{faPct(expected)}</p>
              </div>
              <div className="rounded-xl bg-soft px-3 py-3 text-center">
                <p className="text-[10px] text-ink-3">احتمال رشد</p>
                <p className="mt-1 font-mono text-sm font-black text-ink" dir="ltr">{Math.round(probUp * 100)}%</p>
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-soft/60 p-2">
              <BandChart points={active.forecast} anchor={anchor ?? 0} />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-ink-3">
              <span className="rounded-full bg-soft px-2 py-1">کف بازه: <b className="font-mono text-ink-2" dir="ltr">{fa(last.p_lower)}</b></span>
              <span className="rounded-full bg-soft px-2 py-1">سقف بازه: <b className="font-mono text-ink-2" dir="ltr">{fa(last.p_upper)}</b></span>
              {active.quality?.status && (
                <span className="rounded-full bg-soft px-2 py-1">
                  کیفیت داده: <b className="text-ink-2">{active.quality.status === "good" ? "مطلوب" : active.quality.status === "stale_anchor" ? "تاریخچه کهنه" : active.quality.status}</b>
                </span>
              )}
              {active.risk?.level && <span className="rounded-full bg-soft px-2 py-1">ریسک: <b className="text-ink-2">{active.risk.level} / {active.risk.volatility}</b></span>}
            </div>
            {active.meta?.note && <p className="mt-2 text-[10px] text-warn">{active.meta.note}</p>}

            <div className={`mt-3 rounded-xl border border-line px-3 py-2.5 text-[11px] font-bold ${advice.tone}`}>{advice.text}</div>
            {active.model?.note && <p className="mt-2 text-[10px] text-ink-3">{active.model.note}</p>}
            {active.meta?.disclaimer && <p className="mt-1 text-[10px] text-warn">{active.meta.disclaimer}</p>}
          </>
        )}
      </section>
    </div>
  );
}
