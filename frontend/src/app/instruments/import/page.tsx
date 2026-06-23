"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import AppLayout from "@/components/layout/AppLayout";
import FileUpload, { type FileUploadResult } from "@/components/ui/FileUpload";
import { useFileUpload } from "@/hooks/useFileUpload";

interface ImportResponse {
  filename: string;
  total_rows: number;
  imported: number;
  parse_errors: string[];
  import_errors: string[];
}

const SCHEMA_HINTS = [
  { name: "symbol", required: true, example: "فولاد" },
  { name: "name", required: false, example: "فولاد مبارکه اصفهان" },
  { name: "isin", required: false, example: "IRO1FOLD0001" },
  { name: "market_type", required: false, example: "bours | farabours | payeh" },
  { name: "sector_code", required: false, example: "27" },
  { name: "group_code", required: false, example: "27" },
  { name: "tick_size", required: false, example: "1" },
  { name: "lot_size", required: false, example: "1" },
  { name: "par_value", required: false, example: "1000" },
];

export default function ImportInstrumentsPage() {
  const queryClient = useQueryClient();
  const { upload, reset } = useFileUpload<ImportResponse>({
    path: "/instruments/import",
    fieldName: "file",
    onSuccess: async (res) => {
      toast.success(`${res.imported} نماد از ${res.total_rows} ردیف با موفقیت اضافه شد`);
      await queryClient.invalidateQueries({ queryKey: ["instruments"] });
    },
  });

  /**
   * Thin adapter so the reusable <FileUpload /> component can drive the hook.
   * Any error thrown by ``upload`` propagates straight to <FileUpload />, which
   * already shows the underlying server message (HTTP 500 trace, validation
   * error, missing column, …) inside its red banner. We intentionally do NOT
   * catch & re-throw a hardcoded string here — that would mask the real cause.
   */
  async function handleUpload(
    incoming: File,
    onProgress: (loaded: number, total: number) => void,
  ): Promise<FileUploadResult> {
    return (await upload(incoming, { onProgress })) as FileUploadResult;
  }

  return (
    <AppLayout
      title="ورود اطلاعات نمادها"
      subtitle="بارگذاری فایل CSV، JSON یا Excel — حداکثر ۱۰ مگابایت"
    >
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <Link
            href="/instruments"
            data-testid="instruments-back-link"
            className="text-sm text-surface-400 hover:text-surface-200 transition-colors"
          >
            ← بازگشت به لیست نمادها
          </Link>

          <span
            className="text-xs text-surface-500"
            title="پاسخ API به‌صورت JSON برمی‌گردد؛ این صرفاً نمایش مسیر است."
          >
            مسیر API: <span className="font-mono">POST /api/v1/instruments/import</span>
          </span>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-5 pb-5 border-b border-surface-800">
            <div className="flex items-center gap-2 text-xs text-surface-400">
              <span aria-hidden>💡</span>
              <span>اولین بار است؟ یک نمونه ۳ ردیفی دانلود کنید و ویرایشش کنید.</span>
            </div>
            <a
              href="/api/v1/instruments/sample"
              download="instruments-sample.csv"
              data-testid="download-sample-template"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-surface-800 hover:bg-surface-700 text-surface-200 border border-surface-700 hover:border-primary-500 rounded-lg text-xs font-medium transition-colors"
            >
              <span aria-hidden>⬇️</span>
              دانلود نمونه CSV
            </a>
          </div>
          <FileUpload
            accept=".csv,.json,.xlsx"
            maxSize={10 * 1024 * 1024}
            title="برای انتخاب فایل کلیک کنید یا آن را اینجا رها کنید"
            hint="فرمت‌های CSV / JSON / Excel پشتیبانی می‌شوند"
            onUpload={handleUpload}
            onClear={reset}
          />
        </div>

        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-surface-200 mb-3">ستون‌های قابل قبول</h3>
          <table className="w-full text-right text-xs" data-testid="schema-table">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 px-2 font-medium">ستون</th>
                <th className="pb-2 px-2 font-medium">اجباری؟</th>
                <th className="pb-2 px-2 font-medium">نمونه</th>
              </tr>
            </thead>
            <tbody>
              {SCHEMA_HINTS.map((c) => (
                <tr key={c.name} className="border-b border-surface-800/50">
                  <td className="py-1.5 px-2 font-mono text-surface-200">{c.name}</td>
                  <td className="py-1.5 px-2">
                    {c.required ? (
                      <span className="text-accent-rose">بله</span>
                    ) : (
                      <span className="text-surface-500">خیر</span>
                    )}
                  </td>
                  <td className="py-1.5 px-2 font-mono text-surface-400">{c.example}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-surface-500 mt-3">
            ردیف‌هایی که ستون <span className="font-mono">symbol</span> خالی دارند نادیده گرفته می‌شوند.
            خطاهای هر ردیف در جمع‌بندی نتیجه نمایش داده می‌شود.
          </p>
        </div>

        <div className="glass-card p-4 text-xs text-surface-400">
          برای دیدن نمادهای جدید،{" "}
          <Link href="/instruments" className="text-primary-400 underline">
            به لیست نمادها بروید
          </Link>
          .
        </div>
      </div>
    </AppLayout>
  );
}
