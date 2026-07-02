"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

interface SuggestionItem {
  symbol: string;
  name: string;
}

/**
 * Shared SymbolSelector — searchable dropdown for stock symbols.
 * Uses `/instruments/search` API for autocomplete.
 */
export default function SymbolSelector({
  value,
  onChange,
  placeholder = "انتخاب نماد...",
}: {
  value: string;
  onChange: (s: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const { data: suggestions = [], isLoading } = useQuery({
    queryKey: ["symbol-search", query],
    queryFn: async (): Promise<SuggestionItem[]> => {
      if (!query.trim()) return [];
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
        <div className="absolute top-full mt-1 right-0 z-50 bg-surface-800 border border-surface-700 rounded-xl shadow-2xl w-72 overflow-hidden">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جستجوی نماد..."
            className="w-full bg-surface-900 px-4 py-2.5 text-sm text-white border-b border-surface-700 outline-none placeholder-surface-500"
            autoFocus
          />
          <div className="max-h-48 overflow-y-auto">
            {isLoading && (
              <div className="px-4 py-3 text-xs text-surface-500">در حال جستجو...</div>
            )}
            {!isLoading &&
              suggestions.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => {
                    onChange(s.symbol);
                    setOpen(false);
                    setQuery("");
                  }}
                  className={`w-full text-right px-4 py-2.5 text-sm hover:bg-surface-700 transition-colors flex items-center justify-between ${
                    s.symbol === value ? "bg-primary-600/20 text-primary-300" : "text-surface-200"
                  }`}
                >
                  <span className="font-mono font-bold">{s.symbol}</span>
                  <span className="text-xs text-surface-500 truncate ml-2">{s.name}</span>
                </button>
              ))}
            {!isLoading && suggestions.length === 0 && query && (
              <div className="px-4 py-3 text-xs text-surface-500">نتیجه‌ای یافت نشد</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
