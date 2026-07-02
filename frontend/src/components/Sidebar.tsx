"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { getStoredAuth, clearAuth } from "@/lib/api";

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

const NAV_ITEMS = [
  { href: "/", label: "داشبورد", icon: "📊" },
  { href: "/markets", label: "بازارها", icon: "📈" },
  { href: "/instruments", label: "نمادها", icon: "💹" },
  { href: "/options", label: "آپشن", icon: "🎯" },
  { href: "/quotes", label: "قیمت‌ها", icon: "💵" },
  { href: "/codal", label: "کدال", icon: "🏢" },
  { href: "/news", label: "اخبار", icon: "📰" },
  { href: "/holders", label: "سهامداران", icon: "👥" },
  { href: "/analysis", label: "تحلیل بازار", icon: "🔍" },
  { href: "/alpha", label: "آلفا", icon: "⚡" },
  { href: "/backtest", label: "بک‌تست", icon: "🧪" },
  { href: "/signals", label: "سیگنال‌ها", icon: "📡" },
  { href: "/risk", label: "ریسک", icon: "🛡️" },
  { href: "/data", label: "مدیریت داده", icon: "💾" },
  { href: "/tables", label: "مرور جداول", icon: "🗃️" },
  { href: "/admin", label: "مدیریت", icon: "⚙️" },
];

const AUTH_ITEMS = [
  { href: "/profile", label: "پروفایل", icon: "👤" },
  { href: "/auth/login", label: "ورود", icon: "🔑" },
  { href: "/auth/register", label: "ثبت‌نام", icon: "📝" },
];

export default function Sidebar({ collapsed = false, onToggle = () => {} }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = typeof window !== "undefined" ? getStoredAuth() : null;
  const [symbolQuery, setSymbolQuery] = useState("");

  function handleSymbolSearch(e: FormEvent) {
    e.preventDefault();
    if (symbolQuery.trim()) {
      router.push(`/symbol/${encodeURIComponent(symbolQuery.trim())}`);
    }
  }

  return (
    <aside
      className={`${
        collapsed ? "w-16" : "w-56"
      } transition-all duration-300 bg-surface-900/80 border-l border-surface-800 flex flex-col shrink-0`}
    >
      <div className="h-14 flex items-center justify-center border-b border-surface-800 px-3">
        {collapsed ? (
          <span className="text-xl">📊</span>
        ) : (
          <span className="font-bold text-sm gradient-text">Iran Market</span>
        )}
      </div>

      {!collapsed && (
        <form onSubmit={handleSymbolSearch} className="px-2 py-2 border-b border-surface-800">
          <div className="flex items-center gap-1 bg-surface-800 rounded-lg px-2 py-1.5">
            <span className="text-xs">🔍</span>
            <input
              type="text"
              value={symbolQuery}
              onChange={(e) => setSymbolQuery(e.target.value)}
              placeholder="جستجوی نماد..."
              className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0"
            />
            {symbolQuery && (
              <button type="submit" className="text-xs text-primary-400 hover:text-primary-300 shrink-0">→</button>
            )}
          </div>
        </form>
      )}

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                active
                  ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
                  : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
              }`}
            >
              <span className="text-lg shrink-0">{item.icon}</span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-surface-800 py-2 px-2 space-y-1">
        {auth ? (
          <>
            <Link
              href="/profile"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                pathname === "/profile"
                  ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
                  : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
              }`}
            >
              <span className="text-lg shrink-0">👤</span>
              {!collapsed && <span className="truncate">{auth.user?.username || "پروفایل"}</span>}
            </Link>
            <button
              onClick={() => { clearAuth(); window.location.href = "/auth/login"; }}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm text-rose-400 hover:bg-rose-500/10 transition-all"
            >
              <span className="text-lg shrink-0">🚪</span>
              {!collapsed && <span className="truncate">خروج</span>}
            </button>
          </>
        ) : (
          AUTH_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  active
                    ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
                    : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
                }`}
              >
                <span className="text-lg shrink-0">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })
        )}
      </div>

      <button
        onClick={onToggle}
        className="h-10 flex items-center justify-center border-t border-surface-800 text-surface-500 hover:text-surface-300 transition-colors"
      >
        {collapsed ? "←" : "→"}
      </button>
    </aside>
  );
}
