"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Bell, Bot, Search } from "lucide-react";
import { NAV_CONFIG, type NavItem } from "@/lib/nav-config";

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

function SidebarNavItem({ item, collapsed, pathname }: { item: NavItem; collapsed: boolean; pathname: string }) {
  const active = item.href ? pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href)) : false;
  const [expanded, setExpanded] = useState(active);

  const allLeaves = item.groups?.flatMap(g => g.items) ?? [];

  return (
    <div>
      <Link
        href={item.href ?? "#"}
        onClick={() => !collapsed && setExpanded(e => !e)}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
          active
            ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
            : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
        }`}
      >
        <item.icon className="size-4 shrink-0" aria-hidden />
        {!collapsed && <span className="truncate">{item.label}</span>}
      </Link>
      {allLeaves.length > 0 && !collapsed && expanded && (
        <div className="mr-3 mt-1 space-y-0.5 border-r border-surface-700/50 pr-2">
          {allLeaves.map((leaf) => {
            const leafActive = pathname === leaf.href;
            return (
              <Link
                key={leaf.href}
                href={leaf.href}
                className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  leafActive
                    ? "bg-primary-600/20 text-primary-300"
                    : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
                }`}
              >
                <span className="truncate">{leaf.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ collapsed = false, onToggle = () => {} }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
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
      <div className="h-14 flex items-center justify-center gap-2 border-b border-surface-800 px-3">
        <Link href="/" className="flex items-center gap-2">
          <div className="size-7 rounded-lg bg-primary-600/20 flex items-center justify-center">
            <span className="text-primary-300 font-bold text-sm">ب</span>
          </div>
          {!collapsed && (
            <span className="font-bold text-sm text-white">بازار سرمایه</span>
          )}
        </Link>
      </div>

      {!collapsed && (
        <form onSubmit={handleSymbolSearch} className="px-2 py-2 border-b border-surface-800">
          <div className="flex items-center gap-2 bg-surface-800 rounded-lg px-2.5 py-2">
            <Search className="size-3.5 text-surface-500 shrink-0" aria-hidden />
            <input
              type="text"
              value={symbolQuery}
              onChange={(e) => setSymbolQuery(e.target.value)}
              placeholder="جستجوی نماد..."
              className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0"
            />
            {symbolQuery && (
              <button type="submit" className="text-xs text-primary-400 hover:text-primary-300 shrink-0">←</button>
            )}
          </div>
        </form>
      )}

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_CONFIG.map((item) => (
          <SidebarNavItem key={item.label} item={item} collapsed={collapsed} pathname={pathname} />
        ))}
      </nav>

      <div className="border-t border-surface-800 py-2 px-2 space-y-1">
        <Link
          href="/admin"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-surface-400 hover:text-surface-200 hover:bg-white/5 transition-all"
        >
          <Bot className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">پنل مدیریت</span>}
        </Link>
        <Link
          href="/alerts"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-surface-400 hover:text-surface-200 hover:bg-white/5 transition-all"
        >
          <Bell className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">هشدارها</span>}
        </Link>
      </div>

      <button
        onClick={onToggle}
        className="h-10 flex items-center justify-center border-t border-surface-800 text-surface-500 hover:text-surface-300 transition-colors"
        aria-label={collapsed ? "باز کردن منو" : "جمع کردن منو"}
      >
        {collapsed ? "←" : "→"}
      </button>
    </aside>
  );
}
