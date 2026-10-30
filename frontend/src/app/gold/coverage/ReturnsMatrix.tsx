"use client";

import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type {
  AssetReturnRow,
  CoverageStatus,
  PeriodKey,
  PeriodReturn,
  ReturnsMatrixResponse,
} from "@/types/phase2";

import { faNumber, faPercent, gapTitle } from "../terminal/format";
import { MissingValue } from "../terminal/TerminalBits";
import { SourceNotice } from "./SectionFeedback";

const PERIOD_LABEL: Record<PeriodKey, string> = {
  "1m": "۱ ماه",
  "3m": "۳ ماه",
  "6m": "۶ ماه",
  "9m": "۹ ماه",
  "1y": "۱ سال",
};

const STATUS_LABEL: Record<CoverageStatus, string> = {
  complete: "کامل",
  incomplete: "ناقص",
  no_data: "بدون داده",
};

function cellReason(cell: PeriodReturn | undefined): string {
  if (!cell) return "این دوره در پاسخ نیامده است";
  if (cell.reason) return cell.reason;
  return cell.status === "incomplete"
    ? "داده برای این دوره کامل نیست"
    : "برای این دوره داده‌ای ثبت نشده است";
}

function ReturnCell({ cell, rowKey, period }: { cell: PeriodReturn | undefined; rowKey: string; period: PeriodKey }) {
  const status = cell?.status ?? "no_data";
  const reason = cellReason(cell);
  return (
    <td
      data-testid={`return-cell-${rowKey}-${period}`}
      data-status={status}
      title={reason}
      className="px-3 py-2 tabular-nums text-zinc-200"
    >
      {cell?.value === null || cell?.value === undefined ? (
        <MissingValue reason={reason} />
      ) : (
        <div className="flex items-center gap-1.5">
          <span
            className={
              cell.value > 0 ? "text-emerald-300" : cell.value < 0 ? "text-rose-300" : "text-zinc-300"
            }
          >
            {faPercent(cell.value)}
          </span>
          {status !== "complete" && (
            <span
              data-testid={`period-incomplete-${rowKey}-${period}`}
              className="rounded bg-amber-500/10 px-1 py-0.5 text-[9px] font-semibold text-amber-300 ring-1 ring-amber-500/40"
            >
              {STATUS_LABEL[status]}
            </span>
          )}
        </div>
      )}
      {cell && cell.observations > 0 && (
        <div className="mt-0.5 text-[9px] text-zinc-500">
          {faNumber(cell.observations)} مشاهده
          {cell.start_date && cell.end_date ? ` · ${cell.start_date} → ${cell.end_date}` : ""}
        </div>
      )}
    </td>
  );
}

function CorrelationCell({ row }: { row: AssetReturnRow }) {
  if (row.correlation_90d === null) {
    return (
      <td
        data-testid={`correlation-${row.key}`}
        data-status={row.correlation_status}
        className="px-3 py-2"
        title={row.correlation_reason ?? undefined}
      >
        <MissingValue reason={row.correlation_reason ?? "همبستگی محاسبه نشد"} />
      </td>
    );
  }
  return (
    <td
      data-testid={`correlation-${row.key}`}
      data-status={row.correlation_status}
      title={row.correlation_reason ?? undefined}
      className="px-3 py-2 tabular-nums text-zinc-200"
    >
      <div className="flex items-center gap-1.5">
        <span>{faNumber(row.correlation_90d, 2)}</span>
        {row.correlation_status !== "complete" && (
          <span className="rounded bg-amber-500/10 px-1 py-0.5 text-[9px] font-semibold text-amber-300 ring-1 ring-amber-500/40">
            {STATUS_LABEL[row.correlation_status]}
          </span>
        )}
      </div>
      <div className="mt-0.5 text-[9px] text-zinc-500">
        {faNumber(row.correlation_observations)} مشاهده
      </div>
    </td>
  );
}

/**
 * ماتریس بازده — دوره‌های ۱ تا ۱۲ ماه، همبستگی ۹۰ روزه، و تبدیل ارز.
 *
 * دوره‌ای که داده‌اش کافی نیست «ناقص» برچسب می‌خورد و دلیلش در tooltip است؛
 * مقدار غایب «—» می‌ماند و هرگز صفر یا میانگین‌گیری جعلی نمی‌شود.
 */
export function ReturnsMatrix({
  data,
  baseCurrency,
  onBaseCurrencyChange,
  pending,
}: {
  data: ReturnsMatrixResponse;
  baseCurrency: "IRR" | "USD";
  onBaseCurrencyChange: (value: "IRR" | "USD") => void;
  pending?: boolean;
}) {
  return (
    <section aria-labelledby="returns-heading" className="space-y-3" data-testid="returns-section">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="returns-heading" className="text-base font-semibold text-zinc-100">
            ماتریس بازده
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            بازده سادهٔ نقطه‌به‌نقطه از آخرین مشاهدهٔ موجود؛ همبستگی پیرسون روی بازده
            روزانه و حداکثر ۹۰ مشاهدهٔ مشترک.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-zinc-800/70 bg-zinc-900/60 p-1">
          {(["IRR", "USD"] as const).map((currency) => (
            <button
              key={currency}
              type="button"
              aria-pressed={baseCurrency === currency}
              data-testid={`base-currency-${currency}`}
              onClick={() => onBaseCurrencyChange(currency)}
              className={`rounded-md px-3 py-1 text-xs transition ${
                baseCurrency === currency
                  ? "bg-amber-500/20 font-semibold text-amber-300"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {currency === "IRR" ? "ریالی" : "دلاری"}
            </button>
          ))}
        </div>
      </div>

      {baseCurrency === "USD" && (
        <SourceNotice testId="returns-usd-note">
          بازده ریالی با بازده دلار/ریالِ همان پنجره به دلار تبدیل شده است؛ دارایی‌های
          دلاری بدون تبدیل می‌مانند. همبستگی همیشه با USD/IRR است.
        </SourceNotice>
      )}

      <div
        className={`overflow-x-auto rounded-xl border border-zinc-800/70 ${pending ? "opacity-60" : ""}`}
      >
        <table className="min-w-[1100px] w-full text-xs" data-testid="returns-matrix">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="px-3 py-2 text-right font-medium">دارایی</th>
              {data.periods.map((period) => (
                <th key={period} scope="col" className="px-3 py-2 text-right font-medium">
                  {PERIOD_LABEL[period] ?? period}
                </th>
              ))}
              <th scope="col" className="px-3 py-2 text-right font-medium">
                همبستگی ۹۰ روزه با USD/IRR
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">منبع / کیفیت</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {data.rows.map((row) => (
              <tr
                key={row.key}
                data-testid={`returns-row-${row.key}`}
                data-native-currency={row.native_currency}
                className="bg-zinc-950/40 align-top hover:bg-zinc-900/40"
              >
                <td className="px-3 py-2">
                  <div className="font-semibold text-zinc-200">{row.label}</div>
                  <div className="mt-0.5 text-[9px] text-zinc-500">
                    ارز بومی: {row.native_currency}
                    {row.native_currency !== data.base_currency && " · تبدیل‌شده"}
                  </div>
                  <div className="mt-1 text-[9px] text-zinc-600">{row.source}</div>
                </td>
                {data.periods.map((period) => (
                  <ReturnCell
                    key={period}
                    cell={row.returns[period]}
                    rowKey={row.key}
                    period={period}
                  />
                ))}
                <CorrelationCell row={row} />
                <td className="px-3 py-2">
                  <DataTrustBadge
                    quality={row.quality}
                    source={row.source}
                    asOf={null}
                    showMeta={false}
                  />
                  {row.data_gaps.length > 0 && (
                    <p
                      className="mt-1 max-w-[180px] text-[9px] leading-4 text-amber-300/70"
                      title={gapTitle(row.data_gaps)}
                    >
                      {row.data_gaps.join("؛ ")}
                    </p>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] leading-5 text-zinc-500" data-testid="returns-method">
        روش: {data.method}
      </p>
    </section>
  );
}
