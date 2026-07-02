"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import Link from "next/link";

// ------ Types ------------------------------------------------------------------------------------------------------------------------------------------------

interface CodalAnnouncement {
  id: number;
  symbol: string | null;
  company_name: string | null;
  title: string | null;
  code: string | null;
  date_publish: string | null;
  time_publish: string | null;
  date_title: string | null;
  date_send: string | null;
  time_send: string | null;
  link: string | null;
  link_pdf: string | null;
  link_excel: string | null;
  link_attachment: string | null;
  ins_id: string | null;
  instrument_id: string | null;
  instrument_symbol: string | null;
  fetched_at: string | null;
  created_at: string | null;
}

interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface LazyResponse {
  symbol: string;
  announcements: CodalAnnouncement[];
  count: number;
  stored: number;
  ins_id: string | null;
  instrument_id: string | null;
}

function formatDate(d: string | null): string {
  if (!d) return "\u2014";
  return d.replace(/-/g, "/");
}

function formatTime(t: string | null): string {
  if (!t) return "";
  return t.length >= 5 ? t.substring(0, 5) : t;
}

// ------ Components ---------------------------------------------------------------------------------------------------------------------------------

function AnnouncementCard({ item }: { item: CodalAnnouncement }) {
  const hasPdf = !!item.link_pdf;
  const hasExcel = !!item.link_excel;
  const hasInstrument = !!item.instrument_symbol;
  const hasInsId = !!item.ins_id;

  return (
    <div className="glass-card p-4 hover:bg-surface-800/50 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {/* Symbol + Instrument badge */}
          <div className="flex items-center gap-2 mb-1.5">
            <Link
              href={`/symbol/${item.symbol ?? ''}`}
              className="text-xs font-bold bg-primary-600/15 text-primary-300 px-2 py-0.5 rounded-md hover:bg-primary-600/25 transition-colors"
            >
              {item.symbol || "\u2014"}
            </Link>
            {hasInstrument && (
              <span className="text-xs bg-accent-emerald/10 text-accent-emerald px-2 py-0.5 rounded-md">
                {item.instrument_symbol}
              </span>
            )}
            {hasInsId && (
              <span className="text-[10px] text-surface-500 font-mono">
                ID: {item.ins_id}
              </span>
            )}
            {item.company_name && (
              <span className="text-xs text-surface-400 truncate">
                {item.company_name}
              </span>
            )}
          </div>

          {/* Title */}
          <h3 className="text-sm font-medium text-surface-100 leading-relaxed line-clamp-2">
            {item.title || "\u0628\u062F\u0648\u0646 \u0639\u0646\u0648\u0627\u0646"}
          </h3>

          {/* Date + Time */}
          <div className="flex items-center gap-3 mt-2 text-xs text-surface-500">
            <span>{formatDate(item.date_publish)}</span>
            {item.time_publish && <span>{formatTime(item.time_publish)}</span>}
            {item.instrument_id && (
              <span className="font-mono text-[10px]">
                instr: {item.instrument_id.substring(0, 8)}...
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1.5 shrink-0">
          {hasPdf && (
            <a
              href={item.link_pdf || undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-accent-rose/10 text-accent-rose px-2.5 py-1 rounded-lg hover:bg-accent-rose/20 transition-colors text-center whitespace-nowrap"
            >
              PDF
            </a>
          )}
          {hasExcel && (
            <a
              href={item.link_excel || undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-accent-emerald/10 text-accent-emerald px-2.5 py-1 rounded-lg hover:bg-accent-emerald/20 transition-colors text-center whitespace-nowrap"
            >
              Excel
            </a>
          )}
          {!hasPdf && !hasExcel && item.link && (
            <a
              href={item.link || undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs bg-primary-600/10 text-primary-300 px-2.5 py-1 rounded-lg hover:bg-primary-600/20 transition-colors text-center whitespace-nowrap"
            >
              \u0645\u0634\u0627\u0647\u062F\u0647
            </a>
          )}
        </div>
      </div>

      {/* Instrument ID row */}
      {hasInstrument && item.instrument_id && (
        <div className="mt-2 pt-2 border-t border-surface-700/50 flex gap-2 text-[10px] text-surface-500 font-mono">
          <span>ins_id: {item.ins_id || "\u2014"}</span>
          <span>instrument_id: {item.instrument_id}</span>
        </div>
      )}
    </div>
  );
}

function AnnouncementSkeleton() {
  return (
    <div className="glass-card p-4">
      <div className="flex gap-2 mb-2">
        <Skeleton className="h-5 w-16 rounded-md" />
        <Skeleton className="h-5 w-24 rounded-md" />
      </div>
      <Skeleton className="h-4 w-full mb-2 rounded" />
      <Skeleton className="h-4 w-3/4 rounded" />
      <div className="flex gap-3 mt-2">
        <Skeleton className="h-3 w-24 rounded" />
        <Skeleton className="h-3 w-16 rounded" />
      </div>
    </div>
  );
}

// ------ Stats Card ---------------------------------------------------------------------------------------------------------------------------------

function StatsCard({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string | number;
}) {
  return (
    <div className="glass-card p-3 flex items-center gap-3">
      <span className="text-xl">{icon}</span>
      <div>
        <div className="text-xs text-surface-500">{label}</div>
        <div className="text-lg font-bold text-surface-100">{value}</div>
      </div>
    </div>
  );
}

// ------ Page ---------------------------------------------------------------------------------------------------------------------------------------------------

export default function BrsapiCodalPage() {
  const [symbol, setSymbol] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [page, setPage] = useState(1);
  const [isFetching, setIsFetching] = useState(false);
  const [fetchMessage, setFetchMessage] = useState<string | null>(null);

  // Lazy fetch: when symbol is entered, fetch from BrsApi API on-demand
  const doLazyFetch = async () => {
    if (!symbol.trim()) return;
    setIsFetching(true);
    setFetchMessage(null);
    try {
      const res = await apiGet<{ success: boolean; data: LazyResponse }>(
        `/brsapi/codal-announcements/lazy/${encodeURIComponent(symbol.trim())}?page=1`
      );
      if (res?.success && res.data) {
        const d = res.data;
        setFetchMessage(
          `${d.count} announcements fetched for "${d.symbol}"${
            d.ins_id ? ` | ins_id: ${d.ins_id}` : ""
          }${d.instrument_id ? ` | instrument_id: ${d.instrument_id}` : ""}`
        );
      } else {
        setFetchMessage("No data returned from API");
      }
    } catch {
      setFetchMessage("Error fetching from API");
    }
    setIsFetching(false);
  };

  // Query DB
  const queryKey = ["brsapi-codal-db", symbol, instrumentId, dateStart, dateEnd, page];

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "50");
      if (symbol.trim()) params.set("symbol", symbol.trim());
      if (instrumentId.trim()) params.set("instrument_id", instrumentId.trim());
      if (dateStart) params.set("date_start", dateStart);
      if (dateEnd) params.set("date_end", dateEnd);

      const res = await apiGet<{ success: boolean; data: PaginatedResult<CodalAnnouncement> }>(
        `/brsapi/codal-announcements?${params.toString()}`
      );
      return res?.data ?? { items: [], total: 0, page: 1, page_size: 50, total_pages: 0 };
    },
    placeholderData: (prev) => prev,
    refetchInterval: 60_000,
  });

  const announcements = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, data?.total_pages ?? 1);

  // Stats
  const withInsId = announcements.filter((a) => a.ins_id).length;
  const withInstrumentId = announcements.filter((a) => a.instrument_id).length;
  const withPdf = announcements.filter((a) => a.link_pdf).length;

  const handleSearch = () => {
    setPage(1);
  };

  const handleLazyFetch = async () => {
    await doLazyFetch();
    // After lazy fetch, re-query DB
    setPage(1);
    refetch();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <AppLayout
      title="Codal Announcements"
      subtitle="BrsApi codal announcements \u2014 lazy per-symbol fetch"
    >
      <div className="max-w-5xl mx-auto space-y-5">

        {/* ------ Header --------------------------------------------------------------------------------------------------------- */}
        <div>
          <h1 className="text-2xl font-bold text-surface-100">Codal Announcements</h1>
          <p className="text-sm text-surface-500 mt-1">
            Fetch announcements per-symbol from BrsApi on demand, stored in DB for fast reuse.
          </p>
        </div>

        {/* ------ Stats ------------------------------------------------------------------------------------------------------------------ */}
        {!isLoading && announcements.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatsCard icon="📋" label="Total" value={total.toLocaleString()} />
            <StatsCard icon="🔍" label="With ins_id" value={withInsId} />
            <StatsCard icon="🔗" label="With instrument_id" value={withInstrumentId} />
            <StatsCard icon="📄" label="Has PDF" value={withPdf} />
          </div>
        )}

        {/* ------ Filters ------------------------------------------------------------------------------------------------------ */}
        <div className="glass-card p-4">
          <div className="flex flex-wrap items-end gap-3">
            {/* Symbol */}
            <div className="flex-1 min-w-[120px]">
              <label className="block text-xs text-surface-500 mb-1">Symbol</label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g. فولاد"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 outline-none focus:border-primary-500"
              />
            </div>

            {/* Instrument ID */}
            <div className="flex-1 min-w-[120px]">
              <label className="block text-xs text-surface-500 mb-1">Instrument ID</label>
              <input
                type="text"
                value={instrumentId}
                onChange={(e) => setInstrumentId(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="instruments.id"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
              />
            </div>

            {/* Date Start */}
            <div className="min-w-[120px]">
              <label className="block text-xs text-surface-500 mb-1">From date</label>
              <input
                type="text"
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="1403-01-01"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
              />
            </div>

            {/* Date End */}
            <div className="min-w-[120px]">
              <label className="block text-xs text-surface-500 mb-1">To date</label>
              <input
                type="text"
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="1403-12-29"
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-surface-100 font-mono outline-none focus:border-primary-500"
              />
            </div>

            {/* Search button */}
            <button
              onClick={handleSearch}
              className="bg-surface-700 hover:bg-surface-600 text-surface-200 px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Search DB
            </button>

            {/* Fetch button (lazy) */}
            <button
              onClick={handleLazyFetch}
              disabled={!symbol.trim() || isFetching}
              className="bg-primary-600 hover:bg-primary-500 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isFetching ? "Fetching..." : `Fetch from API`}
            </button>

            {(isLoading || isFetching) && (
              <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />
            )}
          </div>

          {/* Fetch message */}
          {fetchMessage && (
            <div className="mt-3 text-xs text-accent-emerald">
              {fetchMessage}
            </div>
          )}

          {/* Result count */}
          {!isLoading && total > 0 && (
            <div className="mt-3 text-xs text-surface-500">
              {total.toLocaleString()} announcements found
              {symbol && ` for symbol "${symbol}"`}
              {instrumentId && ` | instrument_id: ${instrumentId}`}
            </div>
          )}
        </div>

        {/* ------ Results ------------------------------------------------------------------------------------------------------ */}
        {isLoading && announcements.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <AnnouncementSkeleton key={i} />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-accent-rose">
            <p className="text-5xl mb-4">!</p>
            <p className="text-lg">Error loading announcements</p>
            <p className="text-sm mt-1 text-surface-500">Try again later</p>
          </div>
        ) : announcements.length > 0 ? (
          <>
            <div className="space-y-3">
              {announcements.map((item, i) => (
                <AnnouncementCard key={item.id ?? i} item={item} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 py-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Prev
                </button>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        page === pageNum
                          ? "bg-primary-600 text-white"
                          : "bg-surface-800 text-surface-400 hover:text-surface-200"
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                {totalPages > 7 && <span className="text-surface-500 text-xs">...</span>}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-400 hover:text-surface-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="text-center py-16 text-surface-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">No announcements found</p>
            <p className="text-sm mt-1">Enter a symbol and click &ldquo;Fetch from API&rdquo; to get data</p>
          </div>
        )}

        {/* ------ How it works ------------------------------------------------------------------------------------ */}
        <div className="glass-card p-4 text-xs text-surface-500 space-y-1">
          <p className="font-medium text-surface-400">How it works</p>
          <p>
            Codal announcements require a symbol (<code>l18</code>) parameter. The batch sync
            cannot fetch them without a symbol. Use the <strong>Fetch from API</strong> button
            to pull announcements for a specific symbol on demand. Data is stored in the DB
            so subsequent queries are fast.
          </p>
          <p>
            <strong>Search DB</strong> queries the local database without calling the BrsApi.
            Use this to browse previously fetched data or filter by other fields.
          </p>
        </div>

        {/* ------ Quick Links ------------------------------------------------------------------------------------------ */}
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href="/codal" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            Main Codal Page
          </Link>
          <Link href="/brsapi" className="text-surface-500 hover:text-surface-200 transition-colors px-2 py-1">
            BrsApi Dashboard
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}
