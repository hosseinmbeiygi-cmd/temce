"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /**
   * پیام اثر جانبی. برای حذف دارایی باید صریح بگوید معامله‌های این دارایی هم
   * تحت‌تأثیرند (F5) — حذف یک ردیف پورتفوی در گزارش مالیاتی جایی را خالی می‌گذارد.
   */
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * دیالوگ تأیید in-page.
 *
 * جایگزین `confirm()` بومی مرورگر شده: آن نسخه نه نام شیء را نشان می‌داد نه
 * عواقبش، و در موبایل/PWA هم قابل استایل‌دهی نیست.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "تأیید",
  cancelLabel = "انصراف",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div
        className="relative w-full max-w-md rounded-xl p-5 space-y-4 shadow-2xl"
        style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}
      >
        <h2 className="text-sm font-bold" style={{ color: "var(--gd-text)" }}>
          {title}
        </h2>
        {description && (
          <div className="text-xs leading-6" style={{ color: "var(--gd-text-2)" }}>
            {description}
          </div>
        )}
        <div className="flex gap-2 justify-start pt-1">
          <button
            ref={confirmRef}
            onClick={onConfirm}
            className="rounded px-4 py-2 text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white"
          >
            {confirmLabel}
          </button>
          <button
            onClick={onCancel}
            className="rounded px-4 py-2 text-xs font-semibold"
            style={{ background: "var(--gd-bg-3)", color: "var(--gd-text-2)" }}
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
