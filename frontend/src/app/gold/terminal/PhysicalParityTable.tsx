"use client";

import { useState } from "react";

import type { PhysicalRow } from "@/types/phase1";

import {
  bubbleTone,
  changeTone,
  faNumber,
  faPercent,
  faSignedAmount,
  gapTitle,
} from "./format";
import { MissingValue, QualityCell, SourceStamp } from "./TerminalBits";

const BASIS_LABEL: Record<PhysicalRow["price_basis"], string> = {
  gram: "هر گرم",
  mesghal: "هر مثقال",
  coin: "هر سکه",
};

function reasonFor(row: PhysicalRow, needle: string): string | undefined {
  const match = row.data_gaps.find((gap) => gap.includes(needle));
  return match ?? gapTitle(row.data_gaps);
}

/**
 * جدول برابری طلا و سکه — قیمت، تغییر، ارزش ذاتی موتور فاز ۰، حباب و USD ضمنی.
 * سوییچ «نمایش حباب به درصد» بین درصد و مبلغ ریالی جابه‌جا می‌کند.
 */
export function PhysicalParityTable({ rows }: { rows: PhysicalRow[] }) {
  const [showPercent, setShowPercent] = useState(true);

  return (
    <section aria-labelledby="physical-heading" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="physical-heading" className="text-base font-semibold text-zinc-100">
            طلا و سکه
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            ارزش ذاتی از موتور فاز ۰ (XAU/USD و دلار آزاد مرجع) محاسبه می‌شود؛ حباب = (بازار − ذاتی) ÷ ذاتی.
          </p>
        </div>
        <label className="inline-flex items-center gap-2 text-xs text-zinc-400">
          <input
            type="checkbox"
            checked={showPercent}
            onChange={(event) => setShowPercent(event.target.checked)}
            className="h-4 w-4 accent-amber-500"
            data-testid="bubble-percent-toggle"
          />
          نمایش حباب به درصد
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
        <table className="min-w-[1100px] w-full text-xs" data-testid="physical-table">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="px-3 py-2 text-right font-medium">دارایی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">قیمت بازار (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش ذاتی (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                حباب {showPercent ? "(٪)" : "(ریال)"}
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">منبع و کیفیت</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {rows.map((row) => {
              const bubbleValue = showPercent ? row.bubble_pct : row.bubble_amount;
              return (
                <tr
                  key={row.symbol}
                  data-testid={`physical-row-${row.symbol}`}
                  className="bg-zinc-950/40 align-top hover:bg-zinc-900/40"
                >
                  <td className="px-3 py-2">
                    <div className="font-semibold text-zinc-200">{row.label}</div>
                    <div className="mt-0.5 text-[10px] text-zinc-500">
                      {row.symbol} · {BASIS_LABEL[row.price_basis]}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {row.price === null ? (
                      <MissingValue reason={reasonFor(row, "قیمت بازار")} />
                    ) : (
                      <div className="tabular-nums text-zinc-100">{faNumber(row.price)}</div>
                    )}
                    <SourceStamp source={row.source_detail} asOf={row.as_of} gaps={row.data_gaps} />
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_pct)}`}>
                    {row.change_pct === null ? <MissingValue /> : faPercent(row.change_pct)}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_amount)}`}>
                    {row.change_amount === null ? <MissingValue /> : faSignedAmount(row.change_amount)}
                  </td>
                  <td className="px-3 py-2">
                    {row.intrinsic === null ? (
                      <MissingValue reason={reasonFor(row, "ارزش ذاتی")} />
                    ) : (
                      <div className="tabular-nums text-zinc-200">{faNumber(row.intrinsic)}</div>
                    )}
                    {row.intrinsic !== null && row.intrinsic_quality !== row.quality && (
                      <div className="mt-0.5 text-[9px] text-zinc-500">
                        ذاتی: {row.intrinsic_quality}
                      </div>
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_pct)}`}>
                    {bubbleValue === null ? (
                      <MissingValue reason={reasonFor(row, "حباب")} />
                    ) : showPercent ? (
                      faPercent(row.bubble_pct)
                    ) : (
                      faSignedAmount(row.bubble_amount)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {row.implied_usd === null ? (
                      <MissingValue reason={reasonFor(row, "USD ضمنی")} />
                    ) : (
                      <div className="tabular-nums text-zinc-200">
                        {faNumber(row.implied_usd, 2)} <span className="text-[9px] text-zinc-500">دلار</span>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <QualityCell
                      quality={row.quality}
                      source={row.source_detail}
                      asOf={row.as_of}
                      gaps={row.data_gaps}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <p className="rounded-lg border border-zinc-800/70 px-4 py-3 text-xs text-zinc-500">
          جدول طلا و سکه خالی است؛ منبع BrsApi هنوز ردیفی برنگردانده است.
        </p>
      )}
    </section>
  );
}
