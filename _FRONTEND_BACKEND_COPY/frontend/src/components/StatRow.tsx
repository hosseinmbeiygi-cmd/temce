"use client";

/**
 * A stat row with an icon, label, and value — used in summary / stats cards.
 *
 * ```tsx
 * <StatRow icon="📋" label="گزارش‌ها" value="۵ گزارش" />
 * ```
 */
export function StatRow({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-surface-400 text-sm">
        {icon} {label}
      </span>
      <span className="font-mono font-bold text-surface-200">{value}</span>
    </div>
  );
}
