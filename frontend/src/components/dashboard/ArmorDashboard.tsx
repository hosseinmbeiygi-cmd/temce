"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Shield, Filter, ArrowUpDown, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/cn";
import { usePrecomputeStore, type SymbolGroup, type SymbolArmorResult } from "@/stores/precomputeStore";
import { SymbolArmorCard } from "./SymbolArmorCard";
import { EmptyState, SkeletonBlock } from "./primitives";

type SortKey = "armor" | "dri" | "symbol";

function GroupSection({
  group,
  results,
  isVisible,
  sortKey,
}: {
  group: SymbolGroup;
  results: SymbolArmorResult[];
  isVisible: boolean;
  sortKey: SortKey;
}) {
  const [showAll, setShowAll] = useState(false);
  const sorted = useMemo(() => {
    const arr = [...results];
    if (sortKey === "armor") arr.sort((a, b) => b.armor_score - a.armor_score);
    else if (sortKey === "dri") arr.sort((a, b) => b.data_dri - a.data_dri);
    else arr.sort((a, b) => a.symbol.localeCompare(b.symbol, "fa"));
    return arr;
  }, [results, sortKey]);

  const display = showAll ? sorted : sorted.slice(0, 12);

  if (!isVisible) return null;

  const groupMeta: Record<SymbolGroup, { title: string; hint: string; accent: string }> = {
    A: { title: "گروه A — نقدشونده‌ها", hint: "پرداخت اول · بیشترین اثر شاخص", accent: "border-up/20 bg-up/[0.04]" },
    B: { title: "گروه B — متوسط", hint: "پس از تثبیت گروه A", accent: "border-warn/20 bg-warn/[0.04]" },
    C: { title: "گروه C — کم‌نقد", hint: "در انتها · ریسک بالاتر", accent: "border-ink/10 bg-soft/60" },
  };
  const meta = groupMeta[group];

  return (
    <motion.section
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={cn("rounded-2xl border p-3 sm:p-4", meta.accent)}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-xl bg-card border border-line text-ink-2">
            <Shield className="size-4" />
          </span>
          <div>
            <h3 className="text-[12px] font-black text-ink">{meta.title}</h3>
            <p className="text-[10px] text-ink-3">{meta.hint} · {results.length} نماد</p>
          </div>
        </div>
        {sorted.length > 12 && (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="inline-flex items-center gap-1 rounded-xl border border-line bg-card px-3 py-1.5 text-[11px] font-bold text-ink-2 hover:bg-soft"
          >
            {showAll ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            {showAll ? "نمایش کمتر" : `نمایش همه (${sorted.length})`}
          </button>
        )}
      </div>

      {results.length === 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-[168px]" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          <AnimatePresence mode="popLayout">
            {display.map((r, idx) => (
              <motion.div
                key={r.symbol}
                layout
                initial={{ opacity: 0, y: 10, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.3, delay: idx * 0.015 }}
              >
                <SymbolArmorCard result={r} index={idx} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.section>
  );
}

export function ArmorDashboard() {
  const allResults = usePrecomputeStore((s) => Array.from(s.results.values()));
  const status = usePrecomputeStore((s) => s.status);
  const visibleGroups = usePrecomputeStore((s) => s.visibleGroups ?? []);

  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("armor");
  const [hideUnreliable, setHideUnreliable] = useState(false);
  const [hideStale, setHideStale] = useState(false);

  const filtered = useMemo(() => {
    let arr = allResults;
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      arr = arr.filter((r) => r.symbol.toLowerCase().includes(q));
    }
    if (hideUnreliable) arr = arr.filter((r) => !r.is_unreliable);
    if (hideStale) arr = arr.filter((r) => !r.is_stale);
    return arr;
  }, [allResults, query, hideUnreliable, hideStale]);

  const byGroup = useMemo(() => {
    const m: Record<SymbolGroup, SymbolArmorResult[]> = { A: [], B: [], C: [] };
    for (const r of filtered) {
      if (m[r.group]) m[r.group].push(r);
    }
    // also sort within group by sortKey
    return m;
  }, [filtered]);

  const hasAny = allResults.length > 0;
  const isRunning = status?.overall_status === "RUNNING" || status?.overall_status === "RETRYING";

  // When no results yet but running — show skeletons for group A
  const showSkeleton = !hasAny && isRunning;

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-card px-3 py-3 shadow-[var(--shadow-card)]">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجوی نماد (فملی، فولاد...)"
            className="w-full rounded-xl border border-line bg-soft py-2 pr-9 pl-3 text-[12px] font-medium text-ink placeholder:text-ink-3 focus:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-200"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-ink-3">
            <ArrowUpDown className="size-3.5" /> مرتب‌سازی
          </span>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="rounded-xl border border-line bg-soft px-3 py-2 text-[12px] font-bold text-ink-2"
          >
            <option value="armor">امتیاز زرهی ↓</option>
            <option value="dri">اعتبار داده (DRI) ↓</option>
            <option value="symbol">حروف الفبا</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-soft px-3 py-2 text-[11px] font-medium text-ink-2 cursor-pointer select-none">
            <input type="checkbox" checked={hideUnreliable} onChange={(e) => setHideUnreliable(e.target.checked)} className="size-3.5 accent-primary-700" />
            مخفی Unreliable
          </label>
          <label className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-soft px-3 py-2 text-[11px] font-medium text-ink-2 cursor-pointer select-none">
            <input type="checkbox" checked={hideStale} onChange={(e) => setHideStale(e.target.checked)} className="size-3.5 accent-primary-700" />
            مخفی STALE
          </label>
        </div>

        <span className="mr-auto hidden items-center gap-1 rounded-full bg-soft px-3 py-1.5 text-[11px] font-bold text-ink-3 sm:inline-flex">
          <Filter className="size-3.5" />
          {filtered.length} / {allResults.length}
        </span>
      </div>

      {/* Progressive groups */}
      {!hasAny && !showSkeleton ? (
        <EmptyState
          icon={Shield}
          title="هنوز محاسبه‌ای انجام نشده"
          hint="پس از شروع پردازش، ابتدا نتایج گروه A (نقدشونده‌ها) نمایش داده می‌شود و سپس گروه‌های B و C به‌صورت تدریجی اضافه می‌شوند."
        />
      ) : (
        <div className="space-y-4">
          {/* Group A always first */}
          <GroupSection group="A" results={byGroup.A} isVisible={visibleGroups.includes("A") || showSkeleton || byGroup.A.length > 0} sortKey={sortKey} />
          {/* Group B appears after A stabilizes — soft animation */}
          <GroupSection group="B" results={byGroup.B} isVisible={visibleGroups.includes("B") || byGroup.B.length > 0} sortKey={sortKey} />
          {/* Group C appears last */}
          <GroupSection group="C" results={byGroup.C} isVisible={visibleGroups.includes("C") || byGroup.C.length > 0} sortKey={sortKey} />

          {/* Empty filtered state */}
          {hasAny && filtered.length === 0 && (
            <EmptyState icon={Search} title="نتیجه‌ای یافت نشد" hint="فیلترها را تغییر دهید یا عبارت جستجو را پاک کنید." />
          )}
        </div>
      )}

      {/* Live hint */}
      {isRunning && hasAny && (
        <p className="text-center text-[11px] text-ink-3">
          نتایج به‌صورت زنده به‌روزرسانی می‌شوند — ابتدا گروه A سپس B و C به‌صورت نرم اضافه خواهند شد.
        </p>
      )}
    </div>
  );
}

export default ArmorDashboard;
