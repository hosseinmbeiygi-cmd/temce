"use client";

import { use, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { notFound } from "next/navigation";
import AppLayout from "@/components/layout/AppLayout";
import { AuditBadge } from "@/components/AuditBadge";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import { formatDateShamsi, formatTime } from "@/lib/dates";

// ------ Types ----------------------------------------------------------------------------------------------------------

interface CodalAttachment {
  id: number;
  announcement_id: number;
  symbol: string | null;
  code: string | null;
  attachment_type: string;
  source_url: string;
  storage_type: string;
  status: string;
  file_size: number | null;
  mime_type: string | null;
  storage_path: string | null;
  downloaded_at: string | null;
  created_at: string;
}

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
  summary: string;
  fetched_at: string;
  created_at: string;
}

// ------ Helpers --------------------------------------------------------------------------------------------------------

function formatFileSize(bytes: number | null): string {
  if (!bytes || bytes === 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getAttachmentIcon(type: string): string {
  switch (type) {
    case "pdf": return "📄";
    case "excel": return "📊";
    case "html": return "🌐";
    case "attachment": return "📎";
    default: return "📁";
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "done": return <span className="text-[10px] bg-accent-emerald/15 text-accent-emerald px-1.5 py-0.5 rounded-full">✓ دانلود شده</span>;
    case "downloading": return <span className="text-[10px] bg-accent-amber/15 text-accent-amber px-1.5 py-0.5 rounded-full animate-pulse">⏳ در حال دانلود</span>;
    case "pending": return <span className="text-[10px] bg-surface-600/30 text-surface-400 px-1.5 py-0.5 rounded-full">⏳ در انتظار</span>;
    case "error": return <span className="text-[10px] bg-accent-rose/15 text-accent-rose px-1.5 py-0.5 rounded-full">❌ خطا</span>;
    default: return <span className="text-[10px] bg-surface-600/30 text-surface-400 px-1.5 py-0.5 rounded-full">{status}</span>;
  }
}

// ------ Detail Page ----------------------------------------------------------------------------------------------------

export default function CodalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  // Derive whether id is numeric (announcement_id) or a symbol string
  const isNumericId = !isNaN(Number(id));

  // Fetch announcement details from brsapi-search (local DB)
  const { data: announcement, isLoading, error } = useQuery({
    queryKey: ["codal-detail", id],
    queryFn: async () => {
      if (isNumericId) {
        // Numeric ID: use brsapi-search with all announcements and find by code/id
        // First try: direct search with symbol=id as fallback
        const res = await apiGet<{ success: boolean; data: { count_announcement: number; announcement: CodalAnnouncement[] } }>(
          `/codal/brsapi-search?page=1`
        );
        const items = res?.data?.announcement;
        if (items) {
          // Find by exact ID match (code field often matches id)
          const matched = items.find((a: CodalAnnouncement) => String(a.id) === id || a.code === id);
          if (matched) return matched;
        }
        // Fallback: try announcements endpoint with page_size=200 and find by code
        const res2 = await apiGet<{ success: boolean; data: { items: CodalAnnouncement[]; total: number } }>(
          `/codal/announcements?page=1&page_size=200`
        );
        const items2 = res2?.data?.items;
        if (items2) {
          const matched = items2.find((a: CodalAnnouncement) => String(a.id) === id || a.code === id);
          if (matched) return matched;
        }
      } else {
        // Symbol string: search by symbol
        const res = await apiGet<{ success: boolean; data: { items: CodalAnnouncement[] } }>(
          `/codal/announcements?page=1&page_size=1&symbol=${encodeURIComponent(id)}`
        );
        const items = res?.data?.items;
        if (items && items.length > 0) return items[0];

        // Fallback: brsapi-search by symbol
        const res2 = await apiGet<{ success: boolean; data: { count_announcement: number; announcement: CodalAnnouncement[] } }>(
          `/codal/brsapi-search?symbol=${encodeURIComponent(id)}&page=1`
        );
        const items2 = res2?.data?.announcement;
        if (items2 && items2.length > 0) return items2[0];
      }

      return null;
    },
  });

  // Fetch attachments for this announcement
  const { data: attachments } = useQuery({
    queryKey: ["codal-attachments", id],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: CodalAttachment[] }>(
        `/codal/announcements/${id}/attachments`
      );
      return res?.data ?? [];
    },
    enabled: !!id && !isNaN(Number(id)),
  });

  // Derive audit status from title if not directly available
  const auditStatus = useMemo(() => {
    if (announcement?.audit_status) return announcement.audit_status;
    const title = announcement?.title || "";
    if (title.includes("حسابرسی شده") || title.includes("حسابرسی‌شده") || title.includes("audited")) return "audited";
    if (title.includes("حسابرسی نشده") || title.includes("unaudited")) return "unaudited";
    return "";
  }, [announcement]);

  // ------ Loading state -----------------------------------------------------------------------------------------------
  if (isLoading) {
    return (
      <AppLayout title="اطلاعیه کدال" subtitle="در حال بارگذاری...">
        <div className="max-w-4xl mx-auto space-y-4">
          <Skeleton className="h-8 w-48 rounded-lg" />
          <Skeleton className="h-6 w-64 rounded-lg" />
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      </AppLayout>
    );
  }

  // ------ Error / Not Found -------------------------------------------------------------------------------------------
  if (error || !announcement) {
    notFound();
  }

  // ------ Render -----------------------------------------------------------------------------------------------------
  return (
    <AppLayout
      title={`${announcement.symbol || ""} — اطلاعیه کدال`}
      subtitle={announcement.title || "جزئیات اطلاعیه"}
    >
      <div className="max-w-4xl mx-auto space-y-5">

        {/* Back button */}
        <Link
          href="/codal"
          className="inline-flex items-center gap-1 text-sm text-surface-400 hover:text-surface-200 transition-colors"
        >
          → بازگشت به لیست اطلاعیه‌ها
        </Link>

        {/* ------ Main Card -------------------------------------------------------------------------------------------- */}
        <div className="glass-card p-6 space-y-5">
          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Link
                  href={`/symbol/${encodeURIComponent(announcement.symbol)}`}
                  className="text-sm font-bold bg-primary-600/15 text-primary-300 px-2.5 py-1 rounded-md hover:bg-primary-600/25 transition-colors"
                >
                  {announcement.symbol || "—"}
                </Link>
                <span className="text-sm text-surface-400 truncate">
                  {announcement.company_name || ""}
                </span>
                <AuditBadge status={auditStatus} />
              </div>
              <h1 className="text-xl font-bold text-surface-100 leading-relaxed">
                {announcement.title || "بدون عنوان"}
              </h1>
            </div>
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-surface-800/50 rounded-xl p-3">
              <p className="text-[10px] text-surface-500 mb-1">تاریخ انتشار</p>
              <p className="text-sm font-semibold text-surface-200 font-mono">
                {formatDateShamsi(announcement.date_publish)}
              </p>
            </div>
            <div className="bg-surface-800/50 rounded-xl p-3">
              <p className="text-[10px] text-surface-500 mb-1">ساعت انتشار</p>
              <p className="text-sm font-semibold text-surface-200 font-mono">
                {announcement.time_publish ? formatTime(announcement.time_publish) : "—"}
              </p>
            </div>
            <div className="bg-surface-800/50 rounded-xl p-3">
              <p className="text-[10px] text-surface-500 mb-1">کد پیگیری</p>
              <p className="text-sm font-semibold text-surface-200 font-mono" dir="ltr">
                {announcement.code || "—"}
              </p>
            </div>
            <div className="bg-surface-800/50 rounded-xl p-3">
              <p className="text-[10px] text-surface-500 mb-1">وضعیت حسابرسی</p>
              <p className="text-sm font-semibold">
                {auditStatus === "audited"
                  ? <span className="text-accent-emerald">✓ حسابرسی شده</span>
                  : auditStatus === "unaudited"
                    ? <span className="text-accent-amber">! حسابرسی نشده</span>
                    : <span className="text-surface-400">نامشخص</span>
                }
              </p>
            </div>
          </div>

          {/* Summary */}
          {announcement.summary && (
            <div className="bg-surface-800/30 rounded-xl p-4">
              <p className="text-[11px] text-surface-500 mb-2">خلاصه اطلاعیه</p>
              <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                {announcement.summary}
              </p>
            </div>
          )}
        </div>

        {/* ------ Download Links --------------------------------------------------------------------------------------- */}
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-surface-100">📥 فایل‌های قابل دانلود</h2>

          {(announcement.link_pdf || announcement.link_excel || announcement.link_attachment) ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {announcement.link_pdf && (
                <a
                  href={announcement.link_pdf.startsWith("http") ? announcement.link_pdf : `https://api.brsapi.ir${announcement.link_pdf}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 bg-surface-800/50 hover:bg-surface-800 rounded-xl p-4 transition-colors group"
                >
                  <span className="text-2xl group-hover:scale-110 transition-transform">📄</span>
                  <div>
                    <p className="text-sm font-medium text-surface-200">PDF</p>
                    <p className="text-[10px] text-surface-500">گزارش اصلی</p>
                  </div>
                </a>
              )}
              {announcement.link_excel && (
                <a
                  href={announcement.link_excel.startsWith("http") ? announcement.link_excel : `https://api.brsapi.ir${announcement.link_excel}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 bg-surface-800/50 hover:bg-surface-800 rounded-xl p-4 transition-colors group"
                >
                  <span className="text-2xl group-hover:scale-110 transition-transform">📊</span>
                  <div>
                    <p className="text-sm font-medium text-surface-200">Excel</p>
                    <p className="text-[10px] text-surface-500">داده‌های مالی</p>
                  </div>
                </a>
              )}
              {announcement.link_attachment && (
                <a
                  href={announcement.link_attachment.startsWith("http") ? announcement.link_attachment : `https://api.brsapi.ir${announcement.link_attachment}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 bg-surface-800/50 hover:bg-surface-800 rounded-xl p-4 transition-colors group"
                >
                  <span className="text-2xl group-hover:scale-110 transition-transform">📎</span>
                  <div>
                    <p className="text-sm font-medium text-surface-200">پیوست</p>
                    <p className="text-[10px] text-surface-500">فایل ضمیمه</p>
                  </div>
                </a>
              )}
            </div>
          ) : (
            <p className="text-sm text-surface-500 text-center py-4">هیچ فایل قابل دانلودی برای این اطلاعیه موجود نیست</p>
          )}

          {/* Note about download */}
          <p className="text-[10px] text-surface-600 text-center">
            {announcement.link_pdf || announcement.link_excel || announcement.link_attachment
              ? "💡 لینک‌های دانلود از سامانه کدال (codal.ir) — در صورت نیاز از فیلترشکن استفاده کنید"
              : "ℹ️ پس از همگام‌سازی داده‌ها از BrsApi، لینک‌های دانلود در دسترس خواهند بود"}
          </p>
        </div>

        {/* ------ Processed Attachments (from CodalAttachmentDownloadService) ------------------------------------------ */}
        {attachments && attachments.length > 0 && (
          <div className="glass-card p-6 space-y-4">
            <h2 className="text-lg font-semibold text-surface-100">📦 پیوست‌های پردازش‌شده</h2>
            <div className="overflow-hidden rounded-xl border border-surface-700/50">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-surface-800/80 text-surface-500">
                    <th className="py-2.5 px-3 text-right font-medium">نوع</th>
                    <th className="py-2.5 px-3 text-right font-medium">نام فایل</th>
                    <th className="py-2.5 px-3 text-right font-medium">وضعیت</th>
                    <th className="py-2.5 px-3 text-right font-medium">اندازه</th>
                    <th className="py-2.5 px-3 text-right font-medium">تاریخ دانلود</th>
                  </tr>
                </thead>
                <tbody>
                  {attachments.map((att) => (
                    <tr key={att.id} className="border-t border-surface-700/50 hover:bg-surface-800/30 transition-colors">
                      <td className="py-2.5 px-3">
                        <span className="flex items-center gap-1.5">
                          {getAttachmentIcon(att.attachment_type)}
                          <span className="text-surface-300 font-medium uppercase">{att.attachment_type}</span>
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="text-surface-400 font-mono text-[10px]">
                          {att.storage_path ? att.storage_path.split("/").pop() : (att.source_url?.split("/").pop() || "—")}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">{getStatusBadge(att.status)}</td>
                      <td className="py-2.5 px-3 text-surface-400 font-mono">{formatFileSize(att.file_size)}</td>
                      <td className="py-2.5 px-3 text-surface-400">
                        {att.downloaded_at ? formatDateShamsi(att.downloaded_at) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ------ Raw Announcement Data (expandable technical details) ------------------------------------------------- */}
        <details className="glass-card p-4">
          <summary className="cursor-pointer text-sm font-medium text-surface-400 hover:text-surface-200 transition-colors">
            🔧 اطلاعات فنی (JSON خام)
          </summary>
          <pre className="mt-3 text-[10px] text-surface-500 font-mono overflow-auto max-h-80 bg-surface-900/50 rounded-lg p-4" dir="ltr">
            {JSON.stringify(announcement, null, 2)}
          </pre>
        </details>

        {/* Quick links */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href={`/symbol/${encodeURIComponent(announcement.symbol)}`} className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← تحلیل نماد {announcement.symbol}
          </Link>
          <Link href="/codal" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            ← لیست اطلاعیه‌ها
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}
