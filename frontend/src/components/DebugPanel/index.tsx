"use client";

import { useState } from "react";
import { DebugLog, DebugStats } from "@/hooks/useDebugLogs";

interface DebugPanelProps {
  logs: DebugLog[];
  stats: DebugStats;
  onClear: () => void;
  isEnabled: boolean;
  onToggle: () => void;
  onExport?: () => void;
}

export default function DebugPanel({ logs, stats, onClear, isEnabled, onToggle, onExport }: DebugPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "success" | "error" | "loading">("all");
  const [searchTerm, setSearchTerm] = useState("");

  const filteredLogs = logs.filter((log) => {
    if (filter !== "all" && log.status !== filter) return false;
    if (searchTerm && !log.endpoint.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  if (!isOpen) {
    return (
      <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
        <button
          onClick={() => setIsOpen(true)}
          className="bg-accent-amber text-black px-4 py-2.5 rounded-full shadow-lg hover:bg-accent-amber/80 transition-all text-sm font-medium flex items-center gap-2"
        >
          🐞 عیب‌یابی
          <span
            suppressHydrationWarning
            className={`bg-accent-rose text-white text-xs px-2 py-0.5 rounded-full transition-opacity ${
              stats.error > 0 ? '' : 'opacity-0 pointer-events-none'
            }`}
          >
            {stats.error}
          </span>
        </button>
        {!isEnabled && (
          <span className="text-xs text-surface-500 bg-surface-800/80 px-3 py-1 rounded-full">⏸️ غیرفعال</span>
        )}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-surface-900 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col border border-surface-700">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-700 flex-wrap gap-2">
          <h2 className="text-lg font-bold text-surface-100 flex items-center gap-2">
            🐞 پنل عیب‌یابی
            <span className="text-xs text-surface-500 font-normal">({logs.length} درخواست)</span>
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            <div
              className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
                isEnabled ? "bg-accent-emerald/20 text-accent-emerald" : "bg-surface-700 text-surface-400"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isEnabled ? "bg-accent-emerald" : "bg-surface-500"}`} />
              {isEnabled ? "فعال" : "غیرفعال"}
            </div>
            <button
              onClick={onToggle}
              className="text-xs px-3 py-1 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded transition-colors"
            >
              {isEnabled ? "⏸️" : "▶️"}
            </button>
            <button
              onClick={onClear}
              className="text-xs px-3 py-1 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded transition-colors"
            >
              🗑️ پاک‌کردن
            </button>
            {onExport && (
              <button
                onClick={onExport}
                className="text-xs px-3 py-1 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded transition-colors"
              >
                📥 خروجی
              </button>
            )}
            <button
              onClick={() => setIsOpen(false)}
              className="text-surface-400 hover:text-surface-100 text-xl leading-none px-2"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-5 gap-2 p-3 bg-surface-800/50 border-b border-surface-700">
          <div className="text-center">
            <div className="text-lg font-bold text-surface-100">{stats.total}</div>
            <div className="text-xs text-surface-500">مجموع</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-accent-emerald">{stats.success}</div>
            <div className="text-xs text-surface-500">موفق</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-accent-rose">{stats.error}</div>
            <div className="text-xs text-surface-500">خطا</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-accent-amber">{stats.loading}</div>
            <div className="text-xs text-surface-500">در حال</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-surface-300">
              {stats.averageDuration > 0 ? `${Math.round(stats.averageDuration)}ms` : "-"}
            </div>
            <div className="text-xs text-surface-500">میانگین زمان</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 p-3 border-b border-surface-700 flex-wrap">
          <div className="flex items-center gap-1 bg-surface-800 rounded-lg p-0.5">
            {(["all", "success", "error", "loading"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-xs px-3 py-1 rounded transition-colors ${
                  filter === f ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"
                }`}
              >
                {f === "all" ? "همه" : f === "success" ? "✅ موفق" : f === "error" ? "❌ خطا" : "⏳ در حال"}
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-[150px]">
            <input
              type="text"
              placeholder="جستجو در endpoint..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-1.5 bg-surface-800 border border-surface-700 rounded text-surface-200 text-xs focus:outline-none focus:border-primary-500"
            />
          </div>
          <span className="text-xs text-surface-500">
            {filteredLogs.length} از {logs.length}
          </span>
        </div>

        {/* Logs */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {filteredLogs.length === 0 ? (
            <div className="text-center text-surface-500 py-8 text-sm">
              {logs.length === 0 ? "هیچ درخواستی ثبت نشده است" : "نتیجه‌ای با فیلترهای انتخاب‌شده یافت نشد"}
            </div>
          ) : (
            filteredLogs.map((log) => (
              <div
                key={log.id}
                className={`p-2.5 rounded-lg border transition-all ${
                  log.status === "loading"
                    ? "border-accent-amber/30 bg-accent-amber/5"
                    : log.status === "success"
                    ? "border-accent-emerald/30 bg-accent-emerald/5"
                    : log.status === "error"
                    ? "border-accent-rose/30 bg-accent-rose/5"
                    : "border-surface-700 bg-surface-800/30"
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono text-surface-300 truncate">{log.endpoint}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                          log.status === "loading"
                            ? "bg-accent-amber/20 text-accent-amber"
                            : log.status === "success"
                            ? "bg-accent-emerald/20 text-accent-emerald"
                            : log.status === "error"
                            ? "bg-accent-rose/20 text-accent-rose"
                            : "bg-surface-600/30 text-surface-400"
                        }`}
                      >
                        {log.status === "loading" ? "⏳" : log.status === "success" ? "✅" : log.status === "error" ? "❌" : "ℹ️"}
                      </span>
                      {log.duration && <span className="text-[10px] text-surface-500">{log.duration}ms</span>}
                      <span className="text-[10px] text-surface-500">{log.timestamp}</span>
                      {log.method && (
                        <span className="text-[10px] text-surface-600 bg-surface-800 px-1.5 py-0.5 rounded">
                          {log.method}
                        </span>
                      )}
                    </div>
                    {log.data !== undefined && (
                      <details className="mt-1">
                        <summary className="text-[10px] text-surface-400 cursor-pointer hover:text-surface-300">
                          📊 مشاهده داده‌ی خام
                        </summary>
                        <pre className="mt-1 text-[10px] bg-surface-800 p-2 rounded overflow-x-auto max-h-40 text-surface-300 font-mono">
                          {JSON.stringify(log.data, null, 2)}
                        </pre>
                      </details>
                    )}
                    {log.error && (
                      <div className="mt-1 text-[10px] text-accent-rose bg-accent-rose/10 p-2 rounded break-all">
                        <span className="font-bold">خطا:</span> {log.error}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="p-2 border-t border-surface-700 text-[10px] text-surface-500 text-center">
          آخرین به‌روزرسانی: {new Date().toLocaleTimeString("fa-IR")} • حداکثر {logs.length} لاگ
        </div>
      </div>
    </div>
  );
}