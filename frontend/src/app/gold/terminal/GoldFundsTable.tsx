"use client";

import { useEffect } from "react";

import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type { FundRow } from "@/types/phase1";

import {
  bubbleTone,
  changeTone,
  faDigits,
  faNumber,
  faPercent,
  faSignedAmount,
  gapTitle,
  navDateLabel,
} from "./format";
import { MissingValue, SourceStamp } from "./TerminalBits";

const NEEDS_COMPOSITION = "نیاز به ترکیب دارایی صندوق";

function compositionReason(row: FundRow): string {
  return gapTitle(row.data_gaps) ?? NEEDS_COMPOSITION;
}

/**
 * جدول صندوق‌های طلا — قیمت، حجم/ارزش، ارزش بازار، NAV صدور/ابطال،
 * حباب اسمی/ذاتی/واقعی و ترکیب سکه/شمش/نقد/سایر.
 *
 * حباب ذاتی، حباب واقعی و USD ضمنی تا وقتی ترکیب دارایی صندوق از منبعی
 * نیامده باشد «—» می‌مانند؛ هرگز صفر یا تخمین نمایش داده نمی‌شود.
 */
export function GoldFundsTable({ funds }: { funds: FundRow[] }) {
  // نقشهٔ بازار فاز ۲ با `#fund-<symbol>` به همین ردیف لینک می‌دهد؛ بعد از
  // بارگذاری داده باید ردیف را اسکرول و موقتاً هایلایت کنیم (hashchange هم
  // پوشش داده می‌شود تا ناوبری در همان صفحه دوباره کار کند).
  useEffect(() => {
    if (typeof window === "undefined") return;
    let timer: number | null = null;

    const reveal = () => {
      const hash = window.location.hash;
      if (!hash.startsWith("#fund-")) return;
      let id: string;
      try {
        id = decodeURIComponent(hash.slice(1));
      } catch {
        return;
      }
      const element = document.getElementById(id);
      if (!element) return;
      if (typeof element.scrollIntoView === "function") {
        element.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      element.classList.add("gd-fund-flash");
      if (timer !== null) window.clearTimeout(timer);
      timer = window.setTimeout(() => element.classList.remove("gd-fund-flash"), 2600);
    };

    reveal();
    window.addEventListener("hashchange", reveal);
    return () => {
      window.removeEventListener("hashchange", reveal);
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [funds]);

  return (
    <section aria-labelledby="funds-heading" className="space-y-3">
      <div>
        <h2 id="funds-heading" className="text-base font-semibold text-zinc-100">
          صندوق‌های طلا
        </h2>
        <p className="mt-1 text-xs text-zinc-500">
          {faNumber(funds.length)} صندوق طلا از فید IME. حباب اسمی = (قیمت بازار − NAV) ÷ NAV.
          حباب ذاتی/واقعی فقط با ترکیب دارایی محاسبه می‌شود.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-800/70">
        <table className="min-w-[1900px] w-full text-xs" data-testid="funds-table">
          <thead className="bg-zinc-900/80 text-zinc-400">
            <tr>
              <th scope="col" className="px-3 py-2 text-right font-medium">صندوق</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">قیمت بازار (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تغییر (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حجم</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش معاملات (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ارزش بازار (ریال)</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">NAV صدور</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">NAV ابطال</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">تاریخ NAV</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">قیمت ذاتی پشتوانه</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب اسمی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب ذاتی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">حباب واقعی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">سکه ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">شمش ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">نقد ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">سایر ٪</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">ترکیب</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">USD ضمنی</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">کیفیت</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {funds.map((row) => {
              const reason = compositionReason(row);
              return (
                <tr
                  key={row.symbol}
                  id={`fund-${row.symbol}`}
                  data-testid={`fund-row-${row.symbol}`}
                  className="bg-zinc-950/40 align-top hover:bg-zinc-900/40"
                >
                  <td className="px-3 py-2">
                    <div className="font-semibold text-zinc-200">{row.name}</div>
                    <div className="mt-0.5 text-[10px] text-zinc-500">{row.symbol}</div>
                  </td>
                  <td className="px-3 py-2">
                    {row.price === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      <div className="tabular-nums text-zinc-100">{faNumber(row.price)}</div>
                    )}
                    <SourceStamp source={row.source_detail} asOf={row.as_of} gaps={row.data_gaps} />
                    <div className="mt-0.5 text-[9px] text-zinc-500">
                      معامله: {row.last_trade_time ? faDigits(row.last_trade_time) : "ساعت ناموجود"} ·{" "}
                      {row.last_trade_date ? navDateLabel(row.last_trade_date, null) : "تاریخ ناموجود"}
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
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.market_cap === null ? <MissingValue /> : faNumber(row.market_cap)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.nav_issue === null ? <MissingValue /> : faNumber(row.nav_issue)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.nav_redemption === null ? <MissingValue /> : faNumber(row.nav_redemption)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="tabular-nums text-zinc-200">
                      {navDateLabel(row.nav_date, row.nav_time)}
                    </div>
                    <div className="mt-1">
                      <DataTrustBadge quality={row.nav_quality} showMeta={false} />
                    </div>
                    <SourceStamp
                      source={row.nav_source}
                      asOf={row.nav_as_of}
                      gaps={row.data_gaps}
                    />
                  </td>
                  <td className="px-3 py-2">
                    {row.intrinsic_price === null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      <div className="tabular-nums text-zinc-200">
                        {faNumber(row.intrinsic_price)}
                      </div>
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_nominal_pct)}`}>
                    {row.bubble_nominal_pct === null ? (
                      <MissingValue reason={reason} />
                    ) : (
                      <>
                        <div>{faPercent(row.bubble_nominal_pct)}</div>
                        <div className="mt-0.5 text-[9px] text-zinc-500">
                          {row.bubble_nominal_amount === null
                            ? "—"
                            : `${faSignedAmount(row.bubble_nominal_amount)} ریال`}
                        </div>
                      </>
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_intrinsic_pct)}`}>
                    {row.bubble_intrinsic_pct === null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      <>
                        <div>{faPercent(row.bubble_intrinsic_pct)}</div>
                        <div className="mt-0.5 text-[9px] text-zinc-500">
                          {row.bubble_intrinsic_amount === null
                            ? "—"
                            : `${faSignedAmount(row.bubble_intrinsic_amount)} ریال`}
                        </div>
                      </>
                    )}
                  </td>
                  <td className={`px-3 py-2 tabular-nums ${bubbleTone(row.bubble_real_pct)}`}>
                    {row.bubble_real_pct === null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      faPercent(row.bubble_real_pct)
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.composition?.coin_pct == null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      faPercent(row.composition.coin_pct, 1)
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.composition?.bar_pct == null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      faPercent(row.composition.bar_pct, 1)
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.composition?.cash_pct == null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      faPercent(row.composition.cash_pct, 1)
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-zinc-200">
                    {row.composition?.other_pct == null ? (
                      <MissingValue reason={NEEDS_COMPOSITION} />
                    ) : (
                      faPercent(row.composition.other_pct, 1)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold ring-1 ${
                        row.composition_status === "available"
                          ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/40"
                          : "bg-amber-500/10 text-amber-300 ring-amber-500/40"
                      }`}
                      title={reason}
                      data-testid={`composition-status-${row.symbol}`}
                    >
                      {row.composition_status === "available" ? "موجود" : NEEDS_COMPOSITION}
                    </span>
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
                  <td className="px-3 py-2">
                    <DataTrustBadge
                      quality={row.quality}
                      source={row.source_detail}
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

      {funds.length === 0 && (
        <p className="rounded-lg border border-zinc-800/70 px-4 py-3 text-xs text-zinc-500">
          فهرست صندوق‌های طلا خالی است؛ فید IME هنوز ردیفی برنگردانده است.
        </p>
      )}
    </section>
  );
}
