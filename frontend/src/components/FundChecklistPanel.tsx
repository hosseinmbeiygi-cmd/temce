"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Filter, Search, SlidersHorizontal } from "lucide-react";
import { Card } from "@/components/ui/Card";
import {
  FUND_CHECKLIST_AREA_ORDER,
  type FundChecklistFundLike,
  type FundChecklistSymbolDetailLike,
} from "@/lib/fund-checklist-real";
import {
  buildFundChecklistRows,
  summarizeFundChecklistAreas,
  summarizeFundChecklistRows,
  type FundChecklistRowView,
} from "@/lib/fund-checklist-real";

type SortKey = "score_desc" | "score_asc" | "index" | "area" | "importance" | "cadence" | "availability";

const IMPORTANCE_ORDER: Record<string, number> = {
  حیاتی: 3,
  بالا: 2,
  متوسط: 1,
};

const AVAILABILITY_ORDER: Record<FundChecklistRowView["availability"], number> = {
  available: 3,
  partial: 2,
  missing: 1,
};

function badgeClass(score: number): string {
  if (score >= 80) return "bg-accent-emerald/15 text-accent-emerald";
  if (score >= 60) return "bg-primary-600/15 text-primary-300";
  if (score >= 40) return "bg-accent-amber/15 text-accent-amber";
  return "bg-accent-rose/15 text-accent-rose";
}

function importanceClass(label: string): string {
  switch (label) {
    case "حیاتی":
      return "bg-accent-rose/15 text-accent-rose";
    case "بالا":
      return "bg-accent-amber/15 text-accent-amber";
    default:
      return "bg-primary-600/15 text-primary-300";
  }
}

function statusClass(label: string): string {
  switch (label) {
    case "بررسی‌شده":
      return "bg-accent-emerald/15 text-accent-emerald";
    case "آماده بررسی":
      return "bg-primary-600/15 text-primary-300";
    case "آماده تکمیل":
      return "bg-surface-700/60 text-surface-300";
    default:
      return "bg-surface-700/60 text-surface-400";
  }
}

function cadenceClass(label: string): string {
  if (label.includes("لحظه")) return "bg-accent-emerald/15 text-accent-emerald";
  if (label.includes("روز")) return "bg-primary-600/15 text-primary-300";
  if (label.includes("هفته")) return "bg-accent-amber/15 text-accent-amber";
  return "bg-surface-700/60 text-surface-400";
}

function availabilityClass(label: FundChecklistRowView["availability"]): string {
  switch (label) {
    case "available":
      return "bg-accent-emerald/15 text-accent-emerald";
    case "partial":
      return "bg-accent-amber/15 text-accent-amber";
    default:
      return "bg-accent-rose/15 text-accent-rose";
  }
}

function availabilityLabel(label: FundChecklistRowView["availability"]): string {
  switch (label) {
    case "available":
      return "واقعی";
    case "partial":
      return "نیمه‌واقعی";
    default:
      return "ناموجود";
  }
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-700/40 bg-surface-900/40 px-3 py-2">
      <p className="text-[9px] text-surface-500">{label}</p>
      <p className="mt-1 text-[10px] leading-4 text-surface-300 break-words">{value || "—"}</p>
    </div>
  );
}

function ChecklistRow({ row }: { row: FundChecklistRowView }) {
  return (
    <div className="rounded-xl border border-surface-700/40 bg-surface-900/30 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-surface-800 px-2 py-0.5 font-mono text-[9px] text-surface-400">{row.item.code}</span>
            <span className="font-medium text-surface-100">{row.item.title}</span>
          </div>
          <p className="mt-1 text-[11px] leading-5 text-surface-500 break-words">{row.item.description}</p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
            <span className={`rounded-full px-2 py-0.5 font-bold ${importanceClass(row.importanceLabel)}`}>{row.importanceLabel}</span>
            <span className={`rounded-full px-2 py-0.5 font-bold ${statusClass(row.statusLabel)}`}>{row.statusLabel}</span>
            <span className={`rounded-full px-2 py-0.5 font-bold ${cadenceClass(row.item.cadence)}`}>{row.item.cadence || "—"}</span>
            <span className={`rounded-full px-2 py-0.5 font-bold ${availabilityClass(row.availability)}`}>{availabilityLabel(row.availability)}</span>
            <span className={`rounded-full px-2 py-0.5 font-bold ${badgeClass(row.score)}`}>{row.score}%</span>
            <span className="rounded-full bg-surface-800 px-2 py-0.5 font-mono text-[9px] text-surface-400">{row.confidence}%</span>
          </div>
        </div>
        <div className="min-w-[140px] text-left">
          <p className="text-[9px] text-surface-500">حوزه</p>
          <p className="text-[10px] font-medium text-surface-200 break-words">{row.item.subarea || "—"}</p>
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <MetaLine label="داده واقعی" value={row.realValue} />
        <MetaLine label="منبع" value={row.realSource} />
        <MetaLine label="نکته" value={row.realNote} />
        <MetaLine label="فرمول / روش" value={row.item.formula} />
      </div>
    </div>
  );
}

interface FundChecklistPanelProps {
  fund: FundChecklistFundLike;
  symbolDetail?: FundChecklistSymbolDetailLike | null;
}

export default function FundChecklistPanel({ fund, symbolDetail }: FundChecklistPanelProps) {
  const [query, setQuery] = useState("");
  const [areaFilter, setAreaFilter] = useState("all");
  const [importanceFilter, setImportanceFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [availabilityFilter, setAvailabilityFilter] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("score_desc");
  const [expandedAreas, setExpandedAreas] = useState<Set<string>>(() => new Set(FUND_CHECKLIST_AREA_ORDER));

  const allRows = useMemo(() => buildFundChecklistRows(fund, symbolDetail), [fund, symbolDetail]);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = allRows.filter((row) => {
      if (areaFilter !== "all" && row.item.area !== areaFilter) return false;
      if (importanceFilter !== "all" && row.importanceLabel !== importanceFilter) return false;
      if (statusFilter !== "all" && row.statusLabel !== statusFilter) return false;
      if (availabilityFilter !== "all" && row.availability !== availabilityFilter) return false;
      if (!q) return true;
      return [
        row.item.code,
        row.item.area,
        row.item.subarea,
        row.item.title,
        row.item.description,
        row.item.formula,
        row.item.analysis_note,
        row.item.source,
        row.item.cadence,
        row.importanceLabel,
        row.statusLabel,
        row.realValue,
        row.realSource,
        row.realNote,
        availabilityLabel(row.availability),
      ]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });

    const sorted = [...list].sort((a, b) => {
      switch (sortBy) {
        case "score_asc":
          return a.score - b.score;
        case "index":
          return a.item.index - b.item.index;
        case "area":
          return a.item.area.localeCompare(b.item.area, "fa");
        case "importance":
          return (IMPORTANCE_ORDER[b.importanceLabel] ?? 0) - (IMPORTANCE_ORDER[a.importanceLabel] ?? 0);
        case "cadence":
          return a.item.cadence.localeCompare(b.item.cadence, "fa");
        case "availability":
          return (AVAILABILITY_ORDER[b.availability] ?? 0) - (AVAILABILITY_ORDER[a.availability] ?? 0);
        default:
          return b.score - a.score;
      }
    });

    return sorted;
  }, [areaFilter, availabilityFilter, importanceFilter, query, allRows, sortBy, statusFilter]);

  const summary = useMemo(() => summarizeFundChecklistRows(filteredRows), [filteredRows]);
  const areaSummaries = useMemo(() => summarizeFundChecklistAreas(filteredRows), [filteredRows]);

  const areaItems = useMemo(() => {
    const map = new Map<string, FundChecklistRowView[]>();
    for (const row of filteredRows) {
      if (!map.has(row.item.area)) map.set(row.item.area, []);
      map.get(row.item.area)!.push(row);
    }

    return FUND_CHECKLIST_AREA_ORDER.map((area) => ({
      area,
      items: map.get(area) ?? [],
    })).filter((group) => group.items.length > 0);
  }, [filteredRows]);

  const allExpanded = areaItems.length > 0 && areaItems.every((group) => expandedAreas.has(group.area));

  const toggleArea = (area: string) => {
    setExpandedAreas((prev) => {
      const next = new Set(prev);
      if (next.has(area)) next.delete(area);
      else next.add(area);
      return next;
    });
  };

  const toggleAll = () => {
    if (allExpanded) {
      setExpandedAreas(new Set());
      return;
    }
    setExpandedAreas(new Set(areaItems.map((group) => group.area)));
  };

  return (
    <Card
      title="چک‌لیست 300 شاخص"
      subtitle="ستون‌های workbook با داده واقعی صندوق و نماد"
      actions={
        <button
          type="button"
          onClick={toggleAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-surface-700 bg-surface-800 px-3 py-1.5 text-xs font-medium text-surface-200 transition-colors hover:bg-surface-700"
        >
          {allExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {allExpanded ? "جمع کردن" : "باز کردن"}
        </button>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-3 xl:grid-cols-[minmax(220px,1.4fr)_repeat(5,minmax(0,1fr))]">
          <div className="relative">
            <Search className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جستجو در کد، عنوان، منبع، داده واقعی..."
              className="w-full rounded-xl border border-surface-700 bg-surface-800/70 py-2.5 pr-9 pl-3 text-sm text-surface-100 outline-none transition-colors placeholder:text-surface-600 focus:border-primary-500"
            />
          </div>

          <select
            value={areaFilter}
            onChange={(e) => setAreaFilter(e.target.value)}
            className="rounded-xl border border-surface-700 bg-surface-800/70 px-3 py-2.5 text-sm text-surface-200 outline-none focus:border-primary-500"
          >
            <option value="all">همه حوزه‌ها</option>
            {FUND_CHECKLIST_AREA_ORDER.map((area) => (
              <option key={area} value={area}>
                {area}
              </option>
            ))}
          </select>

          <select
            value={importanceFilter}
            onChange={(e) => setImportanceFilter(e.target.value)}
            className="rounded-xl border border-surface-700 bg-surface-800/70 px-3 py-2.5 text-sm text-surface-200 outline-none focus:border-primary-500"
          >
            <option value="all">همه سطوح اهمیت</option>
            <option value="حیاتی">حیاتی</option>
            <option value="بالا">بالا</option>
            <option value="متوسط">متوسط</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-surface-700 bg-surface-800/70 px-3 py-2.5 text-sm text-surface-200 outline-none focus:border-primary-500"
          >
            <option value="all">همه وضعیت‌ها</option>
            <option value="آماده تکمیل">آماده تکمیل</option>
            <option value="آماده بررسی">آماده بررسی</option>
            <option value="بررسی‌شده">بررسی‌شده</option>
            <option value="نامشخص">نامشخص</option>
          </select>

          <select
            value={availabilityFilter}
            onChange={(e) => setAvailabilityFilter(e.target.value)}
            className="rounded-xl border border-surface-700 bg-surface-800/70 px-3 py-2.5 text-sm text-surface-200 outline-none focus:border-primary-500"
          >
            <option value="all">همه پوشش‌ها</option>
            <option value="available">واقعی</option>
            <option value="partial">نیمه‌واقعی</option>
            <option value="missing">ناموجود</option>
          </select>

          <button
            type="button"
            onClick={() => {
              setQuery("");
              setAreaFilter("all");
              setImportanceFilter("all");
              setStatusFilter("all");
              setAvailabilityFilter("all");
              setSortBy("score_desc");
            }}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-surface-700 bg-surface-800/70 px-3 py-2.5 text-sm text-surface-300 transition-colors hover:bg-surface-700"
          >
            <SlidersHorizontal className="h-4 w-4" />
            بازنشانی
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center gap-2 rounded-lg border border-surface-700 bg-surface-800/60 px-3 py-1.5 text-xs text-surface-300">
            <Filter className="h-3.5 w-3.5 text-surface-500" />
            {filteredRows.length} / {allRows.length}
          </div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortKey)}
            className="rounded-lg border border-surface-700 bg-surface-800/70 px-3 py-1.5 text-xs text-surface-200 outline-none focus:border-primary-500"
          >
            <option value="score_desc">امتیاز نزولی</option>
            <option value="score_asc">امتیاز صعودی</option>
            <option value="index">شماره</option>
            <option value="area">حوزه</option>
            <option value="importance">اهمیت</option>
            <option value="cadence">تناوب</option>
            <option value="availability">پوشش واقعی</option>
          </select>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-surface-700/40 bg-surface-900/40 p-3">
            <p className="text-[10px] text-surface-500">نمایش / کل</p>
            <p className="mt-1 text-xl font-black text-surface-100">{summary.totalItems}</p>
            <p className="text-[10px] text-surface-500">از {allRows.length} شاخص</p>
          </div>
          <div className="rounded-xl border border-surface-700/40 bg-surface-900/40 p-3">
            <p className="text-[10px] text-surface-500">میانگین امتیاز</p>
            <p className="mt-1 text-xl font-black text-primary-300">{summary.averageScore}%</p>
            <p className="text-[10px] text-surface-500">امتیاز ترکیبی ساختار و داده واقعی</p>
          </div>
          <div className="rounded-xl border border-surface-700/40 bg-surface-900/40 p-3">
            <p className="text-[10px] text-surface-500">واقعی / نیمه / ناموجود</p>
            <p className="mt-1 text-xl font-black text-surface-100">
              {summary.availableCount} / {summary.partialCount} / {summary.missingCount}
            </p>
            <p className="text-[10px] text-surface-500">پوشش داده واقعی صندوق</p>
          </div>
          <div className="rounded-xl border border-surface-700/40 bg-surface-900/40 p-3">
            <p className="text-[10px] text-surface-500">حوزه‌های فعال</p>
            <p className="mt-1 text-xl font-black text-surface-100">{areaSummaries.length}</p>
            <p className="text-[10px] text-surface-500">از {FUND_CHECKLIST_AREA_ORDER.length} حوزه تعریف‌شده</p>
          </div>
        </div>

        <div className="rounded-xl border border-surface-700/40 bg-surface-900/30 p-3 text-[10px] text-surface-500">
          امتیاز هر ردیف = 35٪ ساختار workbook + 65٪ پوشش داده واقعی. برای ستون‌هایی که منبع مستقیم ندارند، مقدار با «ناموجود» ثبت می‌شود.
        </div>

        <div className="space-y-3">
          {areaItems.length === 0 ? (
            <div className="rounded-xl border border-surface-700/40 bg-surface-900/30 p-6 text-center text-surface-500">
              هیچ شاخصی با فیلترهای فعلی پیدا نشد.
            </div>
          ) : (
            areaItems.map(({ area, items }) => {
              const areaSummary = areaSummaries.find((entry) => entry.area === area);
              const expanded = expandedAreas.has(area);
              return (
                <section key={area} className="rounded-2xl border border-surface-700/50 bg-surface-900/25">
                  <button
                    type="button"
                    onClick={() => toggleArea(area)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-right"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-surface-100">{area}</span>
                        <span className="rounded-full bg-surface-800 px-2 py-0.5 text-[9px] font-mono text-surface-400">{items.length}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-surface-500">
                        <span>میانگین {areaSummary?.averageScore ?? 0}%</span>
                        <span>واقعی {areaSummary?.availableCount ?? 0}</span>
                        <span>نیمه‌واقعی {areaSummary?.partialCount ?? 0}</span>
                        <span>ناموجود {areaSummary?.missingCount ?? 0}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                          (areaSummary?.averageScore ?? 0) >= 80
                            ? "bg-accent-emerald/15 text-accent-emerald"
                            : (areaSummary?.averageScore ?? 0) >= 60
                              ? "bg-primary-600/15 text-primary-300"
                              : (areaSummary?.averageScore ?? 0) >= 40
                                ? "bg-accent-amber/15 text-accent-amber"
                                : "bg-accent-rose/15 text-accent-rose"
                        }`}
                      >
                        {areaSummary?.averageScore ?? 0}%
                      </span>
                      {expanded ? <ChevronUp className="h-4 w-4 text-surface-500" /> : <ChevronDown className="h-4 w-4 text-surface-500" />}
                    </div>
                  </button>

                  {expanded && (
                    <div className="space-y-2 border-t border-surface-800/70 p-3">
                      {items.map((row) => (
                        <ChecklistRow key={row.item.code} row={row} />
                      ))}
                    </div>
                  )}
                </section>
              );
            })
          )}
        </div>
      </div>
    </Card>
  );
}

