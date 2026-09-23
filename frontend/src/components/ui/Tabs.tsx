"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { LucideIcon } from "lucide-react";

export interface TabDef {
  id: string;
  label: string;
  icon?: LucideIcon;
  badge?: number | string;
  /** Blocked until its backing data exists — rendered but not selectable. */
  disabled?: boolean;
}

export interface TabGroup {
  id: string;
  label: string;
  icon: LucideIcon;
  tabs: TabDef[];
}

/** `?tab=<tabId>` is the source of truth, so every tab is deep-linkable. */
export function useTabUrl(active: string, onChange: (tabId: string) => void, key = "tab") {
  const router = useRouter();
  const params = useSearchParams();
  const urlTab = params?.get(key) ?? null;
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    if (urlTab && urlTab !== active) onChange(urlTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- react to the URL only
  }, [urlTab]);

  return useCallback(
    (tabId: string) => {
      onChange(tabId);
      const next = new URLSearchParams(params?.toString() ?? "");
      next.set(key, tabId);
      router.replace(`?${next.toString()}`, { scroll: false });
    },
    [onChange, params, router, key]
  );
}

function neighbour(ids: string[], current: string, delta: number) {
  const i = ids.indexOf(current);
  if (i < 0) return ids[0];
  return ids[(i + delta + ids.length) % ids.length];
}

interface TabStripProps {
  tabs: TabDef[];
  active: string;
  onSelect: (id: string) => void;
  ariaLabel: string;
  variant?: "rail" | "strip";
  className?: string;
}

/** RTL-aware roving-tabindex tablist: ArrowLeft advances, ArrowRight goes back, Home/End jump. */
export function TabStrip({ tabs, active, onSelect, ariaLabel, variant = "strip", className = "" }: TabStripProps) {
  const ref = useRef<HTMLDivElement>(null);
  const ids = useMemo(() => tabs.map((t) => t.id), [tabs]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const step: Record<string, number> = { ArrowLeft: 1, ArrowRight: -1 };
    let next: string | undefined;
    if (e.key in step) next = neighbour(ids, active, step[e.key]);
    else if (e.key === "Home") next = ids[0];
    else if (e.key === "End") next = ids[ids.length - 1];
    if (!next) return;
    e.preventDefault();
    onSelect(next);
    ref.current?.querySelector<HTMLButtonElement>(`[data-tab="${CSS.escape(next)}"]`)?.focus();
  };

  return (
    <div
      ref={ref}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={
        variant === "rail"
          ? `flex flex-col gap-1 ${className}`
          : `flex gap-1 overflow-x-auto ${className}`
      }
    >
      {tabs.map((t) => {
        const selected = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            data-tab={t.id}
            aria-selected={selected}
            aria-controls={`panel-${t.id}`}
            id={`tab-${t.id}`}
            tabIndex={selected ? 0 : -1}
            disabled={t.disabled}
            onClick={() => !t.disabled && onSelect(t.id)}
            className={`shrink-0 rounded-xl text-right transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-400 ${
              variant === "rail" ? "px-3 py-2 text-[11px]" : "px-3 py-1.5 text-xs"
            } ${
              selected
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/25"
                : t.disabled
                  ? "text-surface-600 cursor-not-allowed"
                  : "text-surface-400 hover:text-surface-100 hover:bg-surface-800/80"
            }`}
          >
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              {t.icon && <t.icon className={`w-3.5 h-3.5 shrink-0 ${selected ? "opacity-100" : "opacity-70"}`} />}
              {t.label}
              {t.badge !== undefined && t.badge !== "" && (
                <span
                  className={`text-[9px] font-mono px-1.5 rounded-full ${
                    selected ? "bg-white/20 text-white" : "bg-surface-700/70 text-surface-400"
                  }`}
                >
                  {t.badge}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ tab, children }: { tab: TabDef; children: React.ReactNode }) {
  return (
    <section
      role="tabpanel"
      id={`panel-${tab.id}`}
      aria-labelledby={`tab-${tab.id}`}
      tabIndex={0}
      className="animate-[fadeIn_.2s_ease-out] focus-visible:outline-none"
    >
      {children}
    </section>
  );
}

/** Active tab from `?tab=`, validated against the catalogue so bad links fall back. */
export function useTabController(groups: TabGroup[], fallbackId: string, key = "tab") {
  const params = useSearchParams();
  const initial = findTab(groups, params?.get(key) ?? null).tab.id || fallbackId;
  const [active, setActive] = useState(initial);
  const select = useTabUrl(active, setActive, key);
  const { group, tab } = findTab(groups, active);
  return { active, group, tab, select };
}

/** Group → tab resolution for a flat `?tab=` value. */
export function findTab(groups: TabGroup[], tabId: string | null) {
  for (const g of groups) {
    const t = g.tabs.find((x) => x.id === tabId);
    if (t) return { group: g, tab: t };
  }
  return { group: groups[0], tab: groups[0].tabs[0] };
}
