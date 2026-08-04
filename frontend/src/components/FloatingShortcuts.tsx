"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface Shortcut {
  href: string;
  label: string;
  icon: string;
}

const SHORTCUTS: Shortcut[] = [
  { href: "/smart-screener", label: "غربالگر هوشمند", icon: "🤖" },
  { href: "/backtest", label: "بک‌تست", icon: "🧪" },
  { href: "/decision-engine", label: "تصمیم‌گیری", icon: "🧠" },
];

export default function FloatingShortcuts() {
  const pathname = usePathname();

  return (
    <div
      className="fixed left-4 top-1/2 -translate-y-1/2 z-40 flex flex-col gap-2 pointer-events-none"
      role="navigation"
      aria-label="میانبرهای صفحات"
    >
      {SHORTCUTS.map((item) => {
        // Don't show a shortcut when the user is already on that page (or a sub-route of it).
        if (pathname === item.href || pathname.startsWith(`${item.href}/`)) return null;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            title={item.label}
            className="pointer-events-auto flex items-center gap-2
              p-3 md:px-4 md:py-3
              rounded-full
              border border-primary-400/30
              bg-gradient-to-br from-primary-500 to-primary-700 text-white
              hover:from-primary-400 hover:to-primary-600
              shadow-lg hover:shadow-primary-500/40
              backdrop-blur-sm
              transition-all duration-300"
          >
            <span className="text-xl" aria-hidden>
              {item.icon}
            </span>
            <span className="hidden md:inline text-sm font-medium whitespace-nowrap">
              {item.label}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
