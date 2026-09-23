"use client";

import { Eye, Globe2 } from "lucide-react";
import { useMarketOverview, useQuoteCards, useFlowSummary } from "@/hooks/useMarketData";
import LiveDataBanner from "./LiveDataBanner";
import { fmtBillion, fmtInt, fmtNum } from "@/lib/market-format";
import { MiniMetric, SectionHeader } from "./primitives";

export default function MarketOverview() {
  const { data: live, isLive, isError, isLoading } = useMarketOverview();
  const { data: quotes } = useQuoteCards();
  const flow = useFlowSummary();
  // No silent mock substitution: values render an em-dash when the backend
  // has no live data — the LiveDataBanner below explains why.
  const breadth = live?.breadth ?? { up: 0, down: 0, flat: 0 };
  const tradeValueB = live?.tradeValueB ?? null;
  const total = breadth.up + breadth.down + breadth.flat;
  const upPct = total > 0 ? (breadth.up / total) * 100 : 0;

  // Total market cap in USD billion. There is NO live market-cap feed yet, so
  // the hero renders an explicit em-dash instead of the old mock constant —
  // the dollar rate itself comes only from the live quote card.
  const dollar = quotes.find((q) => q.id === "USD" || q.id === "dollar" || q.kind === "dollar");
  const usdRate = dollar?.price != null && dollar.price > 1000 ? dollar.price : null;
  const totalCapB: number | null = null; // TODO: wire a real market-cap endpoint
  const marketCapUsdB = totalCapB != null && usdRate != null ? totalCapB / usdRate : null;

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader icon={Eye} title="نگاه کلی به بازار" subtitle="وضعیت امروز بازار سهام" />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />

      {/* Total market cap — hero metric (needs the live USD quote) */}
      <div className="relative mt-4 overflow-hidden rounded-2xl border border-primary-600/25 bg-gradient-to-bl from-primary-600/10 via-soft/40 to-soft/10 p-4 dark:border-brand-300/25">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-[11px] font-bold text-ink-2">
              <Globe2 className="size-3.5 text-primary-600 dark:text-brand-300" aria-hidden />
              ارزش کل بازار سهام
            </p>
            <p dir="ltr" className="mt-1.5 font-mono text-[26px] font-black leading-none tabular-nums text-ink">
              {marketCapUsdB != null ? fmtNum(marketCapUsdB, 1) : "—"}
              <span className="ms-1.5 text-[13px] font-bold">B$</span>
            </p>
            <p className="mt-1.5 text-[10px] text-ink-3">
              معادل <span dir="ltr" className="font-mono">{totalCapB != null ? fmtBillion(totalCapB) : "—"}</span> میلیارد تومان — با نرخ دلار آزاد
            </p>
          </div>
          <span dir="ltr" className="shrink-0 rounded-xl border border-line bg-card/70 px-2.5 py-1 font-mono text-[10px] font-bold text-ink-2 tabular-nums">
            $1 = {usdRate != null ? fmtInt(usdRate) : "—"}
          </span>
        </div>
      </div>

      {/* Breadth bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-[11px] font-bold">
          <span className="text-up">{fmtInt(breadth.up)} نماد مثبت</span>
          <span className="text-ink-3">مثبت {upPct.toFixed(0)}٪</span>
          <span className="text-down">{fmtInt(breadth.down)} نماد منفی</span>
        </div>
        <div className="mt-2 flex h-2.5 gap-1 overflow-hidden rounded-full bg-soft" dir="rtl">
          <div className="h-full rounded-full bg-up/80 transition-all duration-500" style={{ width: `${upPct}%` }} />
          <div className="h-full flex-1 rounded-full bg-down/70 transition-all duration-500" />
        </div>
        <p className="mt-1.5 text-center text-[10px] text-ink-3">
          {fmtInt(breadth.flat)} نماد بدون تغییر
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <MiniMetric
          label="ارزش معاملات خرد"
          value={tradeValueB != null ? `${fmtBillion(tradeValueB)} م.ت` : "—"}
          hint="میلیارد تومان"
        />
        <MiniMetric
          label="ورود پول حقیقی"
          value={flow?.realNetB != null ? (flow.realNetB >= 0 ? `+${fmtBillion(flow.realNetB)}` : fmtBillion(flow.realNetB)) : "—"}
          tone={flow?.realNetB != null && flow.realNetB >= 0 ? "up" : "down"}
          hint="میلیارد تومان"
        />
        <MiniMetric label="صف خرید" value={flow?.queueBuy != null ? fmtInt(flow.queueBuy) : "—"} tone="up" hint="نماد" />
        <MiniMetric label="صف فروش" value={flow?.queueSell != null ? fmtInt(flow.queueSell) : "—"} tone="down" hint="نماد" />
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-2.5">
        <MiniMetric label="حجم معاملات" value={live?.volumeM != null ? `${fmtInt(live.volumeM)} م` : "—"} hint="میلیون سهم" />
        <MiniMetric label="نسبت P/E بازار" value="—" hint="منبع داده متصل نیست" />
      </div>

      {tradeValueB != null && (
        <div className="mt-3 rounded-xl border border-line bg-soft/60 p-3">
          <p className="text-[11px] font-bold text-ink-2">متن بازار</p>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-3">
            ارزش معاملات خرد امروز به{" "}
            <span dir="ltr" className="font-mono font-bold text-ink">{fmtBillion(tradeValueB)}</span>{" "}
            میلیارد تومان رسید؛ حقیقی‌ها{" "}
            <span className="font-bold text-up">
              {(flow?.realNetB ?? 0) >= 0 ? "+" : ""}{fmtBillion(flow?.realNetB ?? 0)}
            </span>{" "}
            میلیارد تومان وارد بازار کردند.
          </p>
        </div>
      )}
    </section>
  );
}
