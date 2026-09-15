"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";

/**
 * Floating quick-access pill for the smart screener — docked flush to the
 * right edge of the viewport on desktop. Vertical label + icon, navy system.
 */
export default function SmartScreenerFab() {
  const pathname = usePathname();

  // Do not show a shortcut to the page while the user is already there.
  if (pathname === "/smart-screener" || pathname.startsWith("/smart-screener/")) {
    return null;
  }

  return (
    <Link
      href="/smart-screener"
      aria-label="غربالگر هوشمند"
      title="غربالگر هوشمند"
      className="fixed right-0 top-1/2 z-[45] hidden -translate-y-1/2 lg:flex"
    >
      <span className="flex items-center gap-1.5 rounded-l-xl border border-white/10 bg-brand-900/90 px-2 py-3.5 text-brand-100 shadow-[var(--shadow-card-hover)] backdrop-blur transition-all duration-200 hover:bg-brand-800 hover:text-white">
        <Sparkles className="size-4 shrink-0" aria-hidden />
        <span className="text-[10px] font-bold leading-tight tracking-wide [writing-mode:vertical-rl]">
          غربالگر هوشمند
        </span>
      </span>
    </Link>
  );
}
