"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import Link from "next/link";
import { toast } from "sonner";

import AppLayout from "@/components/layout/AppLayout";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface FileResult {
  symbol: string;
  rows: number;
  imported: number;
  updated: number;
}

interface BulkImportResponse {
  success: boolean;
  data?: {
    total_files: number;
    total_rows: number;
    imported: number;
    updated: number;
    per_file: Record<string, FileResult>;
    errors: string[];
  };
  error?: { message: string };
}

const CODAL_COLUMNS = [
  { name: "نماد", required: true, example: "فولاد" },
  { name: "نوع گزارش", required: true, example: "سالانه / 3ماهه / 6ماهه" },
  { name: "سال مالی", required: true, example: "1403" },
  { name: "دوره", required: false, example: "12ماهه" },
  { name: "تاریخ انتشار", required: false, example: "1403-04-31" },
  { name: "خلاصه", required: false, example: "صورت‌های مالی سالانه..." },
  { name: "لینک", required: false, example: "https://codal.ir/..." },
  { name: "دسته", required: false, example: "صورت‌های مالی" },
];

export default function CodalImportPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResponse["data"] | null>(null);

  function acceptFiles(candidates: FileList | null | undefined) {
    if (!candidates || candidates.length === 0) return;
    setError(null);
    setResult(null);

    const valid: File[] = [];
    for (const f of Array.from(candidates)) {
      const lower = f.name.toLowerCase();
      if (!lower.endsWith(".xlsx") && !lower.endsWith(".csv")) {
        setError(`فرمت فایل ${f.name} مجاز نیست. فقط XLSX و CSV پشتیبانی می‌شود.`);
        continue;
      }
      valid.push(f);
    }
    if (valid.length > 0) {
      setFiles((prev) => [...prev, ...valid]);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (loading) return;
    acceptFiles(e.dataTransfer.files);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    acceptFiles(e.target.files);
    e.target.value = "";
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function clearAll() {
    setFiles([]);
    setProgress(0);
    setError(null);
    setResult(null);
  }

  async function handleSubmit() {
    if (files.length === 0 || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(0);

    try {
      const formData = new FormData();
      for (const f of files) {
        formData.append("files", f);
      }

      const xhr = new XMLHttpRequest();
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          setProgress(Math.round((event.loaded / event.total) * 100));
        }
      });

      const response = await new Promise<BulkImportResponse>((resolve, reject) => {
        xhr.onload = () => {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("Invalid JSON response"));
          }
        };
        xhr.onerror = () => reject(new Error("Network error"));
        xhr.onabort = () => reject(new Error("Upload aborted"));

        xhr.open("POST", `${API_BASE}/codal/import-bulk`);
        xhr.setRequestHeader("Accept", "application/json");
        xhr.send(formData);
      });

      if (!response.success) {
        setError(response.error?.message || "خطا در بارگذاری");
        return;
      }

      setResult(response.data || null);
      setProgress(100);

      if (response.data) {
        const { total_files, imported, updated, errors } = response.data;
        const msg = `${imported} گزارش جدید + ${updated} به‌روزرسانی از ${total_files} فایل`;
        if (errors.length > 0) {
          toast.warning(msg + ` — ${errors.length} خطا`);
        } else {
          toast.success(msg);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "خطای ناشناخته";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppLayout
      title="ورود اطلاعات کدال"
      subtitle="بارگذاری فایل‌های Excel یا CSV گزارش‌های کدال — هر فایل به نام یک نماد"
    >
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/codal" className="text-sm text-surface-400 hover:text-surface-200 transition-colors">
            ← بازگشت به صفحه کدال
          </Link>
          <span className="text-xs text-surface-500">
            مسیر API: <span className="font-mono">POST /api/v1/codal/import-bulk</span>
          </span>
        </div>

        <div className="glass-card p-4 text-xs text-surface-400 space-y-1">
          <p>📁 <strong>نام فایل = نماد</strong> — مثلاً <span className="font-mono">فولاد.xlsx</span> برای نماد فولاد</p>
          <p>🔄 گزارش تکراری (همان نماد + نوع + سال + دوره) = <strong>به‌روزرسانی</strong></p>
          <p>📊 فرمت‌های مجاز: <span className="font-mono">.xlsx</span> و <span className="font-mono">.csv</span></p>
        </div>

        {/* Drop zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => !loading && inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); inputRef.current?.click(); }
          }}
          onDragOver={(e) => { e.preventDefault(); if (!loading) setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={[
            "border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all",
            dragOver ? "border-primary-400 bg-primary-500/10" : "border-surface-700 hover:border-primary-500 hover:bg-white/5",
            loading ? "opacity-50 cursor-not-allowed" : "",
          ].join(" ")}
        >
          <input ref={inputRef} type="file" accept=".xlsx,.csv" multiple onChange={handleChange} disabled={loading} className="hidden" />
          <div className="text-5xl mb-3">📋</div>
          <p className="text-surface-200 font-medium">
            {files.length > 0 ? `${files.length} فایل انتخاب شد` : "فایل‌های Excel یا CSV را اینجا رها کنید"}
          </p>
          <p className="text-surface-500 text-sm mt-1">می‌توانید چندین فایل را همزمان انتخاب کنید</p>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-surface-200">فایل‌های انتخاب‌شده ({files.length})</h3>
              <button onClick={clearAll} disabled={loading} className="text-xs text-surface-500 hover:text-accent-rose transition-colors disabled:opacity-50">حذف همه</button>
            </div>
            <div className="max-h-60 overflow-y-auto space-y-1">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface-800/50 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span>{f.name.endsWith(".xlsx") ? "📊" : "📄"}</span>
                    <span className="font-mono text-surface-200 truncate" title={f.name}>{f.name}</span>
                    <span className="text-surface-500 text-xs shrink-0">({(f.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <button onClick={() => removeFile(i)} disabled={loading} className="text-surface-500 hover:text-accent-rose transition-colors shrink-0 disabled:opacity-50">✕</button>
                </div>
              ))}
            </div>
            <button type="button" onClick={handleSubmit} disabled={loading} className="w-full mt-4 bg-primary-600 hover:bg-primary-500 text-white rounded-xl py-3 font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <><span className="animate-spin">⏳</span> در حال بارگذاری... {progress}%</> : <><span>🚀</span> شروع بارگذاری {files.length} فایل</>}
            </button>
          </div>
        )}

        {loading && (
          <div className="w-full bg-surface-800 rounded-full h-3 overflow-hidden">
            <div className="bg-gradient-to-r from-primary-500 to-accent-emerald h-full transition-all duration-300 rounded-full" style={{ width: `${progress}%` }} />
          </div>
        )}

        {error && (
          <div className="glass-card border border-accent-rose/40 bg-accent-rose/5 px-4 py-3 text-sm text-accent-rose">⚠️ {error}</div>
        )}

        {result && (
          <div className="glass-card p-6 space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-3xl">✅</span>
              <div>
                <p className="font-semibold text-surface-100 text-lg">بارگذاری با موفقیت انجام شد</p>
                <p className="text-surface-400 text-sm mt-0.5">{result.total_files} فایل · {result.total_rows} ردیف</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface-800 rounded-xl p-4 text-center">
                <p className="text-xs text-surface-500 mb-1">فایل‌ها</p>
                <p className="text-2xl font-bold text-surface-100">{result.total_files}</p>
              </div>
              <div className="bg-accent-emerald/10 rounded-xl p-4 text-center">
                <p className="text-xs text-accent-emerald mb-1">جدید</p>
                <p className="text-2xl font-bold text-accent-emerald">{result.imported}</p>
              </div>
              <div className="bg-accent-amber/10 rounded-xl p-4 text-center">
                <p className="text-xs text-accent-amber mb-1">به‌روزرسانی</p>
                <p className="text-2xl font-bold text-accent-amber">{result.updated}</p>
              </div>
            </div>
            {result.errors && result.errors.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-sm text-accent-rose">❌ {result.errors.length} خطا</summary>
                <ul className="mt-2 space-y-1 text-xs text-accent-rose list-disc pr-5 max-h-48 overflow-auto bg-surface-800/50 rounded-lg p-3">
                  {result.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </details>
            )}
            <button type="button" onClick={clearAll} className="w-full mt-2 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg py-2.5 text-sm font-medium transition-colors">بارگذاری مجدد</button>
          </div>
        )}

        <div className="glass-card p-4 text-xs text-surface-500 space-y-2">
          <p className="font-medium text-surface-400">💡 راه جایگزین:</p>
          <p><span className="font-mono">python scripts/import_codal.py path/to/files/</span></p>
        </div>

        <details className="glass-card p-4">
          <summary className="cursor-pointer text-sm font-medium text-surface-300 hover:text-surface-100 transition-colors">📋 ستون‌های قابل قبول</summary>
          <table className="w-full text-right text-xs mt-3">
            <thead>
              <tr className="text-surface-500 border-b border-surface-700">
                <th className="pb-2 px-2 font-medium">ستون</th>
                <th className="pb-2 px-2 font-medium">اجباری؟</th>
                <th className="pb-2 px-2 font-medium">نمونه</th>
              </tr>
            </thead>
            <tbody>
              {CODAL_COLUMNS.map((c) => (
                <tr key={c.name} className="border-b border-surface-800/50">
                  <td className="py-1.5 px-2 font-mono text-surface-200">{c.name}</td>
                  <td className="py-1.5 px-2">{c.required ? <span className="text-accent-rose">بله</span> : <span className="text-surface-500">خیر</span>}</td>
                  <td className="py-1.5 px-2 font-mono text-surface-400">{c.example}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </div>
    </AppLayout>
  );
}
