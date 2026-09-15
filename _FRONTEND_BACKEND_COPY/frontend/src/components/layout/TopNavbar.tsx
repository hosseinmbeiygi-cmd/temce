"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  CandlestickChart,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Newspaper,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Search,
  Sun,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { NAV_CONFIG, SEARCH_SHORTCUTS, type NavGroup, type NavItem } from "@/lib/nav-config";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/cn";
import { SEARCH_SYMBOLS } from "@/lib/market-mock";
import { useAuth } from "@/lib/auth-context";

/* ── Small shared bits ──────────────────────────────────────── */

export function IconButton({
  label,
  icon: Icon,
  onClick,
  active,
  className,
}: {
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  active?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-9 cursor-pointer place-items-center rounded-xl border border-white/10 bg-white/5 text-brand-100 transition-all duration-150 hover:bg-white/10 hover:text-white",
        active && "bg-white/12 text-white",
        className,
      )}
    >
      <Icon className="size-4.5" aria-hidden />
    </button>
  );
}

export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();
  return (
    <IconButton
      label={isDark ? "حالت روشن" : "حالت تاریک"}
      icon={isDark ? Sun : Moon}
      onClick={toggleTheme}
    />
  );
}

/* ── Mega panel ─────────────────────────────────────────────── */

function MegaPanel({
  item,
  onNavigate,
  align = "right",
}: {
  item: NavItem;
  onNavigate?: () => void;
  /** RTL: `right` anchors the panel to the item's right edge (first items), `left` for edge items near the left viewport edge. */
  align?: "right" | "left";
}) {
  const groups: NavGroup[] = item.groups ?? [];
  const cols = Math.min(Math.max(groups.length, 1), 4);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.16, ease: "easeOut" }}
      className={`absolute top-full z-50 mt-2 max-w-[90vw] overflow-hidden rounded-2xl border border-line bg-card shadow-[var(--shadow-card-hover)] ${
        align === "left" ? "left-0" : "right-0"
      }`}
      style={{ width: `calc(${cols} * 212px + 40px)` }}
      role="menu"
    >
      <div
        className="grid gap-1 p-4"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {groups.map((group) => (
          <div key={group.title} className="min-w-0 rounded-xl p-1">
            <div className="mb-1.5 flex items-center gap-2 px-2.5 py-1.5">
              {group.icon && <group.icon className="size-3.5 text-ink-3" aria-hidden />}
              <span className="text-[11px] font-bold text-ink-3">{group.title}</span>
            </div>
            <div className="space-y-0.5">
              {group.items.map((leaf) => (
                <Link
                  key={leaf.label + leaf.href}
                  href={leaf.href}
                  onClick={onNavigate}
                  role="menuitem"
                  className="group flex cursor-pointer flex-col gap-0.5 rounded-lg px-2.5 py-2 transition-colors duration-150 hover:bg-soft"
                >
                  <span className="text-[13px] font-medium text-ink group-hover:text-ink">
                    {leaf.label}
                  </span>
                  {leaf.desc && (
                    <span className="text-[10.5px] text-ink-3 leading-snug">{leaf.desc}</span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between border-t border-line bg-soft/60 px-4 py-2.5">
        <span className="text-[11px] text-ink-3">همه بخش‌های {item.label}</span>
        <Link
          href={item.href ?? "#"}
          onClick={onNavigate}
          className="cursor-pointer text-[11px] font-bold text-primary-600 hover:text-primary-500 dark:text-brand-300"
        >
          مشاهده ←
        </Link>
      </div>
    </motion.div>
  );
}

/* ── Symbol search ──────────────────────────────────────────── */

function SymbolSearch({ compact }: { compact: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [focus, setFocus] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);

  const results = q.trim()
    ? SEARCH_SYMBOLS.filter(
        (s) => s.symbol.includes(q.trim()) || s.name.includes(q.trim()),
      ).slice(0, 6)
    : SEARCH_SYMBOLS.slice(0, 5);

  const open = focus;

  function go(href: string) {
    setQ("");
    setFocus(false);
    router.push(href);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = results[activeIdx];
      if (hit) go(`/symbol/${encodeURIComponent(hit.symbol)}`);
    } else if (e.key === "Escape") {
      setFocus(false);
    }
  }

  return (
    <div className={cn("relative", compact ? "w-40" : "w-56")}>
      <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 transition-colors focus-within:border-white/25 focus-within:bg-white/8">
        <Search className="size-4 shrink-0 text-brand-300" aria-hidden />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setActiveIdx(0);
          }}
          onFocus={() => setFocus(true)}
          onBlur={() => setTimeout(() => setFocus(false), 150)}
          onKeyDown={onKeyDown}
          placeholder="جستجوی نماد…"
          aria-label="جستجوی نماد"
          className="h-9 w-full min-w-0 bg-transparent text-[13px] text-white outline-none placeholder:text-brand-400"
        />
        {q && (
          <button
            type="button"
            onClick={() => setQ("")}
            aria-label="پاک کردن جستجو"
            className="cursor-pointer text-brand-300 hover:text-white"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        )}
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 2 }}
            transition={{ duration: 0.14 }}
            className="absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-2xl border border-line bg-card p-2 shadow-[var(--shadow-card-hover)]"
            role="listbox"
          >
            <p className="px-2.5 pb-1 pt-1.5 text-[10px] font-bold text-ink-3">
              {q ? "نتایج جستجو" : "نمادهای پرتقاضا"}
            </p>
            {results.length === 0 ? (
              <p className="px-2.5 py-3 text-[11px] text-ink-3">نمادی یافت نشد</p>
            ) : (
              <div className="space-y-0.5">
                {results.map((s, i) => (
                  <button
                    key={s.symbol}
                    type="button"
                    onMouseDown={() => go(`/symbol/${encodeURIComponent(s.symbol)}`)}
                    onMouseEnter={() => setActiveIdx(i)}
                    role="option"
                    aria-selected={i === activeIdx}
                    className={cn(
                      "flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-right transition-colors",
                      i === activeIdx ? "bg-soft" : "",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-bold text-ink">{s.symbol}</span>
                      <span className="block truncate text-[10.5px] text-ink-3">{s.name}</span>
                    </span>
                    <span className="shrink-0 rounded-md bg-soft px-1.5 py-0.5 text-[10px] font-medium text-ink-3">
                      {s.market}
                    </span>
                  </button>
                ))}
              </div>
            )}
            <div className="mt-1.5 border-t border-line pt-1.5">
              <div className="flex flex-wrap gap-1 px-1">
                {SEARCH_SHORTCUTS.slice(0, 4).map((s) => (
                  <Link
                    key={s.href}
                    href={s.href}
                    onMouseDown={() => setFocus(false)}
                    className="cursor-pointer rounded-md bg-soft px-2 py-1 text-[10px] text-ink-2 transition-colors hover:text-ink"
                  >
                    {s.label}
                  </Link>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Top navbar ─────────────────────────────────────────────── */

export default function TopNavbar({
  sidebarCollapsed = false,
  onSidebarToggle,
}: {
  sidebarCollapsed?: boolean;
  onSidebarToggle?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileGroup, setMobileGroup] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      router.push("/auth/login");
      setLoggingOut(false);
    }
  }

  function openSoon(key: string) {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpenMenu(key);
  }
  function closeSoon() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpenMenu(null), 140);
  }

  // Clean up the hover-close timer on unmount.
  useEffect(() => {
    return () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, []);

  const isActive = (item: NavItem) =>
    item.href === "/" ? pathname === "/" : item.href ? pathname.startsWith(item.href) : false;

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/10 bg-brand-950/95 backdrop-blur supports-[backdrop-filter]:bg-brand-950/85">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-3 lg:px-5">
        {/* Brand */}
        <Link href="/" className="flex shrink-0 cursor-pointer items-center gap-2.5" aria-label="بازار — داشبورد">
          <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-[0_4px_14px_rgba(51,72,107,0.45)]">
            <CandlestickChart className="size-5" aria-hidden />
          </span>
          <span className="hidden leading-tight sm:block">
            <span className="block text-[15px] font-black text-white">بازار سرمایه</span>
            <span className="block text-[9.5px] font-medium tracking-wide text-brand-300">IRAN MARKET TERMINAL</span>
          </span>
        </Link>

        {/* Collapse / compact control — start of the menu */}
        <IconButton
          label={sidebarCollapsed ? "باز کردن منو" : "جمع کردن منو"}
          icon={sidebarCollapsed ? PanelLeftOpen : PanelLeftClose}
          onClick={() => onSidebarToggle?.()}
        />

        {/* Desktop nav (multi-level) */}
        <nav className="hidden min-w-0 flex-1 items-center gap-0.5 lg:flex" aria-label="ناوبری اصلی">
          {NAV_CONFIG.map((item, index) => {
            const active = isActive(item);
            const open = openMenu === item.label;
            const isEdge = index >= NAV_CONFIG.length - 1;
            return (
              <div
                key={item.label}
                className="relative"
                onMouseEnter={() => openSoon(item.label)}
                onMouseLeave={closeSoon}
              >
                <Link
                  href={item.href ?? "#"}
                  onClick={() => setOpenMenu(null)}
                  aria-expanded={open}
                  aria-haspopup="menu"
                  className={cn(
                    "relative flex h-9 cursor-pointer items-center gap-1.5 rounded-xl px-3 text-[13px] font-semibold transition-colors duration-150",
                    active ? "bg-white/12 text-white" : "text-brand-100 hover:bg-white/8 hover:text-white",
                  )}
                >
                  {!sidebarCollapsed && <item.icon className="size-4" aria-hidden />}
                  <span className="whitespace-nowrap">{item.label}</span>
                  {item.groups && item.groups.length > 0 && (
                    <ChevronDown
                      className={cn("size-3.5 text-brand-300 transition-transform duration-150", open && "rotate-180")}
                      aria-hidden
                    />
                  )}
                  {active && <span className="absolute inset-x-2 -bottom-[3px] h-0.5 rounded-full bg-brand-200" />}
                </Link>
                <AnimatePresence>
                  {open && item.groups && (
                    <MegaPanel item={item} align={isEdge ? "left" : "right"} onNavigate={() => setOpenMenu(null)} />
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </nav>

        {/* Actions — opposite side */}
        <div className="mr-auto flex items-center gap-2">
          <div className="hidden md:block">
            <SymbolSearch compact={sidebarCollapsed} />
          </div>
          <Link
            href="/news"
            aria-label="اخبار"
            title="اخبار"
            className="grid size-9 cursor-pointer place-items-center rounded-xl border border-white/10 bg-white/5 text-brand-100 transition-all duration-150 hover:bg-white/10 hover:text-white"
          >
            <Newspaper className="size-4.5" aria-hidden />
          </Link>
          <IconButton label="همگام‌سازی" icon={RefreshCw} onClick={() => router.push("/sync")} />
          <ThemeToggle />
          {isAuthenticated ? (
            <>
              <button
                type="button"
                onClick={() => router.push("/profile")}
                aria-label="پروفایل کاربر"
                title={user?.username ? `پروفایل ${user.username}` : "پروفایل کاربر"}
                className="hidden h-9 max-w-36 cursor-pointer items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-2.5 text-brand-100 transition-all hover:bg-white/10 hover:text-white sm:flex"
              >
                <UserRound className="size-4 shrink-0" aria-hidden />
                <span className="truncate text-xs">{user?.username || "حساب کاربری"}</span>
              </button>
              <IconButton
                label={loggingOut ? "در حال خروج" : "خروج"}
                icon={LogOut}
                onClick={() => void handleLogout()}
                className={loggingOut ? "pointer-events-none opacity-50" : undefined}
              />
            </>
          ) : (
            <Link
              href="/auth/login"
              className="hidden h-9 cursor-pointer items-center rounded-xl border border-white/10 bg-white/5 px-3 text-xs font-semibold text-brand-100 transition-all hover:bg-white/10 hover:text-white sm:flex"
            >
              ورود
            </Link>
          )}
          <IconButton
            label="منوی موبایل"
            icon={mobileOpen ? X : Menu}
            className="lg:hidden"
            onClick={() => setMobileOpen((o) => !o)}
          />
        </div>
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="border-t border-white/10 lg:hidden">
            {/* Search sits OUTSIDE the clipped accordion so its dropdown is never cut off */}
            <div className="px-4 pt-4">
              <SymbolSearch compact={false} />
            </div>
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
            <div className="space-y-1 px-4 py-4">
              {NAV_CONFIG.map((item) => (
                <div key={item.label} className="rounded-xl border border-white/8">
                  <div
                    role="button"
                    tabIndex={0}
                    aria-expanded={mobileGroup === item.label}
                    onClick={() => setMobileGroup(mobileGroup === item.label ? null : item.label)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setMobileGroup(mobileGroup === item.label ? null : item.label);
                      }
                      if (e.key === "Escape") setMobileGroup(null);
                    }}
                    className="flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 text-[13px] font-semibold text-brand-100 hover:bg-white/5"
                  >
                    <span className="flex items-center gap-2">
                      <item.icon className="size-4" aria-hidden />
                      {item.label}
                    </span>
                    <ChevronDown
                      className={cn("size-4 text-brand-300 transition-transform", mobileGroup === item.label && "rotate-180")}
                      aria-hidden
                    />
                  </div>
                  <AnimatePresence>
                    {mobileGroup === item.label && (
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: "auto" }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="grid grid-cols-2 gap-1 px-3 pb-3">
                          {(item.groups ?? []).flatMap((g) => g.items).map((leaf) => (
                            <Link
                              key={leaf.label + leaf.href}
                              href={leaf.href}
                              onClick={() => setMobileOpen(false)}
                              className="cursor-pointer rounded-lg px-2.5 py-2 text-[12px] text-brand-200 hover:bg-white/5 hover:text-white"
                            >
                              {leaf.label}
                            </Link>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </header>
  );
}
