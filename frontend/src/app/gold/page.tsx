"use client";

import { useQuery } from "@tanstack/react-query";
import { getSnapshot } from "@/lib/goldApi";
import GoldSummarySection from "./components/SummarySection";
import CoinBubbleTable from "./components/CoinBubbleTable";
import ImeSpreadSection from "./components/ImeSpreadSection";
import FundsPnavTable from "./components/FundsPnavTable";
import FeedHealthSection from "./components/FeedHealthSection";
import EventCalendarSection from "./components/EventCalendarSection";
import GoldCommandCenterHeader from "./components/CommandCenterHeader";

export default function GoldCommandCenterPage() {
  // One snapshot query for the whole page: every section below is either fed
  // from this response or owns its own (smaller) query.
  const { data, isLoading, isError } = useQuery({
    queryKey: ["gold", "snapshot"],
    queryFn: getSnapshot,
    refetchInterval: 60_000,
    staleTime: 55_000,
  });

  return (
    <div className="gold-command-center">
      <GoldCommandCenterHeader lastUpdated={data?.snapshot_at} />
      <main className="gold-command-center__main space-y-6">
        {isError && (
          <div className="rounded-lg border border-rose-700/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
            دریافت اسنپ‌شات بازار ناموفق بود.
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
