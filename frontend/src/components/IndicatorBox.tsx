"use client";

/**
 * Indicator box used in the Price tab for displaying technical
 * indicator values (RSI, MACD, SMA, Volume, etc.).
 */
export function IndicatorBox({
  label,
  value,
  unit,
  type,
}: {
  label: string;
  value: string;
  unit: string;
  type: "positive" | "negative" | "neutral";
}) {
  const color =
    type === "positive"
      ? "text-accent-emerald"
      : type === "negative"
        ? "text-accent-rose"
        : "text-surface-200";

  return (
    <div className="bg-surface-800 rounded-xl p-3">
      <p className="text-xs text-surface-500 mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
      {unit && <p className="text-xs text-surface-600 mt-0.5">{unit}</p>}
    </div>
  );
}
