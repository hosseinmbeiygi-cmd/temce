"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import DashboardShell from "@/components/layout/DashboardShell";
import DashboardSkeleton from "@/components/layout/DashboardSkeleton";
import NewsStrip from "@/components/dashboard/NewsStrip";
import QuoteCards from "@/components/dashboard/QuoteCards";
import IndexCards from "@/components/dashboard/IndexCards";
import TripleChartsGroup from "@/components/dashboard/TripleChartsGroup";
import MarketMap from "@/components/dashboard/MarketMap";
import MarketOverview from "@/components/dashboard/MarketOverview";
import TopStocksToday from "@/components/dashboard/TopStocksToday";
import OwnershipChange from "@/components/dashboard/OwnershipChange";
import AssetAllocationPie from "@/components/dashboard/AssetAllocationPie";
import IndexImpacts from "@/components/dashboard/IndexImpacts";
import ValueVolumePanel from "@/components/dashboard/ValueVolumePanel";
import LiquidityBlocks from "@/components/dashboard/LiquidityBlocks";
import GlobalMarkets from "@/components/dashboard/GlobalMarkets";
import TrendChart from "@/components/dashboard/TrendChart";
import EventCalendar from "@/components/dashboard/EventCalendar";
import { useMarketSession } from "@/hooks/useMarketData";
import { cn } from "@/lib/cn";
import { faNum } from "@/lib/market-format";

function LiveClock() {
  // Date must not be read during SSR/client hydration; use a stable initial
  // value and start the live clock after the component mounts.
  const [now, setNow] = useState(() => new Date(0));
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(id);
  }, []);
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  return (
    <span dir="ltr" className="font-mono text-[12px] font-bold tabular-nums text-ink">
      {faNum(`${hh}:${mm}`)}
    </span>
  );
}

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055 } },
};

const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

export default function DashboardPage() {
  const [ready, setReady] = useState(false);
  const session = useMarketSession();

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 620);
    return () => clearTimeout(t);
  }, []);

  return (
    <DashboardShell>
      {/* Page header */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-black leading-tight text-ink">داشبورد بازار سرمایه</h1>
          <p className="mt-1 text-[12px] text-ink-3">
            نمای زنده قیمت‌ها، جریان پول و عملکرد بازار — {session.dateFa}
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-line bg-card px-3.5 py-2 shadow-[var(--shadow-card)]">
          <span className="relative flex size-2">
            <span
              className={cn(
                "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
                session.isOpen ? "bg-up" : "bg-ink-3"
              )}
            />
            <span
              className={cn("relative inline-flex size-2 rounded-full", session.isOpen ? "bg-up" : "bg-ink-3")}
            />
          </span>
          <span className="text-[11.5px] font-bold text-ink-2">{session.note}</span>
          <span className="hidden h-4 w-px bg-line sm:block" />
          <LiveClock />
        </div>
      </div>

      {!ready ? (
        <DashboardSkeleton />
      ) : (
        <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
          <motion.section variants={item}>
            <NewsStrip />
          </motion.section>
          <motion.section variants={item}>
            <QuoteCards />
          </motion.section>
          <motion.section variants={item}>
            <GlobalMarkets />
          </motion.section>
          <motion.section variants={item}>
            <IndexCards />
          </motion.section>
          <motion.section variants={item}>
            <TrendChart />
          </motion.section>
          <motion.section variants={item}>
            <TripleChartsGroup />
          </motion.section>

          <motion.div variants={item} className="grid gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <MarketMap />
            </div>
            <MarketOverview />
          </motion.div>

          <motion.div variants={item} className="grid gap-4 xl:grid-cols-3">
            <TopStocksToday />
            <OwnershipChange />
            <AssetAllocationPie />
          </motion.div>

          <motion.div variants={item} className="grid gap-4 xl:grid-cols-2">
            <IndexImpacts />
            <ValueVolumePanel />
          </motion.div>

          <motion.div variants={item}>
            <EventCalendar />
          </motion.div>

          <motion.div variants={item}>
            <LiquidityBlocks />
          </motion.div>
        </motion.div>
      )}
    </DashboardShell>
  );
}
