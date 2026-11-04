"use client";

import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type { PlatformsResponse, PlatformQuote } from "@/types/phase2";

import {
  bubbleTone,
  faNumber,
  faPercent,
  gapTitle,
} from "../terminal/format";
import { MissingValue, SourceStamp } from "../terminal/TerminalBits";
import { SourceNotice } from "./SectionFeedback";

function reasonOf(row: PlatformQuote): string | undefined {
  return gapTitle(row.data_gaps) ?? "منبع این قیمت را نداده است";
}

/**
 * مقایسهٔ قیمت بسترهای آنلاین طلا — فقط اطلاعاتی.
 *
 * این کامپوننت عمداً هیچ لینک بیرونی، دکمهٔ خرید، سبد، یا مسیر پرداخت ندارد.
 * نام بستر فقط ارجاع به منبع عمومی است و به معنی همکاری یا تأیید نیست.
 */
export function PlatformsTable({ data }: { data: PlatformsResponse }) {
  return (
    <section aria-labelledby="platforms-heading" className="space-y-3" data-testid="platforms-section">
      <div>
        <h2 id="platforms-heading" className="text-base font-semibold text-zinc-100">
          بسترهای آنلاین طلا — مقایسهٔ قیمت
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          قیمت‌ها به‌ازای هر گرم طلای ۱۸ عیار و به ریال. کارمزد یا شرایط حساب ممکن است در
          قیمت لحاظ شده باشد؛ این اعداد قیمت قابل‌معاملهٔ تضمینی نیستند.
        </p>
      </div>

      <SourceNotice
        tone={data.source_status === "connected" ? "neutral" : "warn"}
        testId="platforms-notice"
      >
        {data.notice}
      </SourceNotice>

      {data.rows.length === 0 ? (
        <div
          data-testid="platforms-empty"
          className="rounded-xl border border-zinc-800/70 bg-zinc-950/40 px-4 py-5 text-xs leading-6 text-zinc-400"
        >
          هیچ ردیف قیمتی از بسترهای آنلاین متصل نیست. با اتصال یک منبع دارای مجوز، این
          ستون‌ها پر می‌شوند: نام بستر، قیمت خرید/فروش، کمترین و بیشترین روز، ارزش ذاتی
          ۱۸ عیار، حباب، USD ضمنی، منبع و زمان. تا آن زمان ردیف ساختگی ساخته نمی‌شود.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
          <table className="min-w-[1200px] w-full text-xs" data-testid="platforms-table">
            <thead className="bg-zinc-900/80 text-zinc-400">
              <tr>
                <th scope="col" className="px-3 py-2 text-right font-medium">بستر</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">قیمت خرید (ریال/گرم ۱۸)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">قیمت فروش (ریال/گرم ۱۸)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">کمترین روز</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">بیشترین روز</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">ارزش ذاتی ۱۸ عیار</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">حباب ٪</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">منبع / کیفیت</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {data.rows.map((row) => {
                const reason = reasonOf(row);
                return (
                  <tr
                    key={row.platform_slug || row.platform}
                    data-testid={`platform-row-${row.platform_slug || row.platform}`}
                    className="bg-zinc-950/40 align-top hover:bg-zinc-900/40"
                  >
                    <td className="px-3 py-2">
                      <div className="font-semibold text-zinc-200">{row.platform}</div>
                      <div className="mt-0.5 text-[9px] text-zinc-500">{row.platform_slug}</div>
                      <SourceStamp source={row.source_detail} asOf={row.as_of} gaps={row.data_gaps} />
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-100">
                      {row.buy_price === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faNumber(row.buy_price)
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-100">
                      {row.sell_price === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faNumber(row.sell_price)
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-300">
                      {row.low_price === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faNumber(row.low_price)
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-300">
                      {row.high_price === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faNumber(row.high_price)
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.intrinsic_18k === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faNumber(row.intrinsic_18k)
                      )}
                    </td>
                    <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_pct)}`}>
                      {row.bubble_pct === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        faPercent(row.bubble_pct)
                      )}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-zinc-200">
                      {row.implied_usd === null ? (
                        <MissingValue reason={reason} />
                      ) : (
                        <span>
                          {faNumber(row.implied_usd, 2)}{" "}
                          <span className="text-[9px] text-zinc-500">دلار</span>
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <DataTrustBadge
                        quality={row.quality}
                        source={row.source}
                        asOf={row.as_of}
                        showMeta={false}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
