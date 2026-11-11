import { DataTrustBadge } from "@/components/gold/DataTrustBadge";
import type { TickerItem } from "@/types/phase1";

import { changeTone, faNumber, faPercent, faSignedAmount } from "./format";

function unitLabel(unit: TickerItem["unit"]): string {
  return unit === "ounce" ? "دلار / اونس" : "ریال";
}

/**
 * تیکر ثابت بالای میز داده: XAU/USD، طلای ۱۸ عیار (ریال) و دلار آزاد (ریال).
 * شاخص صندوق‌ها عمداً بدون عدد و با برچسب «در دست ساخت» می‌آید.
 */
export function Phase1Ticker({ items }: { items: TickerItem[] }) {
  return (
    <section
      aria-label="تیکر بازار"
      data-testid="phase1-ticker"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
    >
      {items.map((item) => (
        <article
          key={item.key}
          data-testid={`ticker-${item.key}`}
          className="rounded-xl border border-zinc-800/70 bg-zinc-900/50 px-4 py-3"
        >
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-xs font-semibold text-zinc-300">{item.label}</h3>
            {item.status === "under_construction" && (
              <span
                data-testid="under-construction"
                className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-bold text-sky-300 ring-1 ring-sky-500/40"
              >
                در دست ساخت
              </span>
            )}
          </div>

          {item.status === "under_construction" ? (
            <p className="mt-3 text-xs text-zinc-500">
              {item.note ?? "منبع این شاخص متصل نیست."}
            </p>
          ) : (
            <>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span
                  className="text-xl font-black tabular-nums text-zinc-100"
                  data-testid={`ticker-price-${item.key}`}
                >
                  {faNumber(item.price, item.unit === "ounce" ? 2 : 0)}
                </span>
                <span className="text-[10px] text-zinc-500">{unitLabel(item.unit)}</span>
              </div>

              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]">
                <span className={`tabular-nums ${changeTone(item.change_pct)}`}>
                  {item.change_pct === null ? "تغییر: —" : faPercent(item.change_pct)}
                </span>
                {item.change_amount !== null && (
                  <span className={`tabular-nums ${changeTone(item.change_amount)}`}>
                    {faSignedAmount(item.change_amount)}{" "}
                    {item.unit === "ounce" ? "دلار" : "ریال"}
                  </span>
                )}
              </div>

              <div className="mt-2">
                <DataTrustBadge
                  quality={item.quality}
                  source={item.source_detail}
                  asOf={item.as_of}
                />
              </div>

              {item.note && <p className="mt-1 text-[10px] text-zinc-500">{item.note}</p>}
            </>
          )}
        </article>
      ))}
    </section>
  );
}
