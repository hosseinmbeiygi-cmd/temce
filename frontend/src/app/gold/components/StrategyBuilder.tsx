"use client";

/**
 * IME option strategy builder for gold — signed legs in, payoff chart out.
 *
 * The API (``POST /gold/analytics/options/strategy``) owns the economics:
 * net debit, breakevens, max profit/loss and the pre-expiry value. The payoff
 * *curve* is pure intrinsic-value arithmetic on the same legs, so it is drawn
 * here and annotated with the API's extrema — it never becomes a second,
 * diverging pricing engine.
 */

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runOptionsStrategy } from "@/lib/goldApi";
import { cn } from "@/lib/cn";
import type { OptionsStrategyAnalysis, OptionsStrategyLeg } from "@/types/gold";

type PresetId = "straddle" | "strangle" | "vertical" | "iron_condor" | "covered_call";

const PRESETS: Array<{ id: PresetId; label: string; hint: string }> = [
  { id: "straddle", label: "استرادل", hint: "خرید کال و پوت با استرایک یکسان" },
  { id: "strangle", label: "استرانگل", hint: "خرید کال بالاتر و پوت پایین‌تر" },
  { id: "vertical", label: "ورتیکال کال", hint: "خرید کال پایین، فروش کال بالا" },
  { id: "iron_condor", label: "آیرون کوندور", hint: "دو اسپرد عمودی، سود در محدوده" },
  { id: "covered_call", label: "کاورد کال", hint: "دارایی پایه + فروش کال" },
];

function presetLegs(preset: PresetId, strike: number, width: number, premium: number): OptionsStrategyLeg[] {
  switch (preset) {
    case "straddle":
      return [
        { asset_type: "option", option_type: "call", strike, quantity: 1, premium },
        { asset_type: "option", option_type: "put", strike, quantity: 1, premium },
      ];
    case "strangle":
      return [
        { asset_type: "option", option_type: "put", strike: strike - width, quantity: 1, premium },
        { asset_type: "option", option_type: "call", strike: strike + width, quantity: 1, premium },
      ];
    case "vertical":
      return [
        { asset_type: "option", option_type: "call", strike, quantity: 1, premium },
        { asset_type: "option", option_type: "call", strike: strike + width, quantity: -1, premium: premium / 2 },
      ];
    case "iron_condor":
      return [
        { asset_type: "option", option_type: "put", strike: strike - 2 * width, quantity: 1, premium: premium / 4 },
        { asset_type: "option", option_type: "put", strike: strike - width, quantity: -1, premium: premium / 2 },
        { asset_type: "option", option_type: "call", strike: strike + width, quantity: -1, premium: premium / 2 },
        { asset_type: "option", option_type: "call", strike: strike + 2 * width, quantity: 1, premium: premium / 4 },
      ];
    case "covered_call":
      return [
        { asset_type: "underlying", option_type: "call", strike, quantity: 1, premium: 0, entry_price: strike },
        { asset_type: "option", option_type: "call", strike: strike + width, quantity: -1, premium },
      ];
  }
}

export interface PayoffPoint {
  price: number;
  pnl: number;
}

/**
 * Expiry P&L per underlying price for the given legs.
 *
 * Mirrors the leg convention the API documents: positive quantity is long,
 * negative is short, and an ``underlying`` leg contributes spot movement from
 * its ``entry_price``.
 */
export function payoffCurve(
  legs: OptionsStrategyLeg[],
  netDebit: number,
  min: number,
  max: number,
  steps = 60,
): PayoffPoint[] {
  if (legs.length === 0 || steps < 2 || !(max > min)) return [];
  const points: PayoffPoint[] = [];
  for (let index = 0; index <= steps; index += 1) {
    const price = min + ((max - min) * index) / steps;
    let payoff = 0;
    for (const leg of legs) {
      if ((leg.asset_type ?? "option") === "underlying") {
        payoff += (price - (leg.entry_price ?? price)) * leg.quantity;
        continue;
      }
      const intrinsic =
        leg.option_type === "call"
          ? Math.max(0, price - leg.strike)
          : Math.max(0, leg.strike - price);
      payoff += intrinsic * leg.quantity;
    }
    points.push({ price, pnl: payoff - netDebit });
  }
  return points;
}

const fmt = (value: number | null | undefined, digits = 0): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

export function PayoffChart({
  points,
  breakevens,
}: {
  points: PayoffPoint[];
  breakevens: number[];
}) {
  if (points.length < 2) {
    return (
      <div
        data-testid="payoff-empty"
        className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-zinc-500"
        style={{ borderColor: "var(--gd-border)" }}
      >
        برای رسم نمودار، حداقل یک پایه لازم است.
      </div>
    );
  }

  const w = 640;
  const h = 260;
  const pad = 40;
  const prices = points.map((point) => point.price);
  const pnls = points.map((point) => point.pnl);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const minPnl = Math.min(...pnls, 0);
  const maxPnl = Math.max(...pnls, 0);
  const spanPrice = maxPrice - minPrice || 1;
  const spanPnl = maxPnl - minPnl || 1;

  const x = (price: number) => pad + ((price - minPrice) / spanPrice) * (w - 2 * pad);
  const y = (pnl: number) => h - pad - ((pnl - minPnl) / spanPnl) * (h - 2 * pad);
  const zeroY = y(0);
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.price)} ${y(point.pnl)}`).join(" ");
  const area = `${line} L ${x(maxPrice)} ${zeroY} L ${x(minPrice)} ${zeroY} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="نمودار سود و زیان در سررسید" data-testid="payoff-chart">
      <line x1={pad} y1={zeroY} x2={w - pad} y2={zeroY} stroke="#52525b" strokeDasharray="4 4" strokeWidth={1} />
      <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#3f3f46" strokeWidth={1} />
      <path d={area} fill="rgba(251,191,36,0.08)" />
      <path d={line} fill="none" stroke="#fbbf24" strokeWidth={2} />
      {breakevens
        .filter((value) => Number.isFinite(value) && value >= minPrice && value <= maxPrice)
        .map((value) => (
          <g key={value}>
            <line x1={x(value)} y1={zeroY - 8} x2={x(value)} y2={zeroY + 8} stroke="#38bdf8" strokeWidth={2} />
            <text x={x(value)} y={zeroY - 12} fill="#38bdf8" fontSize={9} textAnchor="middle">
              {fmt(value)}
            </text>
          </g>
        ))}
      <text x={w - pad} y={pad + 10} fill="#a1a1aa" fontSize={10} textAnchor="end">
        حداکثر سود: {fmt(maxPnl)}
      </text>
      <text x={w - pad} y={h - pad - 6} fill="#a1a1aa" fontSize={10} textAnchor="end">
        حداکثر زیان: {fmt(minPnl)}
      </text>
    </svg>
  );
}

const inputCls =
  "w-full rounded-md border bg-zinc-950/40 px-2 py-1.5 text-xs text-zinc-100 outline-none transition focus:border-amber-500/60";

export default function StrategyBuilder() {
  const [preset, setPreset] = useState<PresetId>("straddle");
  const [strike, setStrike] = useState(1_000_000);
  const [width, setWidth] = useState(100_000);
  const [premium, setPremium] = useState(50_000);
  const [forward, setForward] = useState<number | "">("");
  const [days, setDays] = useState<number | "">("");
  const [legs, setLegs] = useState<OptionsStrategyLeg[]>(() =>
    presetLegs("straddle", 1_000_000, 100_000, 50_000),
  );

  const analysis = useMutation({
    mutationFn: () =>
      runOptionsStrategy({
        strategy: preset,
        legs,
        forward_price: forward === "" ? undefined : Number(forward),
        days_to_expiry: days === "" ? undefined : Number(days),
        risk_free_rate: 0,
      }),
  });

  const result: OptionsStrategyAnalysis | undefined = analysis.data;
  const curve = useMemo(() => {
    if (!result) return [];
    const strikes = legs.map((leg) => leg.strike).filter((value) => Number.isFinite(value) && value > 0);
    if (strikes.length === 0) return [];
    const low = Math.min(...strikes) * 0.6;
    const high = Math.max(...strikes) * 1.4;
    return payoffCurve(legs, result.net_debit, low, high);
  }, [legs, result]);

  const updatePreset = (next: PresetId) => {
    setPreset(next);
    setLegs(presetLegs(next, strike, width, premium));
    analysis.reset();
  };

  const updateLeg = (index: number, patch: Partial<OptionsStrategyLeg>) => {
    setLegs((prev) => prev.map((leg, current) => (current === index ? { ...leg, ...patch } : leg)));
    if (analysis.data) analysis.reset();
  };

  return (
    <section className="space-y-4" data-testid="strategy-builder">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-300">سازندهٔ استراتژی اختیار (طلا)</h2>
        <span className="text-[11px] text-zinc-500">قیمت‌ها به ریال؛ مدل Black-76 سمت سرور</span>
      </div>

      <div className="flex flex-wrap gap-1">
        {PRESETS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => updatePreset(item.id)}
            title={item.hint}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-[11px] transition",
              preset === item.id
                ? "border-amber-500/50 bg-amber-500/20 text-amber-300"
                : "text-zinc-400 hover:text-zinc-200",
            )}
            style={{ borderColor: preset === item.id ? undefined : "var(--gd-border)" }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-[10px] text-zinc-500">
          استرایک پایه
          <input
            type="number"
            min={1}
            step={10_000}
            value={strike}
            onChange={(event) => setStrike(Number(event.target.value) || 0)}
            className={`${inputCls} mt-1 tabular-nums`}
            style={{ borderColor: "var(--gd-border)" }}
          />
        </label>
        <label className="text-[10px] text-zinc-500">
          فاصلهٔ استرایک‌ها
          <input
            type="number"
            min={1}
            step={10_000}
            value={width}
            onChange={(event) => setWidth(Number(event.target.value) || 0)}
            className={`${inputCls} mt-1 tabular-nums`}
            style={{ borderColor: "var(--gd-border)" }}
          />
        </label>
        <label className="text-[10px] text-zinc-500">
          پرمیوم پایه
          <input
            type="number"
            min={0}
            step={1_000}
            value={premium}
            onChange={(event) => setPremium(Number(event.target.value) || 0)}
            className={`${inputCls} mt-1 tabular-nums`}
            style={{ borderColor: "var(--gd-border)" }}
          />
        </label>
        <label className="text-[10px] text-zinc-500">
          فوروارد (اختیاری)
          <input
            type="number"
            min={1}
            step={10_000}
            value={forward}
            onChange={(event) =>
              setForward(event.target.value === "" ? "" : Number(event.target.value))
            }
            className={`${inputCls} mt-1 tabular-nums`}
            style={{ borderColor: "var(--gd-border)" }}
            placeholder="برای پیش از سررسید"
          />
        </label>
        <label className="text-[10px] text-zinc-500">
          روز تا سررسید (اختیاری)
          <input
            type="number"
            min={1}
            step={1}
            value={days}
            onChange={(event) => setDays(event.target.value === "" ? "" : Number(event.target.value))}
            className={`${inputCls} mt-1 tabular-nums`}
            style={{ borderColor: "var(--gd-border)" }}
          />
        </label>
      </div>

      <div className="space-y-2">
        {legs.map((leg, index) => (
          <div
            key={`${leg.asset_type ?? "option"}-${index}`}
            className="grid grid-cols-2 gap-2 rounded-lg border p-2 md:grid-cols-5"
            style={{ borderColor: "var(--gd-border)" }}
          >
            <label className="text-[10px] text-zinc-500">
              نوع
              <select
                value={leg.asset_type ?? "option"}
                onChange={(event) =>
                  updateLeg(index, { asset_type: event.target.value as "option" | "underlying" })
                }
                className={`${inputCls} mt-1`}
                style={{ borderColor: "var(--gd-border)" }}
              >
                <option value="option">اختیار</option>
                <option value="underlying">دارایی پایه</option>
              </select>
            </label>
            {(leg.asset_type ?? "option") === "option" ? (
              <label className="text-[10px] text-zinc-500">
                کال/پوت
                <select
                  value={leg.option_type}
                  onChange={(event) =>
                    updateLeg(index, { option_type: event.target.value as "call" | "put" })
                  }
                  className={`${inputCls} mt-1`}
                  style={{ borderColor: "var(--gd-border)" }}
                >
                  <option value="call">کال</option>
                  <option value="put">پوت</option>
                </select>
              </label>
            ) : (
              <label className="text-[10px] text-zinc-500">
                قیمت خرید پایه
                <input
                  type="number"
                  value={leg.entry_price ?? 0}
                  onChange={(event) => updateLeg(index, { entry_price: Number(event.target.value) })}
                  className={`${inputCls} mt-1 tabular-nums`}
                  style={{ borderColor: "var(--gd-border)" }}
                />
              </label>
            )}
            <label className="text-[10px] text-zinc-500">
              استرایک
              <input
                type="number"
                min={1}
                value={leg.strike}
                onChange={(event) => updateLeg(index, { strike: Number(event.target.value) || 0 })}
                className={`${inputCls} mt-1 tabular-nums`}
                style={{ borderColor: "var(--gd-border)" }}
              />
            </label>
            <label className="text-[10px] text-zinc-500">
              تعداد (منفی = فروش)
              <input
                type="number"
                step={1}
                value={leg.quantity}
                onChange={(event) => updateLeg(index, { quantity: Number(event.target.value) || 0 })}
                className={`${inputCls} mt-1 tabular-nums`}
                style={{ borderColor: "var(--gd-border)" }}
              />
            </label>
            <label className="text-[10px] text-zinc-500">
              پرمیوم
              <input
                type="number"
                min={0}
                value={leg.premium}
                onChange={(event) => updateLeg(index, { premium: Number(event.target.value) || 0 })}
                className={`${inputCls} mt-1 tabular-nums`}
                style={{ borderColor: "var(--gd-border)" }}
              />
            </label>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="run-strategy"
          onClick={() => analysis.mutate()}
          disabled={analysis.isPending || legs.length === 0}
          className="rounded-md bg-amber-500 px-4 py-1.5 text-[11px] font-semibold text-zinc-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {analysis.isPending ? "در حال محاسبه…" : "تحلیل استراتژی"}
        </button>
        {analysis.isError && (
          <span className="text-[11px] text-rose-300">
            تحلیل ناموفق بود: {analysis.error instanceof Error ? analysis.error.message : "خطای نامشخص"}
          </span>
        )}
      </div>

      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--gd-border)" }}>
              <div className="text-[11px] text-zinc-500">حداکثر سود</div>
              <div className="mt-1 font-mono text-zinc-100">
                {result.max_profit_unbounded ? "نامحدود" : fmt(result.max_profit)}
              </div>
            </div>
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--gd-border)" }}>
              <div className="text-[11px] text-zinc-500">حداکثر زیان</div>
              <div className="mt-1 font-mono text-zinc-100">
                {result.max_loss_unbounded ? "نامحدود" : fmt(result.max_loss)}
              </div>
            </div>
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--gd-border)" }}>
              <div className="text-[11px] text-zinc-500">خالص پرداخت/دریافت</div>
              <div className="mt-1 font-mono text-zinc-100">{fmt(result.net_debit)}</div>
            </div>
            <div className="rounded-xl border p-3" style={{ borderColor: "var(--gd-border)" }}>
              <div className="text-[11px] text-zinc-500">نقاط سربه‌سر</div>
              <div className="mt-1 font-mono text-zinc-100">
                {result.breakevens.length > 0
                  ? result.breakevens.map((value) => fmt(value)).join(" ، ")
                  : "—"}
              </div>
            </div>
          </div>

          <PayoffChart points={curve} breakevens={result.breakevens} />

          {result.pre_expiry_error && (
            <p className="text-[11px] text-zinc-500">ارزش پیش از سررسید: {result.pre_expiry_error}</p>
          )}
        </div>
      )}
    </section>
  );
}
