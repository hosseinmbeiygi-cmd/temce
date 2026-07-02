"use client";

/**
 * A metric display box with label, value, optional unit and colour.
 *
 * ```tsx
 * <MetricBox label="P/E" value="4.5" unit="×" />
 * <MetricBox label="EPS" value="8520" unit="ریال" color="text-accent-emerald" />
 * ```
 */
export function MetricBox({
  label,
  value,
  unit = "",
  color = "text-surface-100",
}: {
  label: string;
  value: string;
  unit?: string;
  color?: string;
}) {
  return (
    <div className="bg-surface-800 rounded-xl p-3">
      <p className="text-xs text-surface-500 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
      {unit && <p className="text-xs text-surface-600 mt-0.5">{unit}</p>}
    </div>
  );
}
