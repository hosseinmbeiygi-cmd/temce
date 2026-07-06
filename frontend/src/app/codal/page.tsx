"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AuditBadge } from "@/components/AuditBadge";
import { DonutChart } from "@/components/DonutChart";
import AppLayout from "@/components/layout/AppLayout";
import RahavardMarketingBanner from "@/components/RahavardMarketingBanner";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { formatDateShamsi, formatTime } from "@/lib/dates";
import Link from "next/link";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------

interface CodalAnnouncement {
  id: number;
  symbol: string;
  company_name: string;
  title: string;
  code: string;
  date_title: string;
  date_send: string;
  time_send: string;
  date_publish: string;
  time_publish: string;
  link: string;
  link_pdf: string;
  link_excel: string;
  link_attachment: string;
  audit_status: string;
  fetched_at: string;
  created_at: string;
}

interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function AnnouncementCard({ item }: { item: CodalAnnouncement }) {
  const hasPdf = !!item.link_pdf;
  const hasExcel = !!item.link_excel;
  const hasAttachment = !!item.link_attachment;

  return (
    <div className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {/* Symbol + Company + Audit Badge */}
          <div className="flex items-center gap-2 mb-1.5">
            <Link
              href={`/symbol/${item.symbol}`}
              className="text-xs font-bold bg-primary-600/15 text-primary-300 px-2 py-0.5 rounded-md hover:bg-primary-600/25 transition-colors"
            >
              {item.symbol || "—"}
            </Link>
            <span className="text-xs text-surface-400 truncate">
              {item.company_name || ""}
            </span>
            <AuditBadge status={item.audit_status} />
          </div>

          {/* Title */}
          <h3 className="text-sm font-medium text-surface-100 leading-relaxed line-clamp-2">
            {item.title || "بدون عنوان"}
          </h3>

          {/* Date + Time */}
          <div className="flex items-center gap-3 mt-2 text-xs text-surface-500">
            <span>📅 {formatDateShamsi(item.date_publish)}</span>
            {item.time_publish && <span>⏰ {formatTime(item.time_publish)}</span>}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1.5 shrink-0">
          {hasPdf && (
            <a
              href={item.link_pdf}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-accent-rose/10 text-accent-rose px-2.5 py-1 rounded-lg hover:bg-accent-rose/20 transition-colors text-center whitespace-nowrap"
            >
              📄 PDF
            </a>
          )}
          {hasExcel && (
            <a
              href={item.link_excel}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-accent-emerald/10 text-accent-emerald px-2.5 py-1 rounded-lg hover:bg-accent-emerald/20 transition-colors text-center whitespace-nowrap"
            >
              📊 Excel
            </a>
          )}
          {!hasPdf && !hasExcel && hasAttachment && (
            <a
              href={item.link_attachment}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-primary-600/10 text-primary-300 px-2.5 py-1 rounded-lg hover:bg-primary-600/20 transition-colors text-center whitespace-nowrap"
            >
              🔗 مشاهده
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function AnnouncementSkeleton() {
  return (
    <div className="glass-card p-4">
      <div className="flex gap-2 mb-2">
        <Skeleton className="h-5 w-16 rounded-md" />
        <Skeleton className="h-5 w-32 rounded-md" />
      </div>
      <Skeleton className="h-4 w-full mb-2 rounded" />
      <Skeleton className="h-4 w-3/4 rounded" />
      <div className="flex gap-3 mt-2">
        <Skeleton className="h-3 w-24 rounded" />
        <Skeleton className="h-3 w-16 rounded" />
      </div>
    </div>
  );
}

const CATEGORIES = [
  { value: "", label: "همه دسته‌بندی‌ها" },
  { value: "1", label: "صورت مالی سالانه" },
  { value: "2", label: "افشای اطلاعات بااهمیت" },
  { value: "3", label: "گزارش عملکرد ماهانه" },
  { value: "4", label: "اساسنامه/امیدنامه" },
  { value: "5", label: "هیئت مدیره و کمیته حسابرسی" },
  { value: "6", label: "دعوت به مجامع و تصمیمات" },
  { value: "7", label: "افزایش سرمایه" },
  { value: "8", label: "شفاف‌سازی بورس/فرابورس" },
  { value: "9", label: "شفاف‌سازی سازمان" },
  { value: "10", label: "سایر" },
  { value: "11", label: "اوراق بدهی" },
];

interface BrsApiSearchResult {
  count_announcement: number;
  count_page: number;
  announcements: CodalAnnouncement[];
}

export default function CodalPage() {
  const [searchSymbol, setSearchSymbol] = useState("");
  const [category, setCategory] = useState("");
  const [auditFilter, setAuditFilter] = useState("");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [page, setPage] = useState(1);

  const hasAdvancedFilters = category !== "" || dateStart !== "" || dateEnd !== "";

  // Build query params for the API call
  const queryKey = ["codal-announcements", searchSymbol, category, auditFilter, dateStart, dateEnd, page];

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: async () => {
      // When advanced filters or audit filter is active, use BrsApi proxy
      if (hasAdvancedFilters || auditFilter) {
        const params = new URLSearchParams();
        if (searchSymbol.trim()) params.set("symbol", searchSymbol.trim());
        if (category) params.set("category", category);
        if (auditFilter === "audited") { params.set("audited", "true"); params.set("unaudited", "false"); }
        else if (auditFilter === "unaudited") { params.set("audited", "false"); params.set("unaudited", "true"); }
        if (dateStart) params.set("date_start", dateStart);
        if (dateEnd) params.set("date_end", dateEnd);
        params.set("page", String(page));

        const res = await apiGet<{ success: boolean; data: BrsApiSearchResult }>(
          `/codal/brsapi-search?${params.toString()}`
        );
        if (!res?.success || !res?.data) {
          return { items: [], total: 0, page: 1, page_size: 50, total_pages: 0 };
        }
        const items = res.data.announcements ?? [];
        const total = res.data.count_announcement ?? items.length;
        const totalPages = Math.max(1, res.data.count_page ?? 1);
        return { items, total, page, page_size: items.length, total_pages: totalPages };
      }

      // Default: search local database
      const params = new URLSearchParams();
      if (searchSymbol.trim()) params.set("symbol", searchSymbol.trim());
      if (dateStart) params.set("date_start", dateStart);
      if (dateEnd) params.set("date_end", dateEnd);
      params.set("page", String(page));
      params.set("page_size", "50");

      const res = await apiGet<{ success: boolean; data: PaginatedResult<CodalAnnouncement> }>(
        `/codal/announcements?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0, page: 1, page_size: 50, total_pages: 0 };
    },
    placeholderData: (prev) => prev,
    refetchInterval: hasAdvancedFilters ? 60_000 : 120_000,
  });

  const announcements = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, data?.total_pages ?? 1);

  // Audit stats
  const auditedCount = data?.items ? data.items.filter((a: CodalAnnouncement) => a.audit_status === "audited").length : 0;
  const unauditedCount = data?.items ? data.items.filter((a: CodalAnnouncement) => a.audit_status === "unaudited").length : 0;
  const unknownCount = data?.items ? data.items.length - auditedCount - unauditedCount : 0;

  // Trigger search on Enter
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      setPage(1);
    }
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setCategory(e.target.value);
    setPage(1);
  };

  const handleAuditFilterChange = (value: string) => {
    setAuditFilter(auditFilter === value ? "" : value);
    setPage(1);
  };

  return (
    <AppLayout title="اطلاعیه‌های کدال" subtitle="جستجو و مشاهده اطلاعیه‌های شرکت‌های پذیرفته شده در بورس">
      <div className="max-w-5xl mx-auto space-y-5">

        {/* ------ Header --------------------------------------------------------------------------------------------------------- */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">اطلاعیه‌های کدال</h1>
            <p className="text-sm text-surface-500 mt-1">جستجو و مشاهده اطلاعیه‌های شرکت‌ها</p>
          </div>
          <Link
            href="/codal/import"
            className="text-sm bg-primary-600/15 text-primary-300 px-4 py-2 rounded-xl hover:bg-primary-600/25 transition-colors"
          >
            + ورود اطلاعات کدال
          </Link>
        </div>

        {/* Marketing Banner */}
        <RahavardMarketingBanner />

        {/* ------ Filters ------------------------------------------------------------------------------------------------------ */}
        <div className="glass-card p-4">
          <div className="flex flex-wrap items-end gap-3">
            {/* Symbol */}
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs text-surface-500 mb-1">نماد</label>
              <input
                type="text"
                value={searchSymbol}
                onChange={(e) => setSearchSymbol(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="مثال: فولاد"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500"
              />
            </div>

            {/* Category */}
            <div className="min-w-[160px]">
              <label className="block text-xs text-surface-500 mb-1">دسته‌بندی</label>
              <select
                value={category}
                onChange={handleCategoryChange}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500 appearance-none cursor-pointer"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>{cat.label}</option>
                ))}
              </select>
            </div>

            {/* Audit Filter */}
            <div className="flex flex-col gap-1">
              <label className="block text-xs text-surface-500 mb-1">وضعیت حسابرسی</label>
              <div className="flex gap-1">
                <button
                  onClick={() => handleAuditFilterChange("audited")}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    auditFilter === "audited"
                      ? "bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30"
                      : "bg-surface-800 text-surface-400 border border-surface-700 hover:text-surface-200"
                  }`}
                >
                  ✓ حسابرسی شده
                </button>
                <button
                  onClick={() => handleAuditFilterChange("unaudited")}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    auditFilter === "unaudited"
                      ? "bg-accent-amber/20 text-accent-amber border border-accent-amber/30"
                      : "bg-surface-800 text-surface-400 border border-surface-700 hover:text-surface-200"
                  }`}
                >
                  ! حسابرسی نشده
                </button>
              </div>
            </div>

            {/* Date Start */}
            <div className="min-w-[130px]">
              <label className="block text-xs text-surface-500 mb-1">از تاریخ</label>
              <input
                type="text"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="۱۴۰۳-۰۱-۰۱"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
              />
            </div>

            {/* Date End */}
            <div className="min-w-[130px]">
              <label className="block text-xs text-surface-500 mb-1">تا تاریخ</label>
              <input
                type="text"
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="۱۴۰۳-۱۲-۲۹"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
              />
            </div>

            {/* Search button */}
            <button
              onClick={() => setPage(1)}
              className="bg-primary-600 hover:bg-primary-500 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              🔍 جستجو
            </button>

            {/* Loading indicator */}
            {isLoading && (
              <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />
            )}
          </div>

          {/* Result count */}
          {!isLoading && total > 0 && (
            <div className="mt-3 text-xs text-surface-500">
              {total.toLocaleString()} اطلاعیه یافت شد
              {searchSymbol && ` برای نماد "${searchSymbol}"`}
            </div>
          )}
        </div>

        {/* ------ Audit Stats Donut ------------------------------------------------------------------ */}
        {!isLoading && announcements.length > 0 && (
          <div className="glass-card p-4">
            <DonutChart
              slices={[
                { label: "حسابرسی شده", value: auditedCount, color: "#22c55e" },
                { label: "حسابرسی نشده", value: unauditedCount, color: "#f59e0b" },
                ...(unknownCount > 0
                  ? [{ label: "نامشخص", value: unknownCount, color: "#6b7280" }]
                  : []
                ),
              ]}
              centerLabel="اطلاعیه"
            />
          </div>
        )}

        {/* ------ Results ------------------------------------------------------------------------------------------------------ */}
        {isLoading && announcements.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <AnnouncementSkeleton key={i} />
            ))}
          </div>
        ) : announcements.length > 0 ? (
          <>
            <div className="space-y-3">
              {announcements.map((item, i) => (
                <AnnouncementCard key={item.id ?? i} item={item} />
              ))}
            </div>

            {/* ------ Pagination --------------------------------------------------------------------------------- */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 py-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  ← قبلی
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        page === pageNum
                          ? "bg-primary-600 text-white"
                          : "bg-surface-800 text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                {totalPages > 7 && <span className="text-surface-500 text-xs">...</span>}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  بعدی →
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">هیچ اطلاعیه‌ای یافت نشد</p>
            <p className="text-sm mt-1">فیلترهای جستجو را تغییر دهید یا بعداً مراجعه کنید</p>
          </div>
        )}

        {/* ------ Quick Links ------------------------------------------------------------------------------------------ */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/instruments" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← همه نمادها
          </Link>
          <Link href="/symbol/فولاد" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            نماد فولاد
          </Link>
          <Link href="/analysis" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            تحلیل بازار
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}
