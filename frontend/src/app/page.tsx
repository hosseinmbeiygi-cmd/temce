"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import DashboardShell from "@/components/layout/DashboardShell";
import NewsStrip from "@/components/dashboard/NewsStrip";
import QuoteCards from "@/components/dashboard/QuoteCards";
import IndexCards from "@/components/dashboard/IndexCards";
import MarketMap from "@/components/dashboard/MarketMap";
import MarketOverview from "@/components/dashboard/MarketOverview";
import TopStocksToday from "@/components/dashboard/TopStocksToday";
import OwnershipChange from "@/components/dashboard/OwnershipChange";
import IndexImpacts from "@/components/dashboard/IndexImpacts";
import ValueVolumePanel from "@/components/dashboard/ValueVolumePanel";
import EventCalendar from "@/components/dashboard/EventCalendar";
import LiquidityBlocks from "@/components/dashboard/LiquidityBlocks";
import GlobalMarkets from "@/components/dashboard/GlobalMarkets";
import { SkeletonBlock } from "@/components/dashboard/primitives";
import { useMarketSession } from "@/hooks/useMarketData";
import { cn } from "@/lib/cn";
import { faNum } from "@/lib/market-format";

// The three recharts widgets are the heaviest code on the page. Load them
// after first paint; the fallbacks below reserve their exact layout so
// nothing shifts when they stream in.
const TrendChart = dynamic(() => import("@/components/dashboard/TrendChart"), {
  loading: () => <ChartSectionSkeleton height="h-72" />,
});
const TripleChartsGroup = dynamic(() => import("@/components/dashboard/TripleChartsGroup"), {
  loading: () => <ChartGroupSkeleton />,
});
const AssetAllocationPie = dynamic(() => import("@/components/dashboard/AssetAllocationPie"), {
  loading: () => <ChartSectionSkeleton height="h-64" />,
});

function ChartSectionSkeleton({ height }: { height: string }) {
  return (
    <div className={`rounded-2xl border border-line bg-card p-4 sm:p-5 ${height}`}>
      <SkeletonBlock className="h-5 w-40" />
      <SkeletonBlock className="mt-2.5 h-3.5 w-56" />
      <SkeletonBlock className="mt-4 h-[calc(100%-4.5rem)] w-full" />
    </div>
  );
}

function ChartGroupSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl border border-line bg-card p-4 sm:p-5">
          <SkeletonBlock className="h-5 w-32" />
          <SkeletonBlock className="mt-2 h-3 w-44" />
          <SkeletonBlock className="mt-3 h-44 w-full" />
        </div>
      ))}
    </div>
  );
}

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
  const session = useMarketSession();

  return (
    <DashboardShell>
      {/* Page header */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="hero-title text-[24px] font-black leading-tight">داشبورد بازار سرمایه</h1>
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

        {/* Below-the-fold sections — skip their offscreen paint/layout work. */}
        <motion.section variants={item} className="cv-auto">
          <EventCalendar />
        </motion.section>

        <motion.section variants={item} className="cv-auto">
          <LiquidityBlocks />
        </motion.section>
      </motion.div>
    </DashboardShell>
  );
}
