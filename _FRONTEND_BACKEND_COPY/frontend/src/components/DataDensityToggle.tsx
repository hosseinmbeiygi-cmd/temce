"use client";

/**
 * DataDensityToggle — سوئیچ بین حالت «ساده» (compact/clean) و «پیشرفته» (pro data-dense).
 * به‌صورت controlled: والد مالک state است.
 */

interface DataDensityToggleProps {
  mode: "compact" | "pro";
  onChange: (mode: "compact" | "pro") => void;
}

export default function DataDensityToggle({ mode, onChange }: DataDensityToggleProps) {
  return (
    <div className="flex bg-soft rounded-lg border border-line p-0.5" title="چگالی داده">
      <button
        onClick={() => onChange("compact")}
        className={`p-1.5 rounded-md transition-all ${mode === "compact" ? "bg-primary-600 text-white" : "text-ink-3 hover:text-ink"}`}
        title="نمای ساده"
      >
        <span className="material-icons text-sm">density_small</span>
      </button>
      <button
        onClick={() => onChange("pro")}
        className={`p-1.5 rounded-md transition-all ${mode === "pro" ? "bg-primary-600 text-white" : "text-ink-3 hover:text-ink"}`}
        title="نمای حرفه‌ای"
      >
        <span className="material-icons text-sm">density_medium</span>
      </button>
    </div>
  );
}