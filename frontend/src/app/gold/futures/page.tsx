"use client";

/** صفحه آتی (IME Coin Futures) — اولویت Antigravity v5.
 *  شامل: Margin Calculator + Health Dashboard + Open Positions + Kill-Switch Banner.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  closeFuturesPosition,
  getFuturesHealth,
  getFuturesPositions,
  getGoldLivePrices,
  getKillSwitch,
  openFuturesPosition,
  postFuturesMargin,
} from "@/lib/goldApi";

type FuturesMarginResp = Awaited<ReturnType<typeof postFuturesMargin>>;
type KillSwitchResp = Awaited<ReturnType<typeof getKillSwitch>>;
import { HealthRatioGauge } from "@/components/gold/HealthRatioGauge";
import { KillSwitchBanner } from "@/components/gold/KillSwitchBanner";

const fmt = (n: number | null | undefined, digits = 0): string => {
  if (n === null || n === undefined || !isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (n: number | null | undefined, digits = 2): string => {
  if (n === null || n === undefined) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}٪`;
};

const alertColor = (lvl: string | null | undefined): string => {
  if (lvl === "CRITICAL") return "text-rose-300 ring-rose-700/40 bg-rose-950/30";
  if (lvl === "WARNING") return "text-amber-300 ring-amber-700/40 bg-amber-950/30";
  if (lvl === "SAFE") return "text-emerald-300 ring-emerald-700/40 bg-emerald-950/30";
  return "text-zinc-300 ring-zinc-700/40 bg-zinc-900/40";
};

export default function GoldFuturesPage() {
  const qc = useQueryClient();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Inputs
  const [entryPrice, setEntryPrice] = useState<number>(300_000_000);
  const [positionType, setPositionType] = useState<"LONG" | "SHORT">("LONG");
  const [leverage, setLeverage] = useState<number>(10);
  const [quantity, setQuantity] = useState<number>(1);
  const [currentPrice, setCurrentPrice] = useState<number | undefined>(undefined);
  const [accountEquity, setAccountEquity] = useState<number | undefined>(50_000_000);

  // Open-position form
  const contractSymbol = "سکه_آتی_IME";

  // Live prices (برای sync قیمت فعلی)
  const { data: live } = useQuery({
    queryKey: ["gold", "live"],
    queryFn: () => getGoldLivePrices(),
    refetchInterval: 5000,
    enabled: mounted,
  });

  // وقتی live می‌آید، current_price را auto-fill کن (اگر خالی بود)
  useEffect(() => {
    if (live?.["coin_bahar_irr"] && currentPrice === undefined) {
      setCurrentPrice(live["coin_bahar_irr"]);
    }
  }, [live, currentPrice]);

  // Margin calculator
  const marginMut = useMutation({
    mutationFn: () =>
      postFuturesMargin({
        entry_price: entryPrice,
        position_type: positionType,
        leverage,
        quantity,
        current_price: currentPrice,
        account_equity: accountEquity,
      }),
  });

  // Positions + health
  const {
    data: positions = [],
    isError: positionsError,
    isLoading: positionsLoading,
  } = useQuery({
    queryKey: ["gold", "futures", "positions"],
    queryFn: () => getFuturesPositions("OPEN"),
    refetchInterval: 10_000,
    enabled: mounted,
  });
  const { data: health, isError: healthError } = useQuery({
    queryKey: ["gold", "futures", "health"],
    queryFn: getFuturesHealth,
    refetchInterval: 10_000,
    enabled: mounted,
  });
  const { data: ks } = useQuery({
    queryKey: ["gold", "kill-switch"],
    queryFn: getKillSwitch,
    refetchInterval: 15_000,
    enabled: mounted,
  });

  // Open / Close position
  const openMut = useMutation({
    mutationFn: () =>
      openFuturesPosition({
        contract_symbol: contractSymbol,
        position_type: positionType,
        entry_price: entryPrice,
        quantity,
        leverage,
        stop_loss: marginMut.data?.recommended_stop_loss ?? null,
        target_1: null,
        target_2: null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gold", "futures"] });
    },
  });

  const closeMut = useMutation({
    mutationFn: (vars: { id: string; exit: number }) =>
      closeFuturesPosition(vars.id, vars.exit, "MANUAL"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gold", "futures"] });
    },
  });

  const m: FuturesMarginResp | undefined = marginMut.data;
  // A missing kill-switch is NOT "NORMAL": keep null and let the banner say so.
  const ksStatus: KillSwitchResp | null = ks ?? null;

  // ``live`` is undefined until the first quote response lands — indexing it
  // unguarded crashed the whole page on its first render. The upstream feed
  // reports 0 for an unavailable quote, so only a positive value is a price.
  const rawLivePrice = live?.["coin_bahar_irr"];
  const livePrice = rawLivePrice != null && rawLivePrice > 0 ? rawLivePrice : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">آتی سکه (IME)</h1>
          <p className="text-xs text-zinc-500 mt-1">
            محاسبه مارجین، لیکوئیدیشن و Health Ratio — اهرم قابل تنظیم
          </p>
        </div>
        <div className="text-left text-xs text-zinc-400">
          {livePrice != null ? (
            <div>
              سکه بهار:{" "}
              <span className="text-amber-300 font-semibold tabular-nums">
                {fmt(livePrice)}
              </span>{" "}
              ریال
            </div>
          ) : (
            <div className="text-zinc-500">قیمت زندهٔ سکه در دسترس نیست</div>
          )}
        </div>
      </div>

      {/* Kill-Switch banner */}
      <KillSwitchBanner status={ksStatus} />

      {/* Calculator + Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Calculator Form */}
        <div className="lg:col-span-2 rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
          <h2 className="text-base font-semibold text-zinc-200 mb-4">🧮 کلکولاتور مارجین</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="قیمت ورود (ریال)">
              <input
                type="number"
                value={entryPrice}
                onChange={(e) => setEntryPrice(+e.target.value || 0)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="نوع پوزیشن">
              <div className="flex gap-1">
                {(["LONG", "SHORT"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setPositionType(t)}
                    className={`flex-1 px-3 py-2 rounded-lg text-sm font-semibold transition ${
                      positionType === t
                        ? t === "LONG"
                          ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                          : "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40"
                        : "bg-zinc-800/60 text-zinc-400 hover:bg-zinc-800"
                    }`}
                  >
                    {t === "LONG" ? "لانگ" : "شورت"}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="حجم (کنترکت)">
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(+e.target.value || 0)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="اهرم">
              <input
                type="number"
                value={leverage}
                onChange={(e) => setLeverage(+e.target.value || 0)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="قیمت فعلی (اختیاری)">
              <input
                type="number"
                value={currentPrice ?? ""}
                onChange={(e) => setCurrentPrice(+e.target.value || undefined)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="اعتبار حساب (اختیاری)">
              <input
                type="number"
                value={accountEquity ?? ""}
                onChange={(e) => setAccountEquity(+e.target.value || undefined)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
          </div>

          <button
            onClick={() => marginMut.mutate()}
            disabled={marginMut.isPending || leverage <= 0 || quantity <= 0}
            className="mt-4 w-full bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/40 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-50"
          >
            {marginMut.isPending ? "در حال محاسبه..." : "محاسبه مارجین"}
          </button>

          {m && (
            <div className="mt-4 space-y-3 border-t border-zinc-700/60 pt-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <Tile label="برداشت اولیه" value={fmt(m.initial_margin)} />
                <Tile label="برداشت نگهداری" value={fmt(m.maintenance_margin)} />
                <Tile label="ارزش کنترکت" value={fmt(m.contract_value)} />
                <Tile label="فاصله به لیق" value={fmtPct(m.distance_to_liquidation_pct, 1)} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                <Tile label="قیمت لیق" value={fmt(m.liquidation_price)} />
                <Tile label="سلامت حساب" value={m.health_ratio?.toFixed(2) ?? "—"} />
                <Tile label="حد ضرر پیشنهادی" value={fmtPct(m.recommended_stop_loss, 1)} />
              </div>
              {m.alert_message && (
                <div
                  className={`rounded-lg px-3 py-2 text-sm ${alertColor(m.alert_level)}`}
                >
                  {m.alert_message}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Health dashboard */}
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
          <h2 className="text-base font-semibold text-zinc-200 mb-4">🫀 سلامت حساب</h2>
          {healthError ? (
            <div className="rounded-lg bg-rose-950/30 ring-1 ring-rose-700/40 px-3 py-2 text-xs text-rose-300">
              وضعیت سلامت حساب از سرور دریافت نشد — مقدار «بحرانی» نمایش داده نمی‌شود.
            </div>
          ) : (
            <>
              <HealthRatioGauge value={health?.health_ratio ?? null} />
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between text-zinc-300">
                  <span>بحرانی</span>
                  <span className="font-mono text-rose-300">{health?.critical_count ?? "—"}</span>
                </div>
                <div className="flex justify-between text-zinc-300">
                  <span>هشدارها</span>
                  <span className="font-mono text-amber-300">{health?.warning_count ?? "—"}</span>
                </div>
                <div className="flex justify-between text-zinc-300">
                  <span>وضعیت ریسک</span>
                  <span className="font-mono text-zinc-200">{riskLabel(health?.health_ratio)}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Positions table */}
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-zinc-200">پوزیشن‌های باز</h2>
          <button
            onClick={() => openMut.mutate()}
            disabled={openMut.isPending}
            className="text-xs bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 rounded px-3 py-1.5 transition disabled:opacity-50"
          >
            {openMut.isPending ? "در حال ثبت..." : "باز کردن پوزیشن جدید"}
          </button>
        </div>
        {(openMut.isError || closeMut.isError) && (
          <div className="mb-3 rounded-lg bg-rose-950/30 ring-1 ring-rose-700/40 px-3 py-2 text-xs text-rose-300">
            {openMut.isError ? "ثبت پوزیشن ناموفق بود" : "بستن پوزیشن ناموفق بود"} — دوباره تلاش کنید.
          </div>
        )}
        {positionsError ? (
          <div className="rounded-lg bg-rose-950/30 ring-1 ring-rose-700/40 px-3 py-2 text-xs text-rose-300">
            فهرست پوزیشن‌ها دریافت نشد.
          </div>
        ) : positionsLoading ? (
          <div className="text-zinc-500 text-sm text-center py-6">در حال بارگذاری...</div>
        ) : positions.length === 0 ? (
          <div className="text-zinc-500 text-sm text-center py-6">هیچ پوزیشنی باز نیست</div>
        ) : (
          // Nine columns do not fit a phone; scroll the table instead of squeezing
          // it (same treatment as /gold/options).
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-700/60">
                  <th className="text-left p-2">نماد</th>
                  <th className="text-right p-2">نوع</th>
                  <th className="text-right p-2">قیمت ورود</th>
                  <th className="text-right p-2">حجم</th>
                  <th className="text-right p-2">اهرم</th>
                  <th className="text-right p-2">PnL</th>
                  <th className="text-right p-2">علت خروج</th>
                  <th className="text-right p-2">سلامت</th>
                  <th className="text-right p-2">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.id} className="border-b border-zinc-700/30">
                    <td className="p-2 text-zinc-200">{p.contract_symbol}</td>
                    <td className="p-2 text-right font-mono">{p.position_type}</td>
                    <td className="p-2 text-right font-mono text-zinc-200">
                      {fmt(p.entry_price)}
                    </td>
                    <td className="p-2 text-right font-mono text-zinc-200">{p.quantity}</td>
                    <td className="p-2 text-right font-mono text-zinc-200">{p.leverage}×</td>
                    <td className="p-2 text-right font-mono">
                      <span
                        className={
                          (p.unrealized_pnl ?? 0) > 0
                            ? "text-emerald-300"
                            : (p.unrealized_pnl ?? 0) < 0
                            ? "text-rose-300"
                            : "text-zinc-400"
                        }
                      >
                        {fmt(p.unrealized_pnl)}
                      </span>
                    </td>
                    <td className="p-2 text-right font-mono text-zinc-200">
                      {p.exit_reason ? p.exit_reason : "—"}
                    </td>
                    <td className="p-2 text-right font-mono text-zinc-200">
                      {p.health_ratio != null ? p.health_ratio.toFixed(2) : "—"}
                    </td>
                    <td className="p-2 text-right">
                      <button
                        onClick={() => {
                          if (p.current_price == null) return;
                          closeMut.mutate({ id: p.id, exit: p.current_price });
                        }}
                        disabled={closeMut.isPending || p.current_price == null}
                        title={p.current_price == null ? "قیمت فعلی در دسترس نیست؛ بستن پوزیشن غیرفعال است" : undefined}
                        className="text-xs text-rose-300 hover:text-rose-200 transition disabled:opacity-50"
                      >
                        بسته شدن
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-zinc-400">{label}</div>
      {children}
    </div>
  );
}

function riskLabel(healthRatio: number | null | undefined): string {
  // No figure means the request failed or the book is empty — never render a
  // fabricated "CRIT" from a missing value.
  if (healthRatio == null) return "—";
  if (healthRatio >= 2) return "SAFE";
  if (healthRatio >= 1.2) return "WARN";
  return "CRIT";
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-zinc-800/60 px-3 py-2">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className="text-sm font-mono text-zinc-100">{value}</div>
    </div>
  );
}
