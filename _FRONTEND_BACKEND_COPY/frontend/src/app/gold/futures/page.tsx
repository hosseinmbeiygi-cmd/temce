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
  type FuturesMarginResp,
  type KillSwitchResp,
} from "@/lib/goldApi";
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
  const [contractSymbol, setContractSymbol] = useState("سکه_آتی_IME");

  // Live prices (برای sync قیمت فعلی)
  const { data: live } = useQuery({
    queryKey: ["gold", "live"],
    queryFn: () => getGoldLivePrices(),
    refetchInterval: 5000,
    enabled: mounted,
  });

  // وقتی live می‌آید، current_price را auto-fill کن (اگر خالی بود)
  useEffect(() => {
    if (live?.coin_bahar_irr && currentPrice === undefined) {
      setCurrentPrice(live.coin_bahar_irr);
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
  const { data: positions = [] } = useQuery({
    queryKey: ["gold", "futures", "positions"],
    queryFn: () => getFuturesPositions("OPEN"),
    refetchInterval: 10_000,
    enabled: mounted,
  });
  const { data: health } = useQuery({
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
  const ksStatus: KillSwitchResp = ks ?? {
    status: "NORMAL",
    reason: null,
    triggered_at: null,
    active_rules: [],
    directive: null,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">آتی سکه (IME)</h1>
          <p className="text-xs text-zinc-500 mt-1">
            محاسبه مارجین، لیکوئیدیشن و Health Ratio — اهرم ۱۰ برابر
          </p>
        </div>
        {live && (
          <div className="text-left text-xs text-zinc-400">
            <div>
              سکه بهار:{" "}
              <span className="text-amber-300 font-semibold tabular-nums">
                {fmt(live.coin_bahar_irr)}
              </span>{" "}
              ریال
            </div>
            {live.is_stale && <div className="text-rose-400">⚠️ داده منقضی</div>}
          </div>
        )}
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
            <Field label="اهرم">
              <select
                value={leverage}
                onChange={(e) => setLeverage(+e.target.value)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100"
              >
                {[5, 10, 15, 20].map((l) => (
                  <option key={l} value={l}>
                    {l}x
                  </option>
                ))}
              </select>
            </Field>
            <Field label="تعداد قرارداد">
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, +e.target.value || 1))}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="قیمت فعلی (اختیاری)">
              <input
                type="number"
                value={currentPrice ?? ""}
                onChange={(e) => setCurrentPrice(e.target.value ? +e.target.value : undefined)}
                placeholder="خالی = بدون Health"
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
            <Field label="موجودی حساب (ریال)">
              <input
                type="number"
                value={accountEquity ?? ""}
                onChange={(e) => setAccountEquity(e.target.value ? +e.target.value : undefined)}
                placeholder="برای Health Ratio"
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
              />
            </Field>
          </div>
          <button
            onClick={() => marginMut.mutate()}
            disabled={marginMut.isPending}
            className="mt-4 w-full bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/40 rounded-lg px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50"
          >
            {marginMut.isPending ? "در حال محاسبه..." : "⚡ محاسبه"}
          </button>
        </div>

        {/* Health Gauge */}
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
          <h2 className="text-base font-semibold text-zinc-200 mb-4 text-center">Health Ratio</h2>
          <HealthRatioGauge value={m?.health_ratio ?? null} />
          {m?.alert_message && (
            <div
              className={`mt-3 text-center text-xs px-2 py-1.5 rounded ring-1 ${alertColor(
                m.alert_level,
              )}`}
            >
              {m.alert_message}
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {m && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="ارزش قرارداد" value={fmt(m.contract_value)} unit="ریال" />
          <Stat
            label="مارجین اولیه"
            value={fmt(m.initial_margin)}
            unit="ریال"
            color="amber"
          />
          <Stat
            label="مارجین نگهداری"
            value={fmt(m.maintenance_margin)}
            unit="ریال"
            color="amber"
          />
          <Stat
            label="قیمت لیکوئیدیشن"
            value={fmt(m.liquidation_price)}
            unit="ریال"
            color="rose"
            highlight
          />
          {m.distance_to_liquidation_pct !== null && (
            <Stat
              label="فاصله تا لیکوئید"
              value={fmt(m.distance_to_liquidation_pct, 2)}
              unit="٪"
              color={m.distance_to_liquidation_pct < 5 ? "rose" : "emerald"}
            />
          )}
          {m.recommended_stop_loss !== null && (
            <Stat
              label="Stop Loss پیشنهادی"
              value={fmt(m.recommended_stop_loss)}
              unit="ریال"
              color="amber"
            />
          )}
          <Stat label="اهرم" value={`${m.leverage}x`} />
          <Stat label="نوع" value={m.position_type === "LONG" ? "لانگ" : "شورت"} />
        </div>
      )}

      {/* Open Position Action */}
      {m && (
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-4">
          <div className="flex flex-col md:flex-row gap-3 items-end">
            <div className="flex-1">
              <label className="text-xs text-zinc-400 mb-1 block">نماد قرارداد</label>
              <input
                type="text"
                value={contractSymbol}
                onChange={(e) => setContractSymbol(e.target.value)}
                className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100"
              />
            </div>
            <button
              onClick={() => openMut.mutate()}
              disabled={openMut.isPending}
              className="px-6 py-2.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 ring-1 ring-emerald-500/40 rounded-lg text-sm font-semibold transition disabled:opacity-50"
            >
              {openMut.isPending ? "..." : "✓ ثبت پوزیشن"}
            </button>
            {openMut.isSuccess && (
              <div className="text-xs text-emerald-300">پوزیشن ثبت شد ✓</div>
            )}
          </div>
        </div>
      )}

      {/* Open Positions Table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-zinc-200">
            📊 پوزیشن‌های باز ({positions.length})
          </h2>
          {health && (health.critical_count > 0 || health.warning_count > 0) && (
            <div className="text-xs flex gap-2">
              {health.critical_count > 0 && (
                <span className="px-2 py-0.5 rounded bg-rose-950/50 text-rose-300 ring-1 ring-rose-700/40">
                  {health.critical_count} بحرانی
                </span>
              )}
              {health.warning_count > 0 && (
                <span className="px-2 py-0.5 rounded bg-amber-950/50 text-amber-300 ring-1 ring-amber-700/40">
                  {health.warning_count} هشدار
                </span>
              )}
            </div>
          )}
        </div>
        <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] text-zinc-500 border-b border-zinc-800/60 bg-zinc-900/60">
                <th className="text-right py-2.5 px-3">قرارداد</th>
                <th className="text-right py-2.5 px-3">نوع</th>
                <th className="text-right py-2.5 px-3">ورود</th>
                <th className="text-right py-2.5 px-3">فعلی</th>
                <th className="text-right py-2.5 px-3">مقدار</th>
                <th className="text-right py-2.5 px-3">P&L</th>
                <th className="text-right py-2.5 px-3">لیکوئید</th>
                <th className="text-right py-2.5 px-3">Health</th>
                <th className="text-right py-2.5 px-3">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-zinc-500 text-xs">
                    پوزیشن بازی ثبت نشده
                  </td>
                </tr>
              )}
              {positions.map((p) => {
                const pnlTone =
                  (p.unrealized_pnl ?? 0) > 0
                    ? "text-emerald-300"
                    : (p.unrealized_pnl ?? 0) < 0
                      ? "text-rose-300"
                      : "text-zinc-500";
                const hrTone =
                  (p.health_ratio ?? 99) < 1.2
                    ? "text-rose-300"
                    : (p.health_ratio ?? 99) < 2
                      ? "text-amber-300"
                      : "text-emerald-300";
                return (
                  <tr
                    key={p.id}
                    className="border-b border-zinc-800/40 hover:bg-zinc-800/20 transition"
                  >
                    <td className="py-2.5 px-3 text-xs text-zinc-200">{p.contract_symbol}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ${
                          p.position_type === "LONG"
                            ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                            : "bg-rose-500/10 text-rose-300 ring-rose-500/30"
                        }`}
                      >
                        {p.position_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-zinc-300">
                      {fmt(p.entry_price)}
                    </td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-zinc-400">
                      {fmt(p.current_price)}
                    </td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-zinc-300">
                      {p.quantity}
                    </td>
                    <td className={`py-2.5 px-3 text-xs tabular-nums font-semibold ${pnlTone}`}>
                      {fmt(p.unrealized_pnl)} ({fmtPct(p.unrealized_pnl_pct)})
                    </td>
                    <td className="py-2.5 px-3 text-xs tabular-nums text-rose-300">
                      {fmt(p.liquidation_price)}
                    </td>
                    <td className={`py-2.5 px-3 text-xs tabular-nums font-semibold ${hrTone}`}>
                      {p.health_ratio?.toFixed(2) ?? "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      <button
                        onClick={() => {
                          const exit = prompt(
                            `قیمت خروج برای ${p.contract_symbol}:`,
                            String(p.current_price ?? p.entry_price),
                          );
                          if (exit && !isNaN(+exit)) {
                            closeMut.mutate({ id: p.id, exit: +exit });
                          }
                        }}
                        className="text-[10px] px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30 rounded transition"
                      >
                        بستن
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs text-zinc-400 mb-1 block">{label}</label>
      {children}
    </div>
  );
}

function Stat({
  label,
  value,
  unit,
  color = "default",
  highlight = false,
}: {
  label: string;
  value: string;
  unit?: string;
  color?: "default" | "emerald" | "amber" | "rose";
  highlight?: boolean;
}) {
  const colorClass = {
    default: "border-zinc-700 bg-zinc-900/60",
    emerald: "border-emerald-700/50 bg-emerald-950/30",
    amber: "border-amber-700/50 bg-amber-950/30",
    rose: "border-rose-700/50 bg-rose-950/30",
  }[color];
  return (
    <div
      className={`rounded-lg border p-3 ${colorClass} ${
        highlight ? "ring-2 ring-rose-500/40" : ""
      }`}
    >
      <div className="text-[10px] text-zinc-400 mb-1">{label}</div>
      <div className="text-lg font-bold text-zinc-100 tabular-nums">
        {value}
        {unit && <span className="text-[10px] text-zinc-500 mr-1">{unit}</span>}
      </div>
    </div>
  );
}
