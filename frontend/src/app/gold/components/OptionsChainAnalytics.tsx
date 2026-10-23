"use client";

/**
 * IME option-chain analytics for gold — IV, delta, open interest and the ATM
 * IV term structure, from ``GET /gold/analytics/options/chain``.
 *
 * Every numeric field is nullable on the wire: a contract whose IV cannot be
 * solved carries ``iv``/greeks ``null`` plus an ``iv_error`` string. Those rows
 * render as "—" with the reason in the title attribute rather than as zeros.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SkeletonBlock } from "@/components/gold/ui/SkeletonBlock";
import { getOptionsChainAnalytics } from "@/lib/goldApi";
import { cn } from "@/lib/cn";
import type { IvTermPoint, OptionsChainContract, OptionsChainReport } from "@/types/gold";

const COMMODITIES = [
  { id: "GoldBar", label: "شمش طلا" },
  { id: "SilverBar", label: "شمش نقره" },
  { id: "ZR", label: "زعفران" },
];

const fmt = (value: number | null | undefined, digits = 0): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (value: number | null | undefined, digits = 2): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${fmt(value * 100, digits)}٪`;
};

const fmtGreeks = (value: number | null | undefined, digits = 3): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return fmt(value, digits);
};

function isServiceUnavailable(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /\b503\b/.test(message);
}

export function sortContracts(rows: OptionsChainContract[]): OptionsChainContract[] {
  return [...rows].sort((a, b) => {
    const daysA = a.days_to_expiry ?? Number.MAX_SAFE_INTEGER;
    const daysB = b.days_to_expiry ?? Number.MAX_SAFE_INTEGER;
    if (daysA !== daysB) return daysA - daysB;
    if (a.strike !== b.strike) return a.strike - b.strike;
    return a.option_type.localeCompare(b.option_type);
  });
}

/**
 * ATM IV against days-to-expiry.
 *
 * Renders nothing when there are fewer than two points: a term structure needs
 * at least two expiries with a solvable IV, and a single point is not a curve.
 */
export function IvTermStructureChart({ points }: { points: IvTermPoint[] }) {
  const sorted = useMemo(
    () =>
      [...points]
        .filter((point) => Number.isFinite(point.atm_iv) && point.days_to_expiry !== null)
        .sort((a, b) => (a.days_to_expiry ?? 0) - (b.days_to_expiry ?? 0)),
    [points],
  );

  if (sorted.length < 2) {
    return (
      <div
        data-testid="iv-term-empty"
        className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-zinc-500"
        style={{ borderColor: "var(--gd-border)" }}
      >
        ساختار زمانی نوسان ضمنی رسم نمی‌شود: حداقل دو سررسید با IV قابل‌محاسبه لازم است
        (اکنون {fmt(sorted.length, 0)} نقطه).
      </div>
    );
  }

  const w = 640;
  const h = 220;
  const pad = 36;
  const days = sorted.map((point) => point.days_to_expiry ?? 0);
  const ivs = sorted.map((point) => point.atm_iv);
  const minDays = Math.min(...days);
  const maxDays = Math.max(...days);
  const minIv = Math.min(...ivs);
  const maxIv = Math.max(...ivs);
  const spanDays = maxDays - minDays || 1;
  const spanIv = maxIv - minIv || Math.max(maxIv * 0.1, 0.01);

  const x = (value: number) => pad + ((value - minDays) / spanDays) * (w - 2 * pad);
  const y = (value: number) => h - pad - ((value - minIv) / spanIv) * (h - 2 * pad);
  const line = sorted.map((point, index) => `${index === 0 ? "M" : "L"} ${x(days[index])} ${y(ivs[index])}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full"
      role="img"
      aria-label="ساختار زمانی نوسان ضمنی"
      data-testid="iv-term-chart"
    >
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#3f3f46" strokeWidth={1} />
      <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#3f3f46" strokeWidth={1} />
      <path d={line} fill="none" stroke="#fbbf24" strokeWidth={2} />
      {sorted.map((point, index) => (
        <g key={`${point.contract_key ?? point.expiry ?? index}`}>
          <circle cx={x(days[index])} cy={y(ivs[index])} r={3.5} fill="#fbbf24" />
          <text x={x(days[index])} y={y(ivs[index]) - 8} fill="#a1a1aa" fontSize={10} textAnchor="middle">
            {fmtPct(point.atm_iv, 1)}
          </text>
          <text x={x(days[index])} y={h - pad + 14} fill="#71717a" fontSize={9} textAnchor="middle">
            {fmt(days[index], 0)} روز
          </text>
        </g>
      ))}
    </svg>
  );
}

function ContractRow({ row }: { row: OptionsChainContract }) {
  return (
    <tr className="border-t" style={{ borderColor: "var(--gd-border)" }}>
      <td className="px-2 py-1.5">
        <span className={row.option_type === "call" ? "text-emerald-300" : "text-rose-300"}>
          {row.option_type === "call" ? "کال" : "پوت"}
        </span>
      </td>
      <td className="px-2 py-1.5 font-mono text-zinc-200">{fmt(row.strike)}</td>
      <td className="px-2 py-1.5 font-mono text-zinc-400">{fmt(row.days_to_expiry, 0)}</td>
      <td className="px-2 py-1.5 font-mono text-zinc-300">{fmt(row.volume)}</td>
      <td className="px-2 py-1.5 font-mono text-zinc-300">{fmt(row.open_interest)}</td>
      <td className="px-2 py-1.5 font-mono text-zinc-400">
        {row.oi_change === null || row.oi_change === undefined
          ? "—"
          : `${row.oi_change > 0 ? "+" : ""}${fmt(row.oi_change)}`}
      </td>
      <td className="px-2 py-1.5 font-mono text-zinc-200">{fmtGreeks(row.delta)}</td>
      <td
        className="px-2 py-1.5 font-mono text-amber-200"
        title={row.iv === null ? row.iv_error ?? "IV قابل‌محاسبه نیست" : undefined}
      >
        {fmtPct(row.iv)}
      </td>
      <td className="px-2 py-1.5">
        {row.is_liquid ? (
          <span className="text-emerald-300">نقدشونده</span>
        ) : (
          <span className="text-amber-300" title={row.liquidity_reasons.join(", ")}>
            محدود
          </span>
        )}
      </td>
    </tr>
  );
}

function ReportContent({ report }: { report: OptionsChainReport }) {
  const [onlyLiquid, setOnlyLiquid] = useState(false);
  const sorted = useMemo(() => sortContracts(report.contracts), [report.contracts]);
  const rows = onlyLiquid ? sorted.filter((row) => row.is_liquid) : sorted;
  const atm = report.iv_term_structure[0];
  const firstSkew = report.skew_by_expiry.find((row) => row.skew !== null);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-zinc-400">
        <span>قراردادها: {fmt(report.contracts_count, 0)}</span>
        <span>فوروارد نزدیک: {fmt(report.forward_price ?? null)}</span>
        <span>ATM IV: {atm ? fmtPct(atm.atm_iv) : "—"}</span>
        <span>
          اسکیو نزدیک:{" "}
          {firstSkew && firstSkew.skew !== null ? fmtPct(firstSkew.skew) : "—"}
        </span>
        {report.source && <span className="text-zinc-600">منبع: {report.source}</span>}
      </div>

      {!report.iv_available && (
        <p
          data-testid="iv-unavailable"
          className="rounded-lg border border-amber-800/40 bg-amber-950/20 px-3 py-2 text-[11px] text-amber-200"
        >
          نوسان ضمنی و دلتا فقط با قیمت فوروارد قابل محاسبه است و فید فعلی فورواردی
          برنگردانده است؛ مقادیر به‌جای صفر با «—» نمایش داده می‌شوند. با وارد کردن
          فوروارد، محاسبه دوباره انجام می‌شود.
        </p>
      )}

      {report.iv_history_source === "unavailable" && (
        <p
          data-testid="iv-history-unavailable"
          className="rounded-lg border border-zinc-700/50 bg-zinc-900/40 px-3 py-2 text-[11px] text-zinc-400"
        >
          رتبه/درصدک تاریخی IV در دسترس نیست ({report.iv_history_reason ?? "سری تاریخی IV ذخیره نمی‌شود"})
          — ستون‌های rank/percentile نمایش داده نمی‌شوند تا مقدار ساختگی تولید نشود.
        </p>
      )}

      <IvTermStructureChart points={report.iv_term_structure} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-zinc-300">زنجیرهٔ اختیار (IV و دلتا)</h3>
        <label className="flex items-center gap-2 text-[11px] text-zinc-400">
          <input
            type="checkbox"
            checked={onlyLiquid}
            onChange={(event) => setOnlyLiquid(event.target.checked)}
          />
          فقط قراردادهای نقدشونده
        </label>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-zinc-500" style={{ borderColor: "var(--gd-border)" }}>
          قراردادی با این فیلتر باقی نماند.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "var(--gd-border)" }}>
          <table className="w-full min-w-[720px] text-right text-xs">
            <thead className="bg-zinc-900/60 text-zinc-400">
              <tr>
                <th className="px-2 py-2 font-medium">نوع</th>
                <th className="px-2 py-2 font-medium">استرایک</th>
                <th className="px-2 py-2 font-medium">روز تا سررسید</th>
                <th className="px-2 py-2 font-medium">حجم</th>
                <th className="px-2 py-2 font-medium">OI</th>
                <th className="px-2 py-2 font-medium">ΔOI</th>
                <th className="px-2 py-2 font-medium">دلتا</th>
                <th className="px-2 py-2 font-medium">IV</th>
                <th className="px-2 py-2 font-medium">نقدشوندگی</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 40).map((row) => (
                <ContractRow key={row.contract_key} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function OptionsChainAnalytics() {
  const [commodity, setCommodity] = useState("GoldBar");
  const [forwardInput, setForwardInput] = useState("");
  const forward = Number(forwardInput) > 0 ? Number(forwardInput) : undefined;
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "options", "chain", commodity, forward ?? null],
    queryFn: () =>
      getOptionsChainAnalytics({ commodity, limit: 200, forwardPrice: forward }),
    refetchInterval: 60_000,
    retry: 1,
  });

  return (
    <section className="space-y-3" data-testid="options-chain-analytics">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-300">تحلیل زنجیرهٔ اختیار IME</h2>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[10px] text-zinc-500">
            فوروارد (اختیاری)
            <input
              type="number"
              min={1}
              step={100_000}
              value={forwardInput}
              onChange={(event) => setForwardInput(event.target.value)}
              placeholder="برای محاسبهٔ IV"
              className="mt-1 w-32 rounded-md border bg-zinc-950/40 px-2 py-1 text-xs tabular-nums text-zinc-100 outline-none focus:border-amber-500/60"
              style={{ borderColor: "var(--gd-border)" }}
            />
          </label>
          <div className="flex gap-1 rounded-lg border p-1" style={{ borderColor: "var(--gd-border)" }}>
          {COMMODITIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCommodity(item.id)}
              className={cn(
                "rounded-md px-2.5 py-1 text-[11px] transition",
                commodity === item.id
                  ? "bg-amber-500/20 text-amber-300"
                  : "text-zinc-400 hover:text-zinc-200",
              )}
            >
              {item.label}
            </button>
          ))}
          </div>
        </div>
      </div>

      {isLoading && <SkeletonBlock visible className="h-48 w-full" />}

      {isError &&
        (isServiceUnavailable(error) ? (
          <div
            data-testid="options-chain-503"
            className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300"
          >
            سرویس زنجیرهٔ اختیار موقتاً در دسترس نیست (۵۰۳). دادهٔ زنجیره نمایش داده نمی‌شود.
          </div>
        ) : (
          <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300">
            دریافت زنجیرهٔ اختیار ناموفق بود. اتصال API را بررسی کنید.
          </div>
        ))}

      {data && !data.available && (
        <div className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-4 text-xs text-amber-200">
          زنجیرهٔ اختیار برای «{COMMODITIES.find((item) => item.id === commodity)?.label}»
          در دسترس نیست{data.reason ? `: ${data.reason}` : ""} — جدول
          <span dir="ltr"> brsapi_ime_options </span>
          ممکن است خالی باشد.
        </div>
      )}

      {data && data.available && data.contracts.length === 0 && (
        <div className="rounded-xl border border-dashed p-4 text-center text-xs text-zinc-500" style={{ borderColor: "var(--gd-border)" }}>
          قراردادی برای این کالا ثبت نشده است.
        </div>
      )}

      {data && data.available && data.contracts.length > 0 && <ReportContent report={data} />}
    </section>
  );
}
