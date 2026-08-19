"use client";

import Link from "next/link";
import { ArrowLeft, Newspaper } from "lucide-react";
import { useNewsItems } from "@/hooks/useMarketData";
import { cn } from "@/lib/cn";
import { SectionHeader } from "./primitives";

const SENTIMENT_DOT: Record<string, string> = {
  positive: "bg-up",
  negative: "bg-down",
  neutral: "bg-warn",
};

export default function NewsStrip() {
  const NEWS = useNewsItems();
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={Newspaper}
        title="آخرین اخبار بازار"
        subtitle="منتخبی از تیترهای امروز اقتصاد ایران"
        action={
          <Link
            href="/news"
            className="flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-ink-3 transition-colors duration-150 hover:bg-soft hover:text-ink"
          >
            همه اخبار
            <ArrowLeft className="size-3.5" aria-hidden />
          </Link>
        }
      />
      <div className="mt-4 grid gap-2.5 md:grid-cols-3">
        {NEWS.map((item) => (
          <Link
            key={item.id}
            href="/news"
            className="group flex cursor-pointer items-start gap-2.5 rounded-xl border border-transparent p-2.5 transition-all duration-200 hover:border-line hover:bg-soft/70"
          >
            <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", SENTIMENT_DOT[item.sentiment])} />
            <span className="min-w-0">
              <span className="block text-[12.5px] font-medium leading-relaxed text-ink line-clamp-2 group-hover:text-ink">
                {item.title}
              </span>
              <span className="mt-1.5 flex items-center gap-2 text-[10px] text-ink-3">
                <span>{item.source}</span>
                <span aria-hidden>•</span>
                <span>{item.time}</span>
                {item.symbols.length > 0 && (
                  <>
                    <span aria-hidden>•</span>
                    <span className="font-mono">{item.symbols.slice(0, 2).join("،")}</span>
                  </>
                )}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
