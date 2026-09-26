"use client";

import { useState } from "react";
import Link from "next/link";
import { Map, MapPinned } from "lucide-react";
import { useSectorMap } from "@/hooks/useMarketData";
import { fmtPct } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import LiveDataBanner from "./LiveDataBanner";
import { EmptyState, SectionHeader } from "./primitives";

const UP_RGB = "22,163,74";
const DOWN_RGB = "220,38,38";

const VIEWS = [
  { key: "stocks", label: "سهام" },
  { key: "funds", label: "صندوق‌ها" },
  { key: "monthly", label: "ماهانه" },
] as const;

type ViewKey = (typeof VIEWS)[number]["key"];

function tileStyle(changePct: number) {
  const pos = changePct >= 0;
  const heat = Math.min(Math.abs(changePct) / 3, 1);
  const alpha = 0.1 + heat * 0.5;
  const rgb = pos ? UP_RGB : DOWN_RGB;
  return {
    background: `rgba(${rgb}, ${alpha})`,
    borderColor: `rgba(${rgb}, ${0.28 + heat * 0.4})`,
    color: alpha > 0.45 ? "#fff" : pos ? "var(--up)" : "var(--down)",
  };
}

export default function MarketMap() {
  const [view, setView] = useState<ViewKey>("stocks");
  const { data: sectors, isLive, isError, isLoading } = useSectorMap();

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={Map}
        title="نقشه بازار"
        subtitle={view === "monthly" ? "بازده یک‌ماهه گروه‌های صنعت" : "وضعیت امروز بر اساس تغییر قیمت"}
        action={
          <div className="flex items-center gap-1 rounded-xl border border-line bg-soft p-1">
            {VIEWS.map((v) => (
              <button
                key={v.key}
                type="button"
                onClick={() => setView(v.key)}
                className={cn(
                  "cursor-pointer rounded-lg px-2.5 py-1 text-[10.5px] font-bold transition-colors duration-150",
                  view === v.key ? "bg-card text-ink shadow-[var(--shadow-card)]" : "text-ink-3 hover:text-ink-2",
                )}
              >
                {v.label}
              </button>
            ))}
          </div>
        }
      />
      <LiveDataBanner state={{ isLive: isLive || view !== "stocks", isError, isLoading: view === "stocks" && isLoading }} />
      {view !== "stocks" || sectors.length === 0 ? (
        view === "stocks" ? (
          <div className="mt-4">
            <EmptyState
              icon={MapPinned}
              title="داده زنده‌ای برای نقشه بازار در دسترس نیست"
              hint="تا بازگشت خوراک treemap این بخش خالی می‌ماند."
            />
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState
              icon={MapPinned}
              title="داده‌ای برای این نما در دسترس نیست"
              hint="منبع زنده برای صندوق‌ها و بازده ماهانه هنوز متصل نشده است."
            />
          </div>
        )
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
          {sectors.map((s) => (
            <Link
              key={s.name}
              href="/heatmap"
              style={tileStyle(s.changePct)}
              className="group flex cursor-pointer flex-col justify-between rounded-xl border p-3 transition-transform duration-150 hover:scale-[1.02]"
            >
              <span className="truncate text-[11px] font-bold leading-snug">{s.name}</span>
              <span className="mt-2 flex items-baseline justify-between gap-1">
                <span dir="ltr" className="font-mono text-[15px] font-black tabular-nums">
                  {fmtPct(s.changePct, 1)}
                </span>
                <span className="text-[9.5px] opacity-70">{s.count} نماد</span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
