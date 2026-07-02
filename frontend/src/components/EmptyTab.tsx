"use client";

/**
 * Empty state display with a message and 📭 icon.
 * Used when there's no data to show in a tab or section.
 */
export function EmptyTab({ message = "اطلاعاتی در دسترس نیست" }: { message?: string }) {
  return (
    <div className="text-center py-16 text-surface-500">
      <p className="text-5xl mb-4">📭</p>
      <p>{message}</p>
    </div>
  );
}
