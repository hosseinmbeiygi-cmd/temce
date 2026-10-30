"use client";

import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type { TehranBoardResponse, TehranRow } from "@/types/phase2";

import {
  bubbleTone,
  changeTone,
  faNumber,
  faPercent,
  faSignedAmount,
  gapTitle,
} from "../terminal/format";
import { MissingValue, SourceStamp } from "../terminal/TerminalBits";
import { SourceNotice } from "./SectionFeedback";

const KIND_LABEL: Record<TehranRow["kind"], string> = {
  gold: "طلا",
  coin: "سکه",
  used: "دست‌دوم",
  exchange: "تعویض",
};

const SOURCE_STATUS_TEXT: Record<TehranBoardResponse["source_status"], string> = {
  not_connected:
    "هیچ منبع قیمت خرده‌فروشی/بنکداری تهران متصل نیست. همهٔ ستون‌ها حفظ شده‌اند و جای هر قیمت «—» است؛ هیچ عددی جایگزین یا تخمین زده نمی‌شود.",
  partial:
    "بخشی از اقلام تختهٔ تهران از منبع متصل آمده و بقیه بدون قیمت‌اند. ردیف‌های «—» یعنی منبع برای آن قلم داده نداده است.",
  connected: "همهٔ اقلام تختهٔ تهران از منبع متصل قیمت گرفته‌اند.",
};

function reasonOf(row: TehranRow): string | undefined {
  return gapTitle(row.data_gaps) ?? "منبع این قلم را نداده است";
}

/**
 * تختهٔ طلافروشی/بنکداری تهران — قیمت، تغییر، ارزش ذاتی موتور فاز ۰، حباب،
 * USD ضمنی و اختلاف با جدول رسمی فاز ۱.
 *
 * ستون‌ها هرگز به‌خاطر نبود منبع حذف نمی‌شوند؛ ردیف بدون قیمت «—» با دلیل است.
 */
export function TehranBoardTable({ data }: { data: TehranBoardResponse }) {
  return (
    <section aria-labelledby="tehran-heading" className="space-y-3" data-testid="tehran-board">
      <div>
        <h2 id="tehran-heading" className="text-base font-semibold text-zinc-100">
          تختهٔ طلافروشی و بنکداری تهران
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          {faNumber(data.rows.length)} قلم؛ اختلاف با جدول رسمی = قیمت تهران − قیمت فاز ۱.
          ارزش ذاتی و حباب با همان موتور فاز ۰ (XAU/USD × دلار آزاد) محاسبه می‌شود.
        </p>
      </div>

      <SourceNotice
        tone={data.source_status === "connected" ? "neutral" : "warn"}
        testId="tehran-source-status"
      >
        {SOURCE_STATUS_TEXT[data.source_status]}
      </SourceNotice>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
        <table className="min-w-[1800px] w-full text-xs" data-testid="tehran-board-table">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="px-3 py-2 text-right font-medium">قلم</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">قیمت تهران (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش ذاتی (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">اختلاف با جدول رسمی ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">اختلاف (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">مرجع مقایسه</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">کیفیت</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {data.rows.map((row) => {
              const reason = reasonOf(row);
              return (
                <tr
                  key={row.key}
                  id={`tehran-${row.key}`}
                  data-testid={`tehran-row-${row.key}`}
                  data-kind={row.kind}
                  className={`align-top ${
                    row.kind === "used" || row.kind === "exchange"
                      ? "bg-amber-500/5 hover:bg-amber-500/10"
                      : "bg-zinc-950/40 hover:bg-zinc-900/40"
                  }`}
                >
                  <td className="px-3 py-2">
                    <div className="font-semibold text-zinc-200">{row.label}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1">
                      <span className="rounded bg-zinc-800/80 px-1 py-0.5 text-[9px] text-zinc-300">
                        {KIND_LABEL[row.kind]}
                      </span>
                      {row.purity !== null && (
                        <span className="text-[9px] text-zinc-500">عیار {faNumber(row.purity)}</span>
                      )}
                      {row.price_basis === "coin" && (
                        <span className="text-[9px] text-zinc-500">مبنای سکه</span>
                      )}
                    </div>
                    {row.note && (
                      <div className="mt-1 max-w-[260px] text-[9px] leading-4 text-amber-300/70">
                        {row.note}
                      </div>
                    )}
                    <SourceStamp source={row.source_detail} asOf={row.as_of} gaps={row.data_gaps} />
                  </td>
                  <td className="px-3 py-2">
                    {row.tehran_price === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      <div className="tabular-nums text-zinc-100">
                        {faNumber(row.tehran_price)}
                      </div>
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_pct)}`}>
                    {row.change_pct === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faPercent(row.change_pct)
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${changeTone(row.change_amount)}`}>
                    {row.change_amount === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faSignedAmount(row.change_amount)
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.intrinsic === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      <div>
                        {faNumber(row.intrinsic)}
                        <div className="mt-1">
                          <DataTrustBadge quality={row.intrinsic_quality} showMeta={false} />
                        </div>
                      </div>
                    )}
                  </td>
                  <td
                    data-testid={`tehran-bubble-${row.key}`}
                    className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_pct)}`}
                  >
                    {row.bubble_pct === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faPercent(row.bubble_pct)
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_amount)}`}>
                    {row.bubble_amount === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faSignedAmount(row.bubble_amount)
                    )}
                  </td>
                  <td
                    data-testid={`tehran-spread-${row.key}`}
                    className={`px-3 py-2 tabular-nums ${changeTone(row.spread_vs_official_pct)}`}
                  >
                    {row.spread_vs_official_pct === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faPercent(row.spread_vs_official_pct)
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${changeTone(row.spread_vs_official_amount)}`}>
                    {row.spread_vs_official_amount === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      faSignedAmount(row.spread_vs_official_amount)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {row.implied_usd === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      <div className="tabular-nums text-zinc-200">
                        {faNumber(row.implied_usd, 2)}{" "}
                        <span className="text-[9px] text-zinc-500">دلار</span>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[10px] text-zinc-400" title={row.official_symbol ?? undefined}>
                    {row.official_label ?? "—"}
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
    </section>
  );
}
