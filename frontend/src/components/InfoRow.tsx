"use client";

/**
 * A simple label/value row for displaying structured info in a card.
 *
 * ```tsx
 * <InfoRow label="نام کامل" value="شرکت نمونه" />
 * ```
 */
export function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-surface-500">{label}</span>
      <span className="font-medium text-surface-200 text-left">{value}</span>
    </div>
  );
}
