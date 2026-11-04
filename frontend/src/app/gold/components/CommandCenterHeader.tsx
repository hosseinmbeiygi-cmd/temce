"use client";

import { ThemeToggle } from "@/components/gold/ThemeProvider";

interface CommandCenterHeaderProps {
  lastUpdated?: string | null;
}

function formatUpdated(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("fa-IR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

export default function GoldCommandCenterHeader({ lastUpdated }: CommandCenterHeaderProps) {
  return (
    <header className="command-center-header flex items-center justify-between gap-4 border-b border-zinc-700/40 pb-3">
      <div className="command-center-header__left flex items-baseline gap-3">
        <h1 className="text-xl font-bold text-zinc-100">آمار طلا و بازار</h1>
        <span className="text-[11px] text-zinc-500">آخرین به‌روزرسانی: {formatUpdated(lastUpdated)}</span>
      </div>
      <div className="command-center-header__actions">
        <ThemeToggle />
      </div>
    </header>
  );
}
