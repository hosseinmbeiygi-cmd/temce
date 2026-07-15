"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------------

export interface FileUploadAccepted {
  filename: string;
  size: number;
  /** First few rows, best-effort, for preview only. */
  preview: string[][];
}

export interface FileUploadResult {
  filename: string;
  total_rows?: number;
  imported?: number;
  parse_errors?: string[];
  import_errors?: string[];
  [key: string]: unknown;
}

export interface FileUploadProps {
  /** Comma-separated accept list, e.g. ".csv,.json,.xlsx" or "image/*" */
  accept?: string;
  /** Max size in bytes; rejects larger files. */
  maxSize?: number;
  /** Title shown above the dropzone. */
  title?: string;
  /** Subtitle / hint. */
  hint?: string;
  /** Called when user clicks the upload button after a file is chosen. */
  onUpload: (
    file: File,
    onProgress: (loaded: number, total: number) => void,
  ) => Promise<FileUploadResult>;
  /** Called when the user clears the current upload. */
  onClear?: () => void;
  /** Disable the controls (e.g. while a parent refetches). */
  disabled?: boolean;
}

// ------ Helpers ------------------------------------------------------------------------------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function filenameIcon(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".csv")) return "📄";
  if (lower.endsWith(".json")) return "🧾";
  if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) return "📊";
  return "📁";
}

async function readPreview(file: File, maxRows = 5): Promise<string[][]> {
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv")) {
    const text = await file.slice(0, 16 * 1024).text();
    const lines = text.split(/\r?\n/).filter(Boolean);
    return lines.slice(0, maxRows + 1).map((l) => l.split(",").map((c) => c.trim()));
  }
  if (name.endsWith(".json")) {
    const text = await file.slice(0, 64 * 1024).text();
    try {
      const data = JSON.parse(text);
      const arr: Record<string, unknown>[] = Array.isArray(data) ? data : Array.isArray(data?.data) ? data.data : [];
      if (!arr.length) return [];
      const headers = Object.keys(arr[0]);
      const rows = arr.slice(0, maxRows).map((row) => headers.map((h) => String(row?.[h] ?? "")));
      return [headers, ...rows];
    } catch {
      return [];
    }
  }
  // .xlsx prescan requires unzip — we show a tip instead of a preview.
  return [];
}

// ------ Component ------------------------------------------------------------------------------------------------------------------------------------------

export default function FileUpload({
  accept = ".csv,.json,.xlsx",
  maxSize = 10 * 1024 * 1024,
  title = "فایل خود را اینجا رها کنید یا کلیک کنید",
  hint,
  onUpload,
  onClear,
  disabled,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string[][]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FileUploadResult | null>(null);

  function reset() {
    setFile(null);
    setPreview([]);
    setProgress(0);
    setError(null);
    setResult(null);
    onClear?.();
  }

  async function acceptFile(candidate: File | null | undefined) {
    if (!candidate) return;
    setError(null);
    setResult(null);
    setProgress(0);

    if (maxSize && candidate.size > maxSize) {
      setError(
        "حجم فایل (" + formatBytes(candidate.size) + ") از حد مجاز (" + formatBytes(maxSize) + ") بیشتر است.",
      );
      return;
    }

    if (accept) {
      const allowed = accept
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);
      const lower = candidate.name.toLowerCase();
      const matched = allowed.some((pattern) => {
        if (pattern.startsWith(".")) return lower.endsWith(pattern);
        if (pattern.endsWith("/*")) {
          // e.g. "image/*" → "image." so "image.png" matches without needing a slash.
          // slice(0, -2) drops both the trailing slash and the star.
          return lower.startsWith(pattern.slice(0, -2));
        }
        return lower.endsWith(pattern);
      });
      if (!matched) {
        setError("فرمت فایل مجاز نیست. فرمت‌های مجاز: " + accept);
        return;
      }
    }

    setFile(candidate);
    setPreview(await readPreview(candidate));
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (disabled || loading) return;
    void acceptFile(e.dataTransfer.files?.[0]);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    void acceptFile(e.target.files?.[0]);
    // Allow re-selecting the same file later.
    e.target.value = "";
  }

  async function handleSubmit() {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    setProgress(0);
    try {
      const data = await onUpload(file, (loaded, total) => {
        setProgress(total ? Math.round((loaded / total) * 100) : 0);
      });
      setResult(data);
      setProgress(100);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "خطای ناشناخته";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && !loading && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !loading) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        data-testid="file-upload-zone"
        className={[
          "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all",
          dragOver
            ? "border-primary-400 bg-primary-500/10"
            : "border-surface-700 hover:border-primary-500 hover:bg-white/5",
          disabled || loading ? "opacity-50 cursor-not-allowed" : "",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          disabled={disabled || loading}
          className="hidden"
          data-testid="file-upload-input"
        />
        <div className="text-5xl mb-4" aria-hidden>
          {file ? filenameIcon(file.name) : "📤"}
        </div>
        <p
          className="text-surface-200 font-medium break-all max-w-full px-2"
          title={file?.name}
        >
          {file ? file.name : title}
        </p>
        {file ? (
          <p className="text-surface-500 text-sm mt-2 truncate max-w-full px-2">
            {formatBytes(file.size)}
            {hint ? ` • ${hint}` : ""}
          </p>
        ) : hint ? (
          <p className="text-surface-500 text-sm mt-2">{hint}</p>
        ) : (
          <p className="text-surface-500 text-sm mt-2">
            فرمت‌های مجاز: <span className="font-mono">{accept}</span>
          </p>
        )}
      </div>

      {preview.length > 0 && (
        <div className="glass-card overflow-x-auto">
          <div className="px-4 py-2 border-b border-surface-800 text-xs text-surface-400">
            پیش‌نمایش (حداکثر {preview.length - 1} ردیف اول)
          </div>
          <table className="w-full text-right text-xs">
            <thead>
              <tr className="text-surface-500 border-b border-surface-800">
                {preview[0]?.map((h, i) => (
                  <th key={i} className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.slice(1).map((row, ri) => (
                <tr key={ri} className="border-b border-surface-800/50 hover:bg-white/5">
                  {row.map((c, ci) => (
                    <td key={ci} className="px-3 py-1.5 font-mono text-surface-300">{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {file && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 bg-primary-600 hover:bg-primary-500 text-white rounded-lg py-2.5 font-medium transition-colors disabled:opacity-50"
          >
            {loading
              ? "در حال بارگذاری... " + progress + "%"
              : "ارسال فایل" + (result ? " (مجدد)" : "")}
          </button>
          <button
            type="button"
            onClick={reset}
            disabled={loading}
            className="px-4 py-2.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            حذف
          </button>
        </div>
      )}

      {loading && (
        <div className="w-full bg-surface-800 rounded-full h-2 overflow-hidden">
          <div
            className="bg-primary-500 h-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {error && (
        <div className="glass-card border border-accent-rose/40 bg-accent-rose/5 px-4 py-3 text-sm text-accent-rose">
          ⚠️ {error}
        </div>
      )}

      {result && (
        <div className="glass-card p-4 text-sm space-y-2">
          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <p className="font-medium text-surface-100">عملیات موفقیت‌آمیز</p>
              <p className="text-surface-400 text-xs mt-0.5">
                فایل: <span className="font-mono">{result.filename}</span>
              </p>
            </div>
          </div>

          {typeof result.total_rows === "number" && (
            <div className="grid grid-cols-3 gap-2 mt-3 text-center">
              <div className="bg-surface-800 rounded p-2">
                <p className="text-xs text-surface-500">کل ردیف‌ها</p>
                <p className="text-lg font-bold text-surface-100">{result.total_rows}</p>
              </div>
              <div className="bg-accent-emerald/10 rounded p-2">
                <p className="text-xs text-accent-emerald">اضافه شد</p>
                <p className="text-lg font-bold text-accent-emerald">{result.imported ?? 0}</p>
              </div>
              <div className="bg-accent-rose/10 rounded p-2">
                <p className="text-xs text-accent-rose">خطا</p>
                <p className="text-lg font-bold text-accent-rose">
                  {(result.parse_errors?.length ?? 0) + (result.import_errors?.length ?? 0)}
                </p>
              </div>
            </div>
          )}

          {((result.parse_errors?.length ?? 0) + (result.import_errors?.length ?? 0)) > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-surface-400 hover:text-surface-200 transition-colors">
                نمایش خطاها
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-accent-rose list-disc pr-5 max-h-48 overflow-auto">
                {result.parse_errors?.map((e, i) => <li key={`p-${i}`}>پارس: {e}</li>)}
                {result.import_errors?.map((e, i) => <li key={`i-${i}`}>ذخیره: {e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
