"use client";

import type { CertificateRow } from "@/types/phase1";

import { bubbleTone, changeTone, faDigits, faNumber, faPercent, faSignedAmount, gapTitle } from "./format";
import { MissingValue, QualityCell, SourceStamp } from "./TerminalBits";

const CONTRACT_LABEL: Record<string, string> = {
  GoldBar: "گواهی شمش طلا",
  GoldCoin: "گواهی سکه طلا",
};

/**
 * گواهی‌های سپردهٔ کالایی طلا.
 *
 * ارزش ذاتی/حباب/USD ضمنی عمداً خالی است: `contract_size` در این فید «ضریب
 * تبدیل نماد به گروه انبار» است، نه گرم؛ بدون وزن و عیار قرارداد، هر عددی
 * ساختگی می‌شد. دلیلش زیر جدول نوشته می‌شود.
 */
export function CertificateTable({ rows }: { rows: CertificateRow[] }) {
  return (
    <section aria-labelledby="certificates-heading" className="space-y-3">
      <div>
        <h2 id="certificates-heading" className="text-base font-semibold text-zinc-100">
          گواهی سپردهٔ طلا
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          قیمت، تغییر، حجم و ارزش معاملات از فید IME. ستون‌های تحلیلی تا دریافت وزن و
          عیار قرارداد «—» می‌مانند.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
        <table className="min-w-[1050px] w-full text-xs" data-testid="certificates-table">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="px-3 py-2 text-right font-medium">قرارداد</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">قیمت (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حجم</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش معاملات (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">اندازه قرارداد</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش ذاتی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">منبع و کیفیت</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {rows.map((row) => (
              <tr
                key={row.contract_code}
                data-testid={`certificate-row-${row.contract_code}`}
                className="bg-zinc-950/40 align-top hover:bg-zinc-900/40"
              >
                <td className="px-3 py-2">
                  <div className="font-semibold text-zinc-200">
                    {CONTRACT_LABEL[row.contract_code] ?? row.contract_code}
                  </div>
                  <div className="mt-0.5 text-[10px] text-zinc-500">
                    {row.commodity ?? "کالا: نامشخص"}
                    {row.description ? ` · ${row.description}` : ""}
                  </div>
                </td>
                <td className="px-3 py-2">
                  {row.price === null ? (
                    <MissingValue reason={gapTitle(row.data_gaps)} />
                  ) : (
                    <div className="tabular-nums text-zinc-100">{faNumber(row.price)}</div>
                  )}
                  <SourceStamp source={row.source_detail} asOf={row.as_of} gaps={row.data_gaps} />
                  <div className="mt-0.5 text-[9px] text-zinc-500">
                    تاریخ منبع: {row.source_date ? faDigits(row.source_date.replace(/-/g, "/")) : "ناموجود"}
                  </div>
                </td>
                <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_pct)}`}>
                  {row.change_pct === null ? <MissingValue /> : faPercent(row.change_pct)}
                </td>
                <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_amount)}`}>
                  {row.change_amount === null ? <MissingValue /> : faSignedAmount(row.change_amount)}
                </td>
                <td className="px-3 py-2 tabular-nums text-zinc-200">
                  {row.volume === null ? <MissingValue /> : faNumber(row.volume)}
                </td>
                <td className="px-3 py-2 tabular-nums text-zinc-200">
                  {row.turnover === null ? <MissingValue /> : faNumber(row.turnover)}
                </td>
                <td className="px-3 py-2">
                  {row.contract_size === null ? (
                    <MissingValue />
                  ) : (
                    <div className="tabular-nums text-zinc-200">{faNumber(row.contract_size)}</div>
                  )}
                  <div className="mt-0.5 text-[9px] text-zinc-500">
                    {row.contract_size_unit ?? "واحد: نامشخص"}
                  </div>
                </td>
                <td className="px-3 py-2 tabular-nums text-zinc-200">
                  {row.intrinsic === null ? (
                    <MissingValue reason={gapTitle(row.data_gaps)} />
                  ) : (
                    faNumber(row.intrinsic)
                  )}
                </td>
                <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_pct)}`}>
                  {row.bubble_pct === null ? (
                    <MissingValue reason={gapTitle(row.data_gaps)} />
                  ) : (
                    faPercent(row.bubble_pct)
                  )}
                </td>
                <td className="px-3 py-2 tabular-nums text-zinc-200">
                  {row.implied_usd === null ? (
                    <MissingValue reason={gapTitle(row.data_gaps)} />
                  ) : (
                    faNumber(row.implied_usd, 2)
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
            ))}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <p className="rounded-lg border border-zinc-800/70 px-4 py-3 text-xs text-zinc-500">
          گواهی طلایی در فید IME موجود نیست.
        </p>
      )}

      {rows.length > 0 && (
        <details className="rounded-lg border border-zinc-800/70 px-4 py-2 text-[10px] text-zinc-500">
          <summary className="cursor-pointer text-zinc-400">
            چرا ارزش ذاتی گواهی‌ها خالی است؟
          </summary>
          <ul className="mt-2 list-disc space-y-1 pr-5">
            {rows.map((row) => (
              <li key={row.contract_code}>
                <span className="text-zinc-400">{CONTRACT_LABEL[row.contract_code] ?? row.contract_code}:</span>{" "}
                {gapTitle(row.data_gaps) ?? "دلیل در منبع ثبت نشده است."}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
