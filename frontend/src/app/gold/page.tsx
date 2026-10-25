"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSnapshot, isServiceUnavailable, subscribeGoldWS } from "@/lib/goldApi";
import { GOLD_FALLBACK_POLL_MS, useGoldWS } from "@/hooks/useGoldWS";
import GoldSummarySection from "./components/SummarySection";
import CoinBubbleTable from "./components/CoinBubbleTable";
import ImeSpreadSection from "./components/ImeSpreadSection";
import FundsPnavTable from "./components/FundsPnavTable";
import FeedHealthSection from "./components/FeedHealthSection";
import EventCalendarSection from "./components/EventCalendarSection";
import GoldCommandCenterHeader from "./components/CommandCenterHeader";

export default function GoldCommandCenterPage() {
  const qc = useQueryClient();
  const ws = useGoldWS();

  // One snapshot query for the whole page: every section below is either fed
  // from this response or owns its own (smaller) query.
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: getSnapshot,
    // F6: سوکت وصل باشد polling خاموش — وگرنه همان داده هم push می‌شود هم
    // ۶۰ ثانیه یک‌بار کشیده می‌شد. در قطعی، polling ۱۰ ثانیه‌ای جایش را می‌گیرد.
    refetchInterval: ws.connected ? false : GOLD_FALLBACK_POLL_MS,
    refetchOnWindowFocus: false,
    staleTime: 55_000,
  });

  // پیام snapshotِ روی WS مستقیم در همان cache نوشته می‌شود؛ بدون این، با
  // خاموش شدن polling صفحه تا رفرش دستی کهنه می‌ماند.
  useEffect(
    () =>
      subscribeGoldWS(undefined, undefined, (snap) => {
        qc.setQueryData(["gold", "snapshot"], snap);
      }),
    [qc],
  );

  return (
    <div className="gold-command-center">
      <GoldCommandCenterHeader lastUpdated={data?.snapshot_at} />
      <main className="gold-command-center__main space-y-6">
        {isError && (
          <div className="rounded-lg border border-rose-700/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
            {isServiceUnavailable(error)
              ? "سرویس دادهٔ طلا موقتاً در دسترس نیست (۵۰۳)؛ چند لحظه دیگر دوباره تلاش کنید."
              : "دریافت اسنپ‌شات بازار ناموفق بود."}
          </div>
        )}

        {ws.stale && (
          <div
            className="rounded-lg px-4 py-3 text-xs"
            style={{ background: "var(--gd-bg-2)", color: "var(--gd-warn)", border: "1px solid var(--gd-border)" }}
          >
            اتصال برقرار است ولی پیام تازه‌ای نمی‌رسد — اعداد روی صفحه کهنه‌اند.
          </div>
        )}

        <GoldSummarySection snapshot={data} isLoading={isLoading} />

        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-zinc-300">حباب سکه</h2>
          <CoinBubbleTable data={data ? Object.values(data.coins) : undefined} />
        </section>

        <ImeSpreadSection />

        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-zinc-300">صندوق‌های طلا (P/NAV)</h2>
          <FundsPnavTable data={data?.funds} />
        </section>

        <FeedHealthSection />
        <EventCalendarSection />
      </main>
    </div>
  );
}
