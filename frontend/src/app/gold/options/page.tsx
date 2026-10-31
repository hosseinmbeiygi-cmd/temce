"use client";

/**
 * Gold derivatives and risk workspace.
 *
 * Combines the public scenario catalogue with the pure portfolio stress
 * calculator. Nothing on this page places orders or mutates account state.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import OptionsChainAnalytics from "../components/OptionsChainAnalytics";
import StrategyBuilder from "../components/StrategyBuilder";
import {
  getGoldRiskScenarios,
  runGoldRiskStress,
  type GoldRiskAssetType,
  type GoldRiskDirection,
  type GoldRiskPositionInput,
  type GoldRiskShocks,
  type GoldRiskStressInput,
} from "@/lib/goldApi";

const ASSET_LABELS: Record<GoldRiskAssetType, string> = {
  gold: "طلا",
  coin: "سکه",
  fund: "صندوق",
  etf: "ETF",
  certificate: "گواهی",
  futures: "آتی",
  option: "اختیار",
  fx: "ارز",
  cash: "نقد",
  other: "سایر",
};

const ASSET_TYPES = Object.keys(ASSET_LABELS) as GoldRiskAssetType[];

const RISK_LABELS: Record<string, string> = {
  LOW: "کم",
  MEDIUM: "متوسط",
  HIGH: "بالا",
  CRITICAL: "بحرانی",
  UNKNOWN: "نامشخص",
};

// Educational sample only. It is never the initial portfolio and is always
// labelled; the real portfolio comes from the user's own inputs.
const SAMPLE_EQUITY = 1_000_000_000;

const SAMPLE_POSITIONS: GoldRiskPositionInput[] = [
  {
    symbol: "IR_COIN_EMAMI",
    asset_type: "coin",
    direction: "long",
    exposure_irr: 500_000_000,
    delta: 1,
    vega_irr_per_vol_point: 0,
    margin_irr: 100_000_000,
    maintenance_margin_irr: 50_000_000,
  },
  {
    symbol: "ZARFSHANG",
    asset_type: "etf",
    direction: "long",
    exposure_irr: 250_000_000,
    delta: 1,
    vega_irr_per_vol_point: 0,
    margin_irr: 0,
    maintenance_margin_irr: 0,
  },
];

const inputCls =
  "w-full rounded-md border bg-zinc-950/40 px-2 py-1.5 text-xs text-zinc-100 outline-none transition focus:border-amber-500/60";

const cardStyle = {
  background: "var(--gd-bg-2)",
  borderColor: "var(--gd-border)",
} as const;

const fmt = (value: number | null | undefined, digits = 0): string => {
  if (value === null || value === undefined || !isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (value: number | null | undefined, digits = 1): string => {
  if (value === null || value === undefined || !isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${fmt(value, digits)}٪`;
};

const fmtIrr = (value: number | null | undefined): string => {
  if (value === null || value === undefined || !isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${fmt(value / 1_000_000_000, 2)} میلیارد`;
  if (abs >= 1_000_000) return `${fmt(value / 1_000_000, 1)} میلیون`;
  return fmt(value);
};

const toneCls = (value: number): string => {
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-zinc-400";
};

const riskTone = (level: string): string => {
  if (level === "CRITICAL") return "bg-rose-950/40 text-rose-300 ring-rose-700/40";
  if (level === "HIGH") return "bg-orange-950/40 text-orange-300 ring-orange-700/40";
  if (level === "MEDIUM") return "bg-amber-950/40 text-amber-300 ring-amber-700/40";
  if (level === "LOW") return "bg-emerald-950/40 text-emerald-300 ring-emerald-700/40";
  return "bg-zinc-900/40 text-zinc-300 ring-zinc-700/40";
};

function shockChips(shocks: GoldRiskShocks) {
  return [
    {
      key: "xau",
      label: "اونس جهانی",
      text: fmtPct(shocks.xau_usd_pct * 100),
      tone: shocks.xau_usd_pct,
    },
    {
      key: "usd",
      label: "دلار آزاد",
      text: fmtPct(shocks.usd_irr_pct * 100),
      tone: shocks.usd_irr_pct,
    },
    {
      key: "premium",
      label: "حباب محلی",
      text: fmtPct(shocks.local_premium_pct * 100),
      tone: shocks.local_premium_pct,
    },
    {
      key: "discount",
      label: "تخفیف صندوق",
      text: fmtPct(shocks.fund_discount_pct * 100),
      tone: shocks.fund_discount_pct,
    },
    {
      key: "vol",
      label: "نوسان ضمنی",
      text: `${shocks.volatility_points > 0 ? "+" : ""}${fmt(
        shocks.volatility_points * 100,
        0,
      )} واحد`,
      tone: shocks.volatility_points,
    },
    {
      key: "liquidity",
      label: "هزینهٔ خروج",
      text: `${fmt(shocks.liquidity_haircut_pct * 100, 1)}٪`,
      tone: -1,
    },
  ];
}

function Metric({
  label,
  value,
  sub,
  testId,
  raw,
}: {
  label: string;
  value: string;
  sub?: string;
  testId?: string;
  raw?: number | null;
}) {
  return (
    <div className="rounded-xl border p-3" style={cardStyle}>
      <div className="text-[11px] text-zinc-500">{label}</div>
      <div
        className="mt-1 text-lg font-semibold tabular-nums text-zinc-100"
        data-testid={testId}
        data-raw={raw ?? undefined}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-[10px] leading-4 text-zinc-500">{sub}</div>}
    </div>
  );
}

export default function GoldDerivativesRiskPage() {
  const [equity, setEquity] = useState<number>(0);
  const [positions, setPositions] = useState<GoldRiskPositionInput[]>([]);
  const [isSample, setIsSample] = useState(false);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);

  const scenariosQuery = useQuery({
    queryKey: ["gold", "risk", "scenarios"],
    queryFn: getGoldRiskScenarios,
    staleTime: 5 * 60_000,
  });

  const stress = useMutation({
    mutationFn: (input: GoldRiskStressInput) => runGoldRiskStress(input),
  });

  const scenarios = scenariosQuery.data ?? [];
  const result = stress.data;
  const selected = result
    ? result.scenarios.find((row) => row.scenario_id === selectedScenarioId) ??
      result.worst_case
    : null;

  const clearResult = () => {
    if (stress.data) stress.reset();
  };

  const updatePosition = (
    index: number,
    patch: Partial<GoldRiskPositionInput>,
  ) => {
    clearResult();
    setIsSample(false);
    setPositions((prev) =>
      prev.map((position, current) =>
        current === index ? { ...position, ...patch } : position,
      ),
    );
  };

  const addPosition = () => {
    clearResult();
    setIsSample(false);
    setPositions((prev) => [
      ...prev,
      {
        symbol: `POSITION_${prev.length + 1}`,
        asset_type: "gold",
        direction: "long",
        exposure_irr: 100_000_000,
        delta: 1,
        vega_irr_per_vol_point: 0,
        margin_irr: 0,
        maintenance_margin_irr: 0,
      },
    ]);
  };

  const removePosition = (index: number) => {
    clearResult();
    setIsSample(false);
    setPositions((prev) => prev.filter((_, current) => current !== index));
  };

  const resetPortfolio = () => {
    stress.reset();
    setEquity(0);
    setPositions([]);
    setIsSample(false);
    setSelectedScenarioId(null);
  };

  const loadSample = () => {
    stress.reset();
    setEquity(SAMPLE_EQUITY);
    setPositions(SAMPLE_POSITIONS.map((position) => ({ ...position })));
    setIsSample(true);
    setSelectedScenarioId(null);
  };

  const runStress = () => {
    setSelectedScenarioId(null);
    stress.mutate({
      equity_irr: equity,
      positions: positions.map((position) => ({ ...position })),
    });
  };

  const numberValue = (value: string): number => {
    if (value === "") return 0;
    const parsed = Number(value);
    return isFinite(parsed) ? parsed : 0;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">مشتقه‌ها و ریسک طلا</h1>
          <p className="mt-1 text-xs text-zinc-500">
            استرس‌تست پورتفوی، ریسک مارجین و حساسیت به شوک‌های بازار ایران
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <Link
            href="/options"
            className="rounded-md border px-2.5 py-1.5 text-zinc-300 transition hover:text-amber-300"
            style={{ borderColor: "var(--gd-border)" }}
          >
            زنجیرهٔ اختیار IME
          </Link>
          <Link
            href="/gold/futures"
            className="rounded-md border px-2.5 py-1.5 text-zinc-300 transition hover:text-amber-300"
            style={{ borderColor: "var(--gd-border)" }}
          >
            آتی سکه
          </Link>
          <Link
            href="/gold/analytics"
            className="rounded-md border px-2.5 py-1.5 text-zinc-300 transition hover:text-amber-300"
            style={{ borderColor: "var(--gd-border)" }}
          >
            تحلیل بازار
          </Link>
          <Link
            href="/gold/portfolio"
            className="rounded-md border px-2.5 py-1.5 text-zinc-300 transition hover:text-amber-300"
            style={{ borderColor: "var(--gd-border)" }}
          >
            پورتفوی
          </Link>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-zinc-200">کاتالوگ سناریوها</h2>
          <span className="text-[11px] text-zinc-500">
            {scenarios.length > 0 ? `${fmt(scenarios.length)} سناریوی آماده` : "—"}
          </span>
        </div>

        {scenariosQuery.isLoading && (
          <div className="rounded-xl border p-4 text-xs text-zinc-500" style={cardStyle}>
            در حال دریافت سناریوها…
          </div>
        )}
        {scenariosQuery.isError && (
          <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300">
            دریافت کاتالوگ سناریوها ناموفق بود. اتصال API را بررسی کنید.
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {scenarios.map((scenario) => (
            <article
              key={scenario.scenario_id}
              data-testid={`scenario-card-${scenario.scenario_id}`}
              className="rounded-xl border p-3"
              style={cardStyle}
            >
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold text-zinc-100">
                  {scenario.name_fa}
                </h3>
                <span className="text-[10px] text-zinc-500" dir="ltr">
                  {scenario.name_en}
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-5 text-zinc-400">
                {scenario.description_fa}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {shockChips(scenario.shocks).map((chip) => (
                  <span
                    key={chip.key}
                    className={`rounded-md bg-zinc-900/60 px-1.5 py-0.5 text-[10px] ${toneCls(
                      chip.tone,
                    )}`}
                  >
                    {chip.label}: {chip.text}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-4 rounded-xl border p-4" style={cardStyle}>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
              پورتفوی تحت آزمون
              {isSample && (
                <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-300 ring-1 ring-amber-500/30">
                  نمونهٔ آموزشی — دارایی واقعی شما نیست
                </span>
              )}
            </h2>
            <p className="mt-1 text-[11px] leading-5 text-zinc-500">
              ارزش اسمی موقعیت‌ها به ریال است. دلتا و وگا فقط برای اختیارها اثر
              معنادار دارند؛ برای سایر دارایی‌ها صفر بگذارید. با تغییر هر مقدار،
              برچسب نمونه برداشته می‌شود.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[11px] text-zinc-400">
              سرمایهٔ پایه (ریال)
              <input
                data-testid="equity-input"
                type="number"
                min={1}
                step={1_000_000}
                value={equity}
                onChange={(event) => {
                  clearResult();
                  setIsSample(false);
                  setEquity(numberValue(event.target.value));
                }}
                className={`${inputCls} mt-1 w-44`}
                style={{ borderColor: "var(--gd-border)" }}
              />
            </label>
            <button
              type="button"
              onClick={loadSample}
              className="rounded-md border px-3 py-1.5 text-[11px] text-amber-300 transition hover:bg-amber-500/10"
              style={{ borderColor: "var(--gd-border)" }}
            >
              بارگذاری نمونهٔ آموزشی
            </button>
            <button
              type="button"
              onClick={resetPortfolio}
              className="rounded-md border px-3 py-1.5 text-[11px] text-zinc-300 transition hover:text-amber-300"
              style={{ borderColor: "var(--gd-border)" }}
            >
              پاک‌سازی
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {positions.length === 0 && (
            <div className="rounded-lg border border-dashed p-5 text-center text-xs text-zinc-500" style={{ borderColor: "var(--gd-border)" }}>
              هیچ موقعیتی ثبت نشده است. «افزودن موقعیت» را بزنید یا برای آشنایی، نمونهٔ آموزشی را بارگذاری کنید.
            </div>
          )}
          {positions.map((position, index) => (
            <div
              key={`${position.symbol}-${index}`}
              className="rounded-lg border p-3"
              style={{ borderColor: "var(--gd-border)" }}
            >
              <div className="flex items-center gap-2">
                <input
                  aria-label={`نماد موقعیت ${index + 1}`}
                  value={position.symbol}
                  onChange={(event) =>
                    updatePosition(index, { symbol: event.target.value })
                  }
                  className={inputCls}
                  style={{ borderColor: "var(--gd-border)" }}
                  placeholder="نماد"
                />
                <button
                  type="button"
                  onClick={() => removePosition(index)}
                  disabled={positions.length <= 1}
                  className="shrink-0 rounded-md border border-rose-900/40 px-2.5 py-1.5 text-[11px] text-rose-300 transition hover:bg-rose-950/30 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  حذف
                </button>
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                <label className="text-[10px] text-zinc-500">
                  نوع دارایی
                  <select
                    value={position.asset_type}
                    onChange={(event) =>
                      updatePosition(index, {
                        asset_type: event.target.value as GoldRiskAssetType,
                      })
                    }
                    className={`${inputCls} mt-1`}
                    style={{ borderColor: "var(--gd-border)" }}
                  >
                    {ASSET_TYPES.map((assetType) => (
                      <option key={assetType} value={assetType}>
                        {ASSET_LABELS[assetType]}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-[10px] text-zinc-500">
                  جهت
                  <select
                    value={position.direction}
                    onChange={(event) =>
                      updatePosition(index, {
                        direction: event.target.value as GoldRiskDirection,
                      })
                    }
                    className={`${inputCls} mt-1`}
                    style={{ borderColor: "var(--gd-border)" }}
                  >
                    <option value="long">خرید</option>
                    <option value="short">فروش</option>
                  </select>
                </label>

                <label className="text-[10px] text-zinc-500">
                  ارزش اسمی (ریال)
                  <input
                    type="number"
                    min={0}
                    step={1_000_000}
                    value={position.exposure_irr}
                    onChange={(event) =>
                      updatePosition(index, {
                        exposure_irr: numberValue(event.target.value),
                      })
                    }
                    className={`${inputCls} mt-1 tabular-nums`}
                    style={{ borderColor: "var(--gd-border)" }}
                  />
                </label>

                <label className="text-[10px] text-zinc-500">
                  مارجین (ریال)
                  <input
                    type="number"
                    min={0}
                    step={1_000_000}
                    value={position.margin_irr ?? 0}
                    onChange={(event) =>
                      updatePosition(index, {
                        margin_irr: numberValue(event.target.value),
                      })
                    }
                    className={`${inputCls} mt-1 tabular-nums`}
                    style={{ borderColor: "var(--gd-border)" }}
                  />
                </label>

                <label className="text-[10px] text-zinc-500">
                  مارجین نگهداری (ریال)
                  <input
                    type="number"
                    min={0}
                    step={1_000_000}
                    value={position.maintenance_margin_irr ?? 0}
                    onChange={(event) =>
                      updatePosition(index, {
                        maintenance_margin_irr: numberValue(event.target.value),
                      })
                    }
                    className={`${inputCls} mt-1 tabular-nums`}
                    style={{ borderColor: "var(--gd-border)" }}
                  />
                </label>

                <label className="text-[10px] text-zinc-500">
                  دلتا
                  <input
                    type="number"
                    step={0.05}
                    value={position.delta ?? 1}
                    onChange={(event) =>
                      updatePosition(index, {
                        delta: numberValue(event.target.value),
                      })
                    }
                    className={`${inputCls} mt-1 tabular-nums`}
                    style={{ borderColor: "var(--gd-border)" }}
                  />
                </label>

                <label className="text-[10px] text-zinc-500">
                  وگا (ریال/واحد نوسان)
                  <input
                    type="number"
                    step={1_000_000}
                    value={position.vega_irr_per_vol_point ?? 0}
                    onChange={(event) =>
                      updatePosition(index, {
                        vega_irr_per_vol_point: numberValue(event.target.value),
                      })
                    }
                    className={`${inputCls} mt-1 tabular-nums`}
                    style={{ borderColor: "var(--gd-border)" }}
                  />
                </label>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={addPosition}
            className="rounded-md border px-3 py-1.5 text-[11px] text-zinc-300 transition hover:text-amber-300"
            style={{ borderColor: "var(--gd-border)" }}
          >
            افزودن موقعیت
          </button>
          <button
            type="button"
            data-testid="run-stress"
            onClick={runStress}
            disabled={stress.isPending || equity <= 0 || positions.length === 0}
            className="rounded-md bg-amber-500 px-4 py-1.5 text-[11px] font-semibold text-zinc-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {stress.isPending ? "در حال محاسبه…" : "اجرای استرس‌تست"}
          </button>
          {equity <= 0 && (
            <span className="text-[11px] text-rose-300">
              سرمایهٔ پایه باید بزرگ‌تر از صفر باشد.
            </span>
          )}
          {positions.length === 0 && (
            <span className="text-[11px] text-rose-300">
              حداقل یک موقعیت برای استرس‌تست لازم است.
            </span>
          )}
          {stress.isError && (
            <span className="text-[11px] text-rose-300">{stress.error.message}</span>
          )}
        </div>
      </section>

      {!result && !stress.isPending && (
        <div
          className="rounded-xl border border-dashed p-6 text-center"
          style={{ borderColor: "var(--gd-border)" }}
        >
          <p className="text-sm text-zinc-300">آمادهٔ اجرا</p>
          <p className="mt-1 text-xs text-zinc-500">
            سرمایه و موقعیت‌ها را تنظیم کنید، سپس «اجرای استرس‌تست» را بزنید.
          </p>
        </div>
      )}

      {result && !result.available && (
        <div className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-4 text-xs text-amber-200">
          موقعیتی برای آزمون ثبت نشده است؛ حداقل یک موقعیت اضافه کنید.
        </div>
      )}

      {result?.available && (
        <>
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-zinc-200">خلاصهٔ ریسک</h2>
              <span
                data-testid="risk-level"
                className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ring-1 ${riskTone(
                  result.risk_level,
                )}`}
              >
                سطح ریسک: {RISK_LABELS[result.risk_level] ?? result.risk_level} ·{" "}
                {result.risk_level}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <Metric
                label="بدترین سود/زیان"
                value={fmtIrr(result.worst_case.pnl_irr)}
                sub={`${result.worst_case.name_fa} · ${fmtPct(
                  result.worst_case.pnl_pct_of_equity,
                )} سرمایه`}
                testId="worst-pnl"
                raw={result.worst_case.pnl_irr}
              />
              <Metric
                label="سرمایهٔ پس از شوک"
                value={fmtIrr(result.worst_case.post_equity_irr)}
                sub={`از ${fmtIrr(result.equity_irr)} سرمایهٔ پایه`}
                testId="post-equity"
                raw={result.worst_case.post_equity_irr}
              />
              <Metric
                label="اهرم ناخالص"
                value={`${fmt(result.gross_leverage_ratio, 2)}×`}
                sub={`مواجههٔ ناخالص ${fmtIrr(result.gross_exposure_irr)}`}
                testId="gross-leverage"
                raw={result.gross_leverage_ratio}
              />
              <Metric
                label="استفاده از مارجین"
                value={fmtPct(result.margin_utilization_pct)}
                sub={`مارجین ${fmtIrr(result.margin_irr)} · نگهداری ${fmtIrr(
                  result.maintenance_margin_irr,
                )}`}
              />
              <Metric
                label="تمرکز (HHI)"
                value={fmt(result.concentration_hhi, 3)}
                sub={`بزرگ‌ترین موقعیت ${fmtPct(result.largest_position_pct)}`}
              />
              <Metric
                label="مواجههٔ خالص"
                value={fmtIrr(result.net_exposure_irr)}
                sub={`${fmtPct(result.net_exposure_pct_of_equity)} سرمایه`}
              />
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-zinc-200">جدول سناریوها</h2>
              <span className="text-[11px] text-zinc-500">
                برای دیدن جزئیات، روی هر ردیف بزنید
              </span>
            </div>
            <div
              className="overflow-x-auto rounded-xl border"
              style={{ borderColor: "var(--gd-border)" }}
            >
              <table className="w-full min-w-[720px] text-right text-xs">
                <thead className="bg-zinc-900/60 text-zinc-400">
                  <tr>
                    <th className="px-3 py-2 font-medium">سناریو</th>
                    <th className="px-3 py-2 font-medium">سود/زیان</th>
                    <th className="px-3 py-2 font-medium">٪ سرمایه</th>
                    <th className="px-3 py-2 font-medium">سرمایهٔ پس از شوک</th>
                    <th className="px-3 py-2 font-medium">مارجین کال</th>
                    <th className="px-3 py-2 font-medium">لیکوئیدیشن</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scenarios.map((row) => {
                    const active = selected?.scenario_id === row.scenario_id;
                    return (
                      <tr
                        key={row.scenario_id}
                        data-testid={`scenario-row-${row.scenario_id}`}
                        onClick={() => setSelectedScenarioId(row.scenario_id)}
                        className={`cursor-pointer border-t transition ${
                          active ? "bg-amber-500/10" : "hover:bg-zinc-900/40"
                        }`}
                        style={{ borderColor: "var(--gd-border)" }}
                      >
                        <td className="px-3 py-2">
                          <div className="font-medium text-zinc-200">{row.name_fa}</div>
                          <div className="text-[10px] text-zinc-500" dir="ltr">
                            {row.name_en}
                          </div>
                        </td>
                        <td className={`px-3 py-2 tabular-nums ${toneCls(row.pnl_irr)}`}>
                          {fmtIrr(row.pnl_irr)}
                        </td>
                        <td
                          className={`px-3 py-2 tabular-nums ${toneCls(
                            row.pnl_pct_of_equity ?? 0,
                          )}`}
                        >
                          {fmtPct(row.pnl_pct_of_equity)}
                        </td>
                        <td className="px-3 py-2 tabular-nums text-zinc-300">
                          {fmtIrr(row.post_equity_irr)}
                        </td>
                        <td className="px-3 py-2">
                          {row.margin_call ? (
                            <span className="text-rose-300">بله</span>
                          ) : (
                            <span className="text-emerald-300">خیر</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {row.forced_liquidation ? (
                            <span className="text-rose-300">بله</span>
                          ) : (
                            <span className="text-emerald-300">خیر</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {selected && (
            <section className="space-y-3 rounded-xl border p-4" style={cardStyle}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-zinc-100">
                    جزئیات: {selected.name_fa}
                  </h2>
                  <p className="mt-1 text-[11px] leading-5 text-zinc-500">
                    {selected.description_fa}
                  </p>
                </div>
                <div className="text-[11px] text-zinc-400">
                  پوشش مارجین:{" "}
                  {selected.maintenance_coverage_ratio === null
                    ? "—"
                    : `${fmt(selected.maintenance_coverage_ratio, 2)}×`}
                </div>
              </div>

              {selected.positions.length === 0 ? (
                <p className="text-xs text-zinc-500">موقعیتی ثبت نشده است.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[620px] text-right text-[11px]">
                    <thead className="text-zinc-500">
                      <tr>
                        <th className="px-2 py-2 font-medium">نماد</th>
                        <th className="px-2 py-2 font-medium">نوع</th>
                        <th className="px-2 py-2 font-medium">جهت</th>
                        <th className="px-2 py-2 font-medium">بازده بازار</th>
                        <th className="px-2 py-2 font-medium">سود/زیان</th>
                        <th className="px-2 py-2 font-medium">اثر وگا</th>
                        <th className="px-2 py-2 font-medium">هزینهٔ نقدشوندگی</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.positions.map((position, index) => (
                        <tr
                          key={`${position.symbol}-${index}`}
                          className="border-t"
                          style={{ borderColor: "var(--gd-border)" }}
                        >
                          <td className="px-2 py-2 text-zinc-200">{position.symbol}</td>
                          <td className="px-2 py-2 text-zinc-400">
                            {ASSET_LABELS[position.asset_type]}
                          </td>
                          <td className="px-2 py-2 text-zinc-400">
                            {position.direction === "long" ? "خرید" : "فروش"}
                          </td>
                          <td
                            className={`px-2 py-2 tabular-nums ${toneCls(
                              position.market_return_pct,
                            )}`}
                          >
                            {fmtPct(position.market_return_pct)}
                          </td>
                          <td
                            className={`px-2 py-2 tabular-nums ${toneCls(
                              position.pnl_irr,
                            )}`}
                          >
                            {fmtIrr(position.pnl_irr)}
                          </td>
                          <td className="px-2 py-2 tabular-nums text-zinc-400">
                            {fmtIrr(position.vega_pnl_irr)}
                          </td>
                          <td className="px-2 py-2 tabular-nums text-zinc-400">
                            {fmtIrr(position.liquidity_cost_irr)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* زنجیرهٔ اختیار IME: IV، دلتا، OI و ساختار زمانی */}
      <div className="rounded-xl border p-4" style={cardStyle}>
        <OptionsChainAnalytics />
      </div>

      {/* سازندهٔ استراتژی با نمودار سود/زیان در سررسید */}
      <div className="rounded-xl border p-4" style={cardStyle}>
        <StrategyBuilder />
      </div>

      <p className="text-[11px] leading-5 text-zinc-500">
        این ابزار صرفاً برای پژوهش و آموزش است و توصیهٔ سرمایه‌گذاری یا پیش‌بینی
        قیمت محسوب نمی‌شود. شوک‌های سناریوها فروض مدل‌اند، نه پیش‌بینی.
      </p>
    </div>
  );
}
