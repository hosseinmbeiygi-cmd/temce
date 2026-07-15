"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface ColumnHint {
  column: string;
  type: string;
  required: boolean;
  desc: string;
}

interface TemplateInfo {
  label: string;
  endpoint: string;
  method: string;
  accept: string;
  max_size_mb: number;
  columns: ColumnHint[];
  sample_endpoint: string | null;
  sample_label?: string;
  note?: string;
}

interface ImportTemplates {
  instruments: TemplateInfo;
  quotes: TemplateInfo;
  codal: TemplateInfo;
}

interface ImportJob {
  id: string;
  job_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number;
  error_message: string | null;
}

interface ImportResult {
  total_files?: number;
  total_rows?: number;
  imported?: number;
  updated?: number;
  errors?: string[];
  per_file?: Record<string, { symbol: string; rows: number; imported: number; updated: number }>;
}

// ── Helpers ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  return n.toLocaleString("fa-IR");
}

function formatDuration(sec: number): string {
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s.toFixed(0)}s`;
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "completed": return "bg-accent-emerald/15 text-accent-emerald";
    case "failed": return "bg-accent-rose/15 text-accent-rose";
    case "running": return "bg-accent-amber/15 text-accent-amber";
    default: return "bg-surface-700 text-surface-400";
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed": return "موفق";
    case "failed": return "خطا";
    case "running": return "در حال اجرا";
    default: return status;
  }
}

function formatTimeOnly(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

const TABS = [
  { key: "instruments", label: "📋 نمادها", accept: ".csv,.json,.xlsx" },
  { key: "quotes", label: "📊 قیمت‌ها", accept: ".csv" },
  { key: "codal", label: "🏢 کدال", accept: ".xlsx,.csv" },
] as const;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ── Upload Section Component ────────────────────────────────────────────────────────────────────────────────────────────────────────

function UploadSection({
  tabKey,
  templates,
}: {
  tabKey: string;
  templates: ImportTemplates | undefined;
}) {
  const template = templates?.[tabKey as keyof ImportTemplates];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const endpoint =
        tabKey === "instruments"
          ? "/instruments/import"
          : tabKey === "quotes"
            ? "/quotes/import-bulk"
            : "/codal/import-bulk";

      if (tabKey === "instruments") {
        // Single file
        const form = new FormData();
        form.append("file", files[0]);
        const res = await fetch(`${API_BASE}${endpoint}`, {
          method: "POST",
          body: form,
        });
        return res.json();
      }

      // Multiple files
      const form = new FormData();
      for (const f of files) {
        form.append("files", f);
      }
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: form,
      });
      return res.json();
    },
    onSuccess: (data) => {
      setResult({
        total_files: data?.data?.total_files ?? data?.total_files ?? 0,
        total_rows: data?.data?.total_rows ?? 0,
        imported: data?.data?.imported ?? 0,
        updated: data?.data?.updated ?? 0,
        errors: data?.data?.errors ?? data?.data?.parse_errors ?? [],
        per_file: data?.data?.per_file,
      });
      setSelectedFiles([]);
    },
    onError: () => {
      setResult({ errors: ["خطا در آپلود فایل"] });
      setSelectedFiles([]);
    },
  });

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      template?.accept.includes(f.name.split(".").pop()?.toLowerCase() || "")
    );
    if (files.length > 0) setSelectedFiles(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const canUpload = selectedFiles.length > 0 && !uploadMutation.isPending;

  return (
    <div className="space-y-4">
      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragOver
            ? "border-primary-400 bg-primary-600/10"
            : "border-surface-700 hover:border-surface-500 bg-surface-800/30"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple={tabKey !== "instruments"}
          accept={template?.accept}
          onChange={handleFileSelect}
          className="hidden"
        />
        <div className="text-4xl mb-3">{dragOver ? "📥" : "📂"}</div>
        <p className="text-sm text-surface-300 mb-1">
          {selectedFiles.length > 0
            ? selectedFiles.length + " فایل انتخاب شده"
            : "فایل را بکشید و رها کنید یا کلیک کنید"}
        </p>
        <p className="text-xs text-surface-500">
          {template?.accept} • حداکثر {template?.max_size_mb}MB
        </p>
        {template?.note && (
          <p className="text-xs text-accent-amber mt-2">{template.note}</p>
        )}
        {selectedFiles.length > 0 && (
          <div className="mt-3 space-y-1">
            {selectedFiles.map((f, i) => (
              <p key={i} className="text-xs text-surface-400 font-mono">{f.name} ({(f.size / 1024).toFixed(0)}KB)</p>
            ))}
          </div>
        )}
      </div>

      {/* Upload Button */}
      <div className="flex gap-3">
        <button
          onClick={() => canUpload && uploadMutation.mutate(selectedFiles)}
          disabled={!canUpload}
          className="flex-1 py-2.5 bg-primary-600 hover:bg-primary-500 disabled:bg-surface-700 disabled:text-surface-500 text-white rounded-xl text-sm font-semibold transition-all"
        >
          {uploadMutation.isPending ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              در حال آپلود...
            </span>
          ) : (
            "📤 آپلود و Import"
          )}
        </button>
        {template?.sample_endpoint && (
          <a
            href={`${API_BASE}${template.sample_endpoint}`}
            className="px-4 py-2.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5"
          >
            📄 نمونه CSV
          </a>
        )}
      </div>

      {/* Result */}
      {uploadMutation.isPending && (
        <div className="glass-card p-4 text-center">
          <div className="flex items-center justify-center gap-2 text-accent-amber text-sm">
            <span className="w-4 h-4 border-2 border-accent-amber/30 border-t-accent-amber rounded-full animate-spin" />
            در حال پردازش فایل‌ها...
          </div>
        </div>
      )}
      {result && !uploadMutation.isPending && (
        <div className={`glass-card p-4 ${result.errors && result.errors.length > 0 ? "border-accent-rose/30" : "border-accent-emerald/30"}`}>
          <h4 className="text-sm font-bold text-surface-200 mb-3">نتایج Import</h4>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            {result.total_files !== undefined && (
              <div><span className="text-xs text-surface-500">فایل‌ها</span><p className="text-lg font-bold text-surface-200">{formatNumber(result.total_files)}</p></div>
            )}
            {result.total_rows !== undefined && (
              <div><span className="text-xs text-surface-500">ردیف‌ها</span><p className="text-lg font-bold text-surface-200">{formatNumber(result.total_rows)}</p></div>
            )}
            {result.imported !== undefined && (
              <div><span className="text-xs text-surface-500">جدید</span><p className="text-lg font-bold text-accent-emerald">{formatNumber(result.imported)}</p></div>
            )}
            {result.updated !== undefined && (
              <div><span className="text-xs text-surface-500">به‌روزرسانی</span><p className="text-lg font-bold text-accent-amber">{formatNumber(result.updated)}</p></div>
            )}
          </div>
          {result.errors && result.errors.length > 0 && (
            <div>
              <p className="text-xs text-accent-rose mb-1">خطاها ({result.errors.length}):</p>
              <div className="max-h-24 overflow-y-auto space-y-0.5">
                {result.errors.slice(0, 10).map((e, i) => (
                  <p key={i} className="text-[10px] text-accent-rose/80 font-mono">{e}</p>
                ))}
              </div>
            </div>
          )}
          {result.per_file && Object.keys(result.per_file).length > 0 && (
            <div className="mt-2 pt-2 border-t border-surface-700">
              <p className="text-[10px] text-surface-500 mb-1">جزئیات هر فایل:</p>
              <div className="space-y-0.5">
                {Object.entries(result.per_file).map(([name, info]) => (
                  <p key={name} className="text-[10px] text-surface-400 font-mono">
                    {name}: {info.imported} جدید, {info.updated} به‌روز ({info.rows} ردیف)
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Schema Hints */}
      {template && template.columns.length > 0 && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-bold text-surface-400 mb-2">📋 ستون‌های قابل قبول</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-surface-600 border-b border-surface-700">
                  <th className="text-right py-1.5 px-2">ستون</th>
                  <th className="text-right py-1.5 px-2">نوع</th>
                  <th className="text-right py-1.5 px-2">اجباری</th>
                  <th className="text-right py-1.5 px-2">توضیح</th>
                </tr>
              </thead>
              <tbody>
                {template.columns.map((col) => (
                  <tr key={col.column} className="border-b border-surface-800/50">
                    <td className="py-1.5 px-2 font-mono text-surface-300">{col.column}</td>
                    <td className="py-1.5 px-2 text-surface-500">{col.type}</td>
                    <td className="py-1.5 px-2">
                      <span className={`px-1.5 py-0.5 rounded ${col.required ? "bg-accent-rose/15 text-accent-rose" : "bg-surface-800 text-surface-500"}`}>
                        {col.required ? "بله" : "خیر"}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-surface-500">{col.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function DataImportPage() {
  const [activeTab, setActiveTab] = useState<string>("instruments");

  const { data: templates } = useQuery({
    queryKey: ["import-templates"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: ImportTemplates }>("/data-import/templates");
      return res.data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["import-history"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { items: ImportJob[]; total: number } }>("/data-import/history");
      return res.data;
    },
    refetchInterval: 30000,
  });

  const importJobs = history?.items || [];

  return (
    <AppLayout title="📥 ورود داده" subtitle="آپلود CSV و Import داده‌های بازار سرمایه">
      {/* ── Tabs ── */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
              activeTab === tab.key
                ? "bg-primary-600/20 text-primary-300 border border-primary-600/30"
                : "bg-surface-800/50 text-surface-400 border border-surface-700 hover:text-surface-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Upload Section ── */}
      <UploadSection tabKey={activeTab} templates={templates} />

      {/* ── Import History ── */}
      <div className="mt-8">
        <h2 className="text-lg font-bold text-surface-200 mb-4">🔄 تاریخچه Import</h2>
        {historyLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : importJobs.length > 0 ? (
          <div className="glass-card p-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="text-right py-2 px-2">نوع</th>
                  <th className="text-right py-2 px-2">وضعیت</th>
                  <th className="text-right py-2 px-2">مدت</th>
                  <th className="text-right py-2 px-2">زمان</th>
                  <th className="text-right py-2 px-2">خطا</th>
                </tr>
              </thead>
              <tbody>
                {importJobs.slice(0, 20).map((job) => (
                  <tr key={job.id} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                    <td className="py-2 px-2 font-mono text-surface-300">{job.job_type}</td>
                    <td className="py-2 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusBadgeClass(job.status)}`}>
                        {statusLabel(job.status)}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-surface-400">{job.duration_seconds > 0 ? formatDuration(job.duration_seconds) : "—"}</td>
                    <td className="py-2 px-2 text-surface-500">{formatTimeOnly(job.completed_at || job.started_at)}</td>
                    <td className="py-2 px-2 text-accent-rose max-w-[160px] truncate" title={job.error_message || ""}>
                      {job.error_message || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="glass-card p-8 text-center">
            <p className="text-surface-500 text-sm">هنوز هیچ Import انجام نشده است.</p>
            <p className="text-surface-600 text-xs mt-1">یک فایل انتخاب کنید و دکمه آپلود را بزنید.</p>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
