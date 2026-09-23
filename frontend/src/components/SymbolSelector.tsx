"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useSectorCounts } from "@/hooks/useSectorCounts";
import { sectorBadge } from "@/lib/sectors";

interface SuggestionItem {
  symbol: string;
  name: string;
  sector?: string;
}

// ── Market filter tabs ──
// Real symbol counts per market come from `GET /symbols/sectors`; this static
// list is only a fallback when the backend is unreachable.

const FALLBACK_MARKETS: { key: string; label: string }[] = [
  { key: "", label: "همه" },
  { key: "سهام", label: "سهام" },
  { key: "صندوق", label: "صندوق" },
  { key: "طلا و سکه", label: "طلا و سکه" },
  { key: "ارز", label: "ارز" },
  { key: "رمزارز", label: "رمزارز" },
  { key: "کامودیتی", label: "کامودیتی" },
  { key: "بورس کالا", label: "بورس کالا" },
];

/**
 * Shared SymbolSelector — searchable dropdown for stock symbols.
 * Uses `/symbols/search` (static catalog) then falls back to `/instruments/search`.
 */
export default function SymbolSelector({
  value,
  onChange,
  placeholder = "انتخاب نماد...",
  marketFilter,
  onMarketFilterChange,
}: {
  value: string;
  onChange: (s: string) => void;
  placeholder?: string;
  marketFilter?: string;
  onMarketFilterChange?: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const { data: suggestions = [], isLoading } = useQuery({
    queryKey: ["symbol-search", query],
    queryFn: async (): Promise<SuggestionItem[]> => {
      if (!query.trim()) return [];
      // Try static catalog first (DB-free, has sector info)
      try {
        const res = await apiGet<{ success: boolean; data: SuggestionItem[] }>(
          `/symbols/search?q=${encodeURIComponent(query)}&limit=20`
        );
        if (res?.data?.length) return res.data;
      } catch { /* fall through */ }
      // Fallback to instruments search
      try {
        const res = await apiGet<{ success: boolean; data: { items: SuggestionItem[] } }>(
          `/instruments/search?q=${encodeURIComponent(query)}&page_size=8`
        );
        return res?.data?.items || [];
      } catch {
        return [];
      }
    },
    enabled: open && query.length > 0,
  });

  // ── Real market-sector counts from the server ──
  const { counts: sectorCounts, total: totalCount } = useSectorCounts();

  const markets = useMemo(() => {
    const keys = Object.keys(sectorCounts);
    if (!keys.length) return FALLBACK_MARKETS;
    return [
      { key: "", label: "همه" },
      ...keys.map((k) => ({ key: k, label: k })),
    ];
  }, [sectorCounts]);


  // ── Market filter tabs ──

  const filtered = marketFilter
    ? suggestions.filter((s) => s.sector === marketFilter)
    : suggestions;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-surface-800 hover:bg-surface-700 border border-surface-700 rounded-xl px-4 py-2.5 text-white font-mono font-bold text-base transition-colors min-w-[120px]"
      >
        {value || placeholder}
        <span className="text-xs text-surface-500">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 z-50 bg-surface-800 border border-surface-700 rounded-xl shadow-2xl w-[340px] overflow-hidden">
          {/* Search input */}
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجوی نماد..."
            className="w-full bg-surface-900 px-4 py-2.5 text-sm text-white border-b border-surface-700 outline-none placeholder-surface-500"
            autoFocus
          />

          {/* Market filter tabs — counts from GET /symbols/sectors */}
          {markets.length > 0 && (
            <div className="flex gap-1 px-3 py-2 border-b border-surface-700/50 overflow-x-auto flex-wrap">
              {markets.map((m) => {
                const active = (marketFilter || "") === m.key;
                const count = m.key ? sectorCounts[m.key] ?? 0 : totalCount;
                return (
                  <button
                    key={m.key}
                    onClick={() => onMarketFilterChange?.(m.key)}
                    title={`${m.label}: ${count.toLocaleString("en-US")} نماد`}
                    className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap transition-colors ${
                      active
                        ? "bg-primary-600 text-white shadow-sm"
                        : "bg-surface-900 text-surface-400 hover:text-surface-200"
                    }`}
                  >
                    {m.label}
                    {count > 0 && (
                      <span className="mr-1 opacity-60">{count.toLocaleString("en-US")}</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Results */}
          <div className="max-h-48 overflow-y-auto">
            {isLoading && (
              <div className="px-4 py-3 text-xs text-surface-500">در حال جستجو...</div>
            )}
            {!isLoading &&
              filtered.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => {
                    onChange(s.symbol);
                    setOpen(false);
                    setQuery("");
                  }}
                  className={`w-full text-right px-4 py-2.5 text-sm hover:bg-surface-700 transition-colors ${
                    s.symbol === value
                      ? "bg-primary-600/20 text-primary-300"
                      : "text-surface-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono font-bold shrink-0">{s.symbol}</span>
                      {s.name && (
                        <span className="text-xs text-surface-500 truncate max-w-[120px]">
                          {s.name}
                        </span>
                      )}
                    </div>
                    {s.sector && (
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded shrink-0 ${sectorBadge(s.sector)}`}
                      >
                        {s.sector}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            {!isLoading && filtered.length === 0 && query && (
              <div className="px-4 py-3 text-xs text-surface-500">نتیجه‌ای یافت نشد</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
